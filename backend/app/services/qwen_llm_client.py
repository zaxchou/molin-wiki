"""
统一 LLM 调用客户端（v2.0 已成为 app/llm 网关的薄封装）。
- 文本模型：DeepSeek V4 Flash 优先 → Qwen 兜底
- 图像模型：保持 Qwen VL（不变）

网关提供：连接复用 / 统一重试（429、5xx 指数退避）/ 计量 / 统一错误语义。
新代码请直接使用 app.llm 的 chat_completion / chat_completion_async。
本模块保留旧签名（返回 dict，错误以 {"error": ...} 表达）以兼容存量调用方。
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.llm import LLMError, chat_completion, chat_completion_async

logger = logging.getLogger(__name__)


def get_text_llm_config() -> Tuple[str, str, str]:
    """获取当前文本 LLM 配置，返回 (api_key, base_url, model)。

    网关重构前的存量签名，内部改走统一网关的 resolve_provider——
    自动跟随管理后台「AI 接口」开关（MiMo/custom 等），不再写死 DeepSeek→Qwen。
    无可用供应商时返回空三元组（调用方按旧有的 HTTP 失败路径兜底），不抛异常。
    """
    try:
        from app.llm.providers import resolve_provider
        _, api_key, base_url, model, _ = resolve_provider()
        return api_key, base_url, model
    except Exception as e:
        logger.warning("get_text_llm_config: 无可用 LLM 配置: %s", e)
        return "", "", ""


def call_qwen_chat(
    model: str = None,
    messages: List[Dict[str, str]] = None,
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """同步 Chat Completions（旧契约：失败返回 {"error": ...}）。"""
    try:
        return chat_completion(
            messages=messages or [], model=model, max_tokens=max_tokens,
            temperature=temperature, extra_body=extra_body)
    except LLMError as e:
        logger.error("LLM 调用失败: %s", e)
        return {"error": str(e)[:100]}


async def call_qwen_chat_async(
    model: str = None,
    messages: List[Dict[str, str]] = None,
    max_tokens: int = 300,
    temperature: float = 0.1,
    extra_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """异步 Chat Completions（旧契约：失败返回 {"error": ...}）。"""
    try:
        return await chat_completion_async(
            messages=messages or [], model=model, max_tokens=max_tokens,
            temperature=temperature, extra_body=extra_body)
    except LLMError as e:
        logger.error("LLM 调用失败: %s", e)
        return {"error": str(e)[:100]}
