"""搜索结果精排 — exact-match boost（B12 收敛）

原 heuristic_rerank 的 5 信号加权（命中率/位置/长度/章节）把 RRF 融合分
(~0.01 量级)与余弦分(0-1)混加，尺度失衡；llm_rerank 无调用方。
仅保留可靠信号：完整包含 query 的文档上浮，其余保持融合排序。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def exact_match_boost(
    query: str,
    results: List[Dict[str, Any]],
    top_k: int = 10,
    content_field: str = "content",
) -> List[Dict[str, Any]]:
    """完整命中 query 的结果上浮到最前，组内保持原序（稳定排序）。

    Args:
        query: 用户查询文本
        results: 搜索结果列表（来自 hybrid_search）
        top_k: 返回数量
        content_field: payload 中内容字段的键名
    """
    if not results:
        return []

    if not query or not query.strip():
        return results[:top_k]

    q = query.strip()

    def _has_exact_match(result: Dict[str, Any]) -> int:
        payload = result.get("payload", {})
        content = payload.get(content_field, "") or ""
        if q in content:
            return 0
        meta = payload.get("metadata", {})
        meta_text = " ".join([
            payload.get("chapter", "") or "",
            meta.get("book_title", "") if isinstance(meta, dict) else "",
        ])
        return 0 if q in meta_text else 1

    ranked = sorted(results, key=_has_exact_match)
    return ranked[:top_k]
