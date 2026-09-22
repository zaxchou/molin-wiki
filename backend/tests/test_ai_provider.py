"""AI 接口切换开关 — 契约测试。

覆盖：读取 / 切换 / 越权 / 非法供应商，以及切换后 resolve_provider 真正生效。
"""


def test_ai_provider_anonymous_rejected(client):
    assert client.get("/api/v1/admin/ai-provider").status_code in (401, 403)


def test_ai_provider_reader_rejected(client, reader_token):
    resp = client.get("/api/v1/admin/ai-provider",
                      headers={"Authorization": f"Bearer {reader_token}"})
    assert resp.status_code == 403


def test_ai_provider_get(client, admin_token):
    resp = client.get("/api/v1/admin/ai-provider",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["provider"] in ("auto", "custom", "deepseek", "qwen", "siliconflow", "zhipu")
    assert set(data["keys_present"].keys()) == {"custom", "deepseek", "qwen", "siliconflow", "zhipu"}
    assert isinstance(data["usage"], dict)


def test_ai_provider_switch_roundtrip(client, admin_token):
    hdr = {"Authorization": f"Bearer {admin_token}"}
    # 切到 qwen
    resp = client.put("/api/v1/admin/ai-provider",
                      headers=hdr, json={"provider": "qwen", "model": ""})
    assert resp.status_code == 200, resp.text
    data = client.get("/api/v1/admin/ai-provider", headers=hdr).json()
    assert data["provider"] == "qwen"

    # resolve_provider 应遵循运行时覆盖（调用方未显式指定时）
    from app.llm.providers import resolve_provider, invalidate_runtime_default
    invalidate_runtime_default()
    name, _, _, resolved_model, _ = resolve_provider()
    assert name == "qwen"

    # 调用方显式指定的 model 优先于运行时覆盖
    _, _, _, resolved_model2, _ = resolve_provider(model="my-model")
    assert resolved_model2 == "my-model"

    # 切回 auto
    resp = client.put("/api/v1/admin/ai-provider",
                      headers=hdr, json={"provider": "auto", "model": ""})
    assert resp.status_code == 200
    invalidate_runtime_default()
    data = client.get("/api/v1/admin/ai-provider", headers=hdr).json()
    assert data["provider"] == "auto"


def test_ai_provider_invalid_rejected(client, admin_token):
    resp = client.put("/api/v1/admin/ai-provider",
                      headers={"Authorization": f"Bearer {admin_token}"},
                      json={"provider": "gpt-9000", "model": ""})
    assert resp.status_code == 400


def test_ai_provider_put_needs_super_admin(client, editor_token):
    resp = client.put("/api/v1/admin/ai-provider",
                      headers={"Authorization": f"Bearer {editor_token}"},
                      json={"provider": "qwen", "model": ""})
    assert resp.status_code == 403
