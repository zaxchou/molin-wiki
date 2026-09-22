"""
LLM 情感主裁判服务（v3.2，B11 后唯一 LLM 路径）
────────────────────────────────────────
独立解读题跋情感，不依赖词库分数：
  - 只接收题跋原文与元数据（作者/年代/主题/空间/印章）
  - 返回 7 维绝对分（raw -10~+10）+ 三段式解读
  - 调用方（content_analysis / admin reanalyze）自行与词库基线做逐维度择优融合
  - LLM 调用失败 → 返回 None，调用方降级到纯词库

输出格式：
  {
    "dimension_scores": { "text": {"raw": 3.5, "confidence": 0.8, "reasoning": "..."}, ... },
    "combined": { "polarity": "...", "combined_raw": 2.1, "summary": "积极面：...
消极面：...
综合判断：..." },
    "meta": { "model": "...", "token_count": 1234, "time_ms": 3200 }
  }
"""

import time
import logging
from typing import List, Optional
from app.llm import parse_json_loose
from app.services.qwen_llm_client import call_qwen_chat_async

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 回复中提取 JSON 对象（统一走网关 parse_json_loose，容忍围栏与前后缀文本）"""
    try:
        return parse_json_loose(text)
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════
# v3.2: LLM 主裁判模式 — 独立解读，不看词库分数
# ═══════════════════════════════════════════════════════════════════

JUDGE_SYSTEM_PROMPT = """你是诗词情感分析师。对输入的诗句，按以下三项输出，每项写成一整段。

**一、评分**（写入 dimension_scores 和 combined）：

独立判断每个维度的情感分（raw -10~+10），注意：
- 看反讽、对比、条件句式。不要只看单个词的字面意思
- "甘芳物无限，辣味嫌人餐" → 甘芳是反衬，不是说甜的好
- "任使含咀乃得志" → 重点是"忍受"，不是"得志"
- 书画语境："狂""醉""痴""顽""怪"常为正面（艺术自由）；"辣""拙""丑""枯"可能是艺术主张

**二、解读**（写入 combined.summary，严格按以下三段式，每项写成一整段，引用词句为证）：

积极面：提取正向情绪、自我肯定、坚持、美感、生命意志等，引用词句为证。

消极面：指出孤独、被拒、命运不顺、苦涩、自嘲、幻灭等，引用词句为证。

综合判断：基于以上两面，给出一个总体定性（如：偏积极 / 偏消极 / 悲凉中的倔强 / 热烈下的虚无等），并说明两面如何共存。

要求：语言凝练有分析感，避免流水账。"""

JUDGE_OUTPUT_FORMAT = """
## 输出格式（严格 JSON）
{
  "dimension_scores": {
    "text":      {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "spatial":   {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "painting":  {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "size":      {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "period":    {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "seal":      {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"},
    "theme":     {"raw": <float -10~+10>, "confidence": <float 0-1>, "reasoning": "<为什么>"}
  },
  "combined": {
    "polarity": "positive|negative|neutral|complex",
    "combined_raw": <float>,
    "summary": "积极面：
...

消极面：
...

综合判断：
..."
  }
}
"""

def _build_judge_prompt(
    text: str,
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
) -> str:
    """构建 LLM 裁判的输入提示——只给题跋和上下文，不给词库分数"""
    lines = [f"## 题跋全文\n{text}\n"]

    artist_hints = {
        "李鱓": "扬州八怪之一。早年供奉内廷→中期扬州卖画→晚期归隐。题跋常带自嘲、不驯、苦涩中的倔强。",
        "郑燮": "扬州八怪之一，号板桥。题跋多含为民请命、不媚权贵之意。",
        "徐渭": "大写意开创者，一生坎坷潦倒。题跋常狂放与悲愤交织。",
        "朱耷": "明宗室后裔，国破家亡后出家。画中鱼鸟白眼向人，题跋晦涩隐晦。",
    }
    if artist:
        lines.append(f"## 作者\n{artist}")
        if artist in artist_hints:
            lines.append(f"背景：{artist_hints[artist]}")

    if year:
        lines.append(f"## 年代\n{year}年")
    if themes:
        theme_names = [t.get("name", "") for t in themes[:5]]
        lines.append(f"## 主题标签\n{'、'.join(theme_names)}")
    if spatial_info:
        lines.append(f"## 空间布局参考\n{spatial_info}")
    if seal_info:
        lines.append(f"## 印章参考\n{seal_info}")

    lines.append(JUDGE_OUTPUT_FORMAT)
    return "\n".join(lines)


def judge_score_for_dimension(judge_entry, lexicon_raw: float) -> float:
    """逐维度择优：裁判有明确高置信判断 → 用裁判分；否则用词库基线分。

    content_analysis 与 admin reanalyze 共用此规则，保证两条入口算法一致。
    """
    if not isinstance(judge_entry, dict):
        return lexicon_raw
    raw = judge_entry.get("raw", 0) or 0
    confidence = judge_entry.get("confidence", 0) or 0
    if abs(raw) > 0.1 and confidence >= 0.5:
        return raw
    return lexicon_raw


async def judge_independently(
    text: str,
    artist: str = None,
    year: int = None,
    themes: List = None,
    spatial_info: str = None,
    seal_info: str = None,
) -> Optional[dict]:
    """
    v3.2: LLM 主裁判模式——独立解读题跋，不受词库分数影响。

    只接收题跋和元数据，不接收词库基线分。
    返回独立的情感判断（dimension_scores + combined）。
    失败时返回 None（调用方降级到词库）。
    """
    start = time.time()
    user_prompt = _build_judge_prompt(
        text=text, artist=artist, year=year,
        themes=themes, spatial_info=spatial_info, seal_info=seal_info,
    )

    try:
        response = await call_qwen_chat_async(
            max_tokens=2000,
            temperature=0.4,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        logger.warning(f"LLM judge call failed: {e}")
        return None

    if "error" in response:
        logger.warning(f"LLM judge returned error: {response['error']}")
        return None

    choices = response.get("choices", [])
    if not choices:
        logger.warning("LLM judge: no choices in response")
        return None

    reply_text = choices[0].get("message", {}).get("content", "")
    if not reply_text:
        logger.warning("LLM judge: empty reply")
        return None

    parsed = _extract_json(reply_text)
    if not parsed:
        logger.warning(f"LLM judge: failed to parse JSON (len={len(reply_text)}). First 200: {reply_text[:200]}")
        return None

    dims = parsed.get("dimension_scores")
    if not isinstance(dims, dict) or len(dims) < 7:
        logger.warning(f"LLM judge: invalid dimension_scores")
        return None

    combined = parsed.get("combined")
    if not isinstance(combined, dict) or "summary" not in combined:
        logger.warning("LLM judge: invalid combined")
        return None

    elapsed = time.time() - start
    usage = response.get("usage", {})
    parsed["meta"] = {
        "model": response.get("model", "unknown"),
        "token_count": usage.get("total_tokens", 0),
        "time_ms": int(elapsed * 1000),
    }

    logger.info(f"LLM judge: polarity={combined.get('polarity')}, text_raw={dims.get('text',{}).get('raw')}, elapsed={elapsed:.1f}s")
    return parsed
