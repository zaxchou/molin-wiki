"""v2.0 §2.4 — LLM 统一网关：供应商解析（配置驱动 + 管理后台运行时可切）。"""
import time
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

from app.core.config import get_settings
from app.llm.errors import ProviderError

# 管理后台「AI 接口」运行时覆盖（存 site_settings），TTL 缓存避免每次调用查库
RUNTIME_PROVIDER_KEY = "llm_default_provider"
RUNTIME_MODEL_KEY = "llm_default_model"
_RUNTIME_TTL = 5.0
_runtime_cache: Dict[str, Any] = {"at": 0.0, "provider": "", "model": ""}


def read_runtime_defaults() -> Tuple[str, str]:
    """直读 site_settings 里的运行时覆盖，返回 (provider, model)，未设置返回 ("", "")。"""
    try:
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(text(
                "SELECT key, value FROM site_settings WHERE key IN (:p, :m)"
            ), {"p": RUNTIME_PROVIDER_KEY, "m": RUNTIME_MODEL_KEY}).fetchall()
            kv = {r[0]: (r[1] or "").strip() for r in rows}
            return kv.get(RUNTIME_PROVIDER_KEY, ""), kv.get(RUNTIME_MODEL_KEY, "")
        finally:
            db.close()
    except Exception:
        return "", ""  # 表不存在/库不可用时静默回退到 env 行为


def _runtime_default() -> Tuple[str, str]:
    """带 TTL 缓存的运行时覆盖读取（热路径用）。"""
    now = time.monotonic()
    if now - _runtime_cache["at"] <= _RUNTIME_TTL:
        return _runtime_cache["provider"], _runtime_cache["model"]
    provider, model = read_runtime_defaults()
    _runtime_cache.update({"at": now, "provider": provider, "model": model})
    return provider, model


def invalidate_runtime_default() -> None:
    """管理端切换供应商后调用，下次解析立即生效（不等 TTL）。"""
    _runtime_cache["at"] = 0.0


def _custom_ready(s) -> bool:
    return bool(s.AI_API_KEY and s.AI_BASE_URL)


def resolve_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[str, str, str, str, Dict[str, Any]]:
    """解析出 (name, api_key, base_url, model, body_defaults)。

    优先级：调用方显式指定 > site_settings 运行时覆盖（管理后台切换，作为一对生效） >
    env auto（按密钥可用性自动选择：custom → deepseek → qwen → zhipu）。
    body_defaults 是各供应商必需的请求体默认值（如关闭思考模式）。
    """
    s = get_settings()
    explicit = bool((provider or "").strip())
    name = (provider or "").strip().lower()
    runtime_provider, runtime_model = ("", "") if explicit else _runtime_default()

    if not name:
        name = (runtime_provider or "auto").lower()

    if name == "auto":
        if _custom_ready(s):
            name = "custom"
        elif s.DEEPSEEK_API_KEY:
            name = "deepseek"
        elif s.QWEN_API_KEY:
            name = "qwen"
        elif s.ZHIPU_ENABLED and s.ZHIPU_API_KEY:
            name = "zhipu"
        else:
            raise ProviderError("未配置任何可用的 LLM 供应商密钥")

    # 管理后台的全局模型覆盖：仅在「调用方未显式指定 provider/model」时套用
    if model is None and runtime_model and not explicit:
        model = runtime_model

    if name == "custom":
        if not _custom_ready(s):
            raise ProviderError("custom 供应商未配置：需在服务器 env 设置 AI_BASE_URL + AI_API_KEY")
        if not (model or s.AI_MODEL):
            raise ProviderError("custom 供应商未指定模型：请设置 AI_MODEL 或在管理后台填模型覆盖")
        return (name, s.AI_API_KEY, s.AI_BASE_URL.rstrip("/"),
                model or s.AI_MODEL,
                {"thinking": {"type": "disabled"}})  # MiMo 等推理模型默认关思考，防 max_tokens 被 reasoning 吃光
    if name == "deepseek":
        return (name, s.DEEPSEEK_API_KEY, s.DEEPSEEK_BASE_URL,
                model or s.DEEPSEEK_TEXT_MODEL,
                {"thinking": {"type": "disabled"}})
    if name == "qwen":
        return (name, s.QWEN_API_KEY, s.QWEN_BASE_URL,
                model or s.QWEN_MODEL,
                {"enable_thinking": s.QWEN_THINKING_ENABLED})
    if name == "siliconflow":
        return (name, s.SILICONFLOW_API_KEY, "https://api.siliconflow.cn/v1",
                model or s.SILICONFLOW_MODEL, {})
    if name == "zhipu":
        return (name, s.ZHIPU_API_KEY, s.ZHIPU_BASE_URL,
                model or s.ZHIPU_MODEL, {})
    raise ProviderError(f"未知供应商: {name}")
