"""艺术家临时隐藏开关 — 列表过滤 + admin 读写 + 权限 + 公共设置不泄露。"""
from sqlalchemy import text as sql_text


def _register(client, username):
    r = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "test123456"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return {"Authorization": f"Bearer {data['token']}"}, data["user_id"]


def _promote(user_id, role="super_admin"):
    from app.core.database import SessionLocal

    db = SessionLocal()
    db.execute(
        sql_text("UPDATE users SET role = :r WHERE id = :i"),
        {"r": role, "i": user_id},
    )
    db.commit()
    db.close()


def _list_names(client):
    r = client.get("/api/v1/artists", params={"page_size": 500})
    assert r.status_code == 200
    return [a["name"] for a in r.json()["artists"]]


def test_hidden_artist_toggle(client):
    headers, uid = _register(client, "hide_admin")
    _promote(uid)

    # 创建测试画家（super_admin 创建 → verified=1，默认列表可见）
    r = client.post("/api/v1/artists", json={"name": "刘海勇"}, headers=headers)
    assert r.status_code == 200 and r.json().get("success"), r.text
    assert "刘海勇" in _list_names(client)

    r = client.get("/api/v1/artists/letter-index")
    assert "刘海勇" in r.json()["names"]

    stats_before = client.get("/api/v1/artists/stats-summary").json()["total_verified"]

    # 隐藏
    r = client.put(
        "/api/v1/admin/hidden-artists",
        json={"names": ["刘海勇"]},
        headers=headers,
    )
    assert r.status_code == 200 and r.json()["names"] == ["刘海勇"]

    assert "刘海勇" not in _list_names(client)
    r = client.get("/api/v1/artists/letter-index")
    assert "刘海勇" not in r.json()["names"]
    stats_after = client.get("/api/v1/artists/stats-summary").json()["total_verified"]
    assert stats_after == stats_before - 1

    # 管理员可读名单
    r = client.get("/api/v1/admin/hidden-artists", headers=headers)
    assert r.json()["names"] == ["刘海勇"]

    # 公共 site-settings 不泄露管理开关
    r = client.get("/api/v1/site-settings")
    assert "hidden_artists" not in r.json()["settings"]

    # 恢复
    r = client.put(
        "/api/v1/admin/hidden-artists", json={"names": []}, headers=headers
    )
    assert r.status_code == 200
    assert "刘海勇" in _list_names(client)
    stats_restored = client.get("/api/v1/artists/stats-summary").json()["total_verified"]
    assert stats_restored == stats_before


def test_hidden_artists_requires_admin(client):
    headers, _ = _register(client, "hide_reader")  # 默认 reader
    r = client.put(
        "/api/v1/admin/hidden-artists", json={"names": ["x"]}, headers=headers
    )
    assert r.status_code == 403
    r = client.get("/api/v1/admin/hidden-artists", headers=headers)
    assert r.status_code == 403
    # 未登录也进不来
    r = client.put("/api/v1/admin/hidden-artists", json={"names": ["x"]})
    assert r.status_code == 401
