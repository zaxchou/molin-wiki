"""B6 回归 — tiba_worker 可导入且走 LLM 网关。

背景：模型类 5 月从 tubi_* 改名 tiba_* 后，tiba_worker.py 顶层导入断裂 4 个月，
且 worker_main.py:90 / main.py:216 的 try/except 吞掉 ModuleNotFoundError，
队列任务静默失败。本测试保证：可导入、process_one 存在、VL 调用走网关而非
硬编码 siliconflow、generate_heatmap_data 死代码已删除。
"""


def test_tiba_worker_importable():
    import tiba_worker

    assert callable(tiba_worker.process_one)
    # 模型类导入正确（旧名 Tubi* 若回归会 ImportError）
    from app.models.tiba_analysis import TibaAnalysis
    from app.models.tiba_job import TibaJob
    assert tiba_worker.TibaAnalysis is TibaAnalysis
    assert tiba_worker.TibaJob is TibaJob


def test_tiba_worker_no_dead_heatmap_helper():
    import tiba_worker

    assert not hasattr(tiba_worker, "generate_heatmap_data")


def test_tiba_worker_uses_gateway_not_raw_siliconflow():
    """VL 调用必须走 app.llm.client（vision 通道固定 provider=qwen）。"""
    import inspect

    import tiba_worker

    src = inspect.getsource(tiba_worker.process_one)
    assert "chat_completion" in src
    assert 'provider="qwen"' in src
    assert "api.siliconflow.cn" not in src
    assert "image_url" in src  # 仍传图


def test_metadata_extractor_importable_and_gateway():
    """B5 回归 — 元数据提取走默认文本 LLM 网关。"""
    import inspect

    from app.modules.pantianshou_composition import metadata_extractor

    src = inspect.getsource(metadata_extractor._call_llm)
    assert "chat_completion_async" in src
    assert "deepseek" not in src.lower()
