"""AI 内容读时英文化（中间件 + 缓存表）契约测试。"""
import os

os.environ.setdefault("DATA_DIR", ".")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.ai_text_translation import AiTextTranslation  # noqa: E402
from app.services.ai_translation import invalidate_cache, translate_json  # noqa: E402


def test_en_response_substitutes_cached_translation():
    with TestClient(app) as client:
        db = SessionLocal()
        zh = "测试专用：这是一段需要被替换的分析文本。"
        en = "Test fixture: this analysis text should be substituted."
        db.merge(AiTextTranslation(zh=zh, en=en, source="manual"))
        db.commit()
        db.close()
        invalidate_cache()

        # 单元级：递归替换命中缓存
        payload = {"analysis_note": zh, "items": [{"reasoning": zh, "keep": " untouched"}]}
        out = translate_json(payload, db)
        assert out["analysis_note"] == en
        assert out["items"][0]["reasoning"] == en
        assert out["items"][0]["keep"] == " untouched"

        # 中间件冒烟：EN 请求正常返回且结构不坏
        r_en = client.get("/api/v1/tiba/results?page=1&page_size=1",
                          headers={"Accept-Language": "en"})
        assert r_en.status_code == 200
        assert r_en.json().get("success") is True

    invalidate_cache()
