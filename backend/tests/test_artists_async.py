"""B7 回归 — 画家 API 的 async 路由内不得残留同步阻塞的 LLM/HTTP 调用。

背景：ai_fill_artist / generate_travel_notes / ai_discover_rules 是 async 路由，
内部却用同步 requests 抓百度百科、同步 call_qwen_chat 调 LLM（单次最长 8000 tokens），
会阻塞事件循环数十秒，拖垮全站并发。修复：百科抓取走 httpx.AsyncClient +
run_in_threadpool（同步 crawler 服务），LLM 全部改 call_qwen_chat_async。
"""
import inspect


def test_artists_helpers_are_coroutine_functions():
    from app.api import artists
    assert inspect.iscoroutinefunction(artists._fetch_baike_data)
    assert inspect.iscoroutinefunction(artists._ai_generate_fields)
    assert inspect.iscoroutinefunction(artists.ai_fill_artist)
    assert inspect.iscoroutinefunction(artists.generate_travel_notes)


def test_artists_source_has_no_sync_blocking_calls():
    from app.api import artists
    with open(artists.__file__, encoding="utf-8") as f:
        src = f.read()
    assert "requests.get" not in src
    assert "import requests" not in src
    # 同步旧契约；async 版为 call_qwen_chat_async(，不含此子串
    assert "call_qwen_chat(" not in src
    assert "httpx.AsyncClient" in src
    assert "call_qwen_chat_async(" in src
    assert "await _fetch_baike_data(" in src
    assert "await _ai_generate_fields(" in src


def test_artist_rules_discover_is_async():
    from app.api import artist_rules
    assert inspect.iscoroutinefunction(artist_rules.ai_discover_rules)
    with open(artist_rules.__file__, encoding="utf-8") as f:
        src = f.read()
    assert "call_qwen_chat(" not in src
    assert "await call_qwen_chat_async(" in src
