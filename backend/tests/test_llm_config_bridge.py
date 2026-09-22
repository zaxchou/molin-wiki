"""B1 断链修复回归 — get_text_llm_config 恢复并跟随网关解析。

背景：网关重构(80d66a6)删除了该函数，7 文件 24 处 import 断链且异常被吞，
导致搜索改写/AI 摘要/洞察静默失效。恢复后必须保证：可导入、返回旧契约形状、
配置解析走 resolve_provider（跟随管理后台供应商切换）。
"""


def test_get_text_llm_config_importable_and_shape():
    from app.services.qwen_llm_client import get_text_llm_config
    cfg = get_text_llm_config()
    assert isinstance(cfg, tuple) and len(cfg) == 3
    assert all(isinstance(x, str) for x in cfg)


def test_get_text_llm_config_follows_gateway(monkeypatch):
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config

    s = get_settings()
    # auto 顺序 custom→deepseek→…：清掉 custom（本地 .env 可能配了 MiMo）钉到 deepseek 分支
    monkeypatch.setattr(s, "AI_API_KEY", "", raising=False)
    monkeypatch.setattr(s, "AI_BASE_URL", "", raising=False)
    monkeypatch.setattr(s, "DEEPSEEK_API_KEY", "sk-test-bridge", raising=False)
    api_key, base_url, model = get_text_llm_config()
    assert api_key == "sk-test-bridge"
    assert base_url == s.DEEPSEEK_BASE_URL
    assert model == s.DEEPSEEK_TEXT_MODEL


def test_get_text_llm_config_prefers_custom(monkeypatch):
    """本地/服务器配了 AI_* 时（如 MiMo），auto 应解析到 custom。"""
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config

    s = get_settings()
    monkeypatch.setattr(s, "AI_API_KEY", "sk-test-custom", raising=False)
    monkeypatch.setattr(s, "AI_BASE_URL", "https://example.com/v1", raising=False)
    monkeypatch.setattr(s, "AI_MODEL", "test-model", raising=False)
    api_key, base_url, model = get_text_llm_config()
    assert (api_key, base_url, model) == ("sk-test-custom", "https://example.com/v1", "test-model")


def test_get_text_llm_config_never_raises(monkeypatch):
    """无任何可用密钥时返回空三元组而非抛异常（匹配旧版兜底行为）。"""
    from app.core.config import get_settings
    from app.services.qwen_llm_client import get_text_llm_config

    s = get_settings()
    monkeypatch.setattr(s, "AI_API_KEY", "", raising=False)
    monkeypatch.setattr(s, "AI_BASE_URL", "", raising=False)
    monkeypatch.setattr(s, "DEEPSEEK_API_KEY", "", raising=False)
    monkeypatch.setattr(s, "QWEN_API_KEY", "", raising=False)
    monkeypatch.setattr(s, "ZHIPU_ENABLED", False, raising=False)
    assert get_text_llm_config() == ("", "", "")
