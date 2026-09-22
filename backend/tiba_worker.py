import time
import concurrent.futures
import os
import json
import redis
from PIL import Image
from datetime import datetime, timedelta
import numpy as np

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.path_utils import normalize_path
from app.llm.client import chat_completion
from app.models.tiba_analysis import TibaAnalysis
from app.models.tiba_job import TibaJob

settings = get_settings()


# ===== Worker Queue Keys =====
QUEUE_KEY_PENDING = "tubi:queue:pending"
QUEUE_KEY_PROCESSING = "tubi:queue:processing"


def get_redis():
    conn = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=15.0,
        retry_on_timeout=True
    )
    conn.ping()
    return conn


def requeue_processing(conn):
    while True:
        item = conn.rpop(QUEUE_KEY_PROCESSING)
        if not item:
            break
        conn.lpush(QUEUE_KEY_PENDING, item)


def cleanup_stale_jobs():
    db = SessionLocal()
    try:
        threshold = datetime.now() - timedelta(minutes=30)
        stale = db.query(TibaAnalysis).filter(
            TibaAnalysis.status == "analyzing",
            TibaAnalysis.updated_at < threshold
        ).all()
        if stale:
            for a in stale:
                a.status = "error"
                a.analysis_note = "分析超时，请重试"
            db.commit()

        jobs = (
            db.query(TibaJob)
            .filter(TibaJob.status == "processing")
            .filter(TibaJob.updated_at.isnot(None))
            .filter(TibaJob.updated_at < threshold)
            .all()
        )
        if jobs:
            for j in jobs:
                j.status = "queued"
                j.last_error = "任务超时已重排队"
            db.commit()
    finally:
        db.close()


# ===== 核心：AI 识图（只做画材+画面描述）=====
def process_one(conn, image_id: str):
    """调用 VL 模型，返回画材 + 画面结构描述，写入 analysis_note"""
    from app.services.siliconflow_service import encode_image_to_base64

    db = SessionLocal()
    db_analysis = None
    db_job = None
    try:
        db_analysis = db.query(TibaAnalysis).filter(TibaAnalysis.image_id == image_id).first()
        if not db_analysis:
            return

        db_job = db.query(TibaJob).filter(TibaJob.image_id == image_id).first()
        if db_job:
            db_job.status = "processing"
            db_job.last_error = None
        else:
            db_job = TibaJob(image_id=image_id, status="processing")
            db.add(db_job)
        db.commit()

        db_analysis.status = "analyzing"
        db.commit()

        filepath = db_analysis.filepath
        if not filepath or not os.path.exists(filepath):
            db_analysis.status = "error"
            db_analysis.analysis_note = "文件不存在"
            db.commit()
            return

        width = db_analysis.image_width or 0
        height = db_analysis.image_height or 0
        if width == 0 or height == 0:
            with Image.open(filepath) as img:
                width, height = img.size
                db_analysis.image_width = width
                db_analysis.image_height = height
            db.commit()

        # VL 模型：画材 + 画面结构
        print(f"[tubi_worker] VL: {image_id}")
        b64 = encode_image_to_base64(filepath, max_side=1536, quality=80)

        prompt = (
            "请用中文简要描述这幅书画作品：\n"
            "1. 画材：纸张/绢本/绫本等材质判断\n"
            "2. 画面内容与构图：主体元素、布局方式、笔墨特点\n"
            "限制在100字以内，只返回描述文本，不要JSON格式。"
        )

        # 视觉通道固定走 qwen（不跟随管理后台默认文本 AI 开关）
        result_text = ""
        try:
            data = chat_completion(
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt}
                ]}],
                provider="qwen",
                model=settings.QWEN_MODEL,
                max_tokens=300,
                temperature=0.3,
                timeout=60.0,
                retries=1,
            )
            result_text = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[tiba_worker] VL error: {e}")

        if not result_text:
            db_analysis.status = "error"
            db_analysis.analysis_note = "VL模型调用失败"
            if db_job:
                db_job.status = "error"
            db.commit()
            return

        # 落库 — 立即 commit，防止进程意外退出丢失结果
        db_analysis.analysis_note = result_text
        db_analysis.status = "analyzed"
        if db_job:
            db_job.status = "done"
        db.commit()
        print(f"[tubi_worker] done: {image_id}")

        # 画材标签（可选，失败不影响主流程）
        try:
            kw_map = {"纸本": "纸本", "绢本": "绢本", "绫本": "绫本", "水墨": "水墨", "设色": "设色", "金笺": "金笺"}
            tags = [v for k, v in kw_map.items() if k in result_text]
            if tags:
                db_analysis.material_tags = ",".join(tags)
                db.commit()
        except Exception:
            pass

    except Exception as e:
        print(f"[tubi_worker] error: {e}")
        import traceback; traceback.print_exc()
        if db_analysis:
            try:
                db_analysis.status = "error"
                db_analysis.analysis_note = str(e)[:500]
                if db_job:
                    db_job.status = "error"
                db.commit()
            except Exception:
                pass
    finally:
        try:
            db.close()
        except Exception:
            pass


# ===== Worker main loop =====
def run():
    conn = None
    cleanup_stale_jobs()
    try:
        conn = get_redis()
        requeue_processing(conn)
    except Exception:
        conn = None

    if conn:
        lock = conn.lock("tubi:analysis:lock", timeout=1800)
        while True:
            try:
                image_id = conn.brpoplpush(QUEUE_KEY_PENDING, QUEUE_KEY_PROCESSING, timeout=5)
            except redis.exceptions.TimeoutError:
                continue
            except redis.exceptions.ConnectionError:
                try:
                    conn = get_redis()
                    lock = conn.lock("tubi:analysis:lock", timeout=1800)
                except Exception:
                    time.sleep(1)
                continue
            if not image_id:
                continue

            acquired = lock.acquire(blocking=True, blocking_timeout=5)
            if not acquired:
                conn.lrem(QUEUE_KEY_PROCESSING, 1, image_id)
                conn.lpush(QUEUE_KEY_PENDING, image_id)
                continue

            try:
                process_one(conn, image_id)
            finally:
                try:
                    lock.release()
                except Exception:
                    pass
                conn.lrem(QUEUE_KEY_PROCESSING, 0, image_id)
    else:
        while True:
            db = SessionLocal()
            job = None
            try:
                job = db.query(TibaJob).filter(TibaJob.status == "queued").order_by(TibaJob.created_at.asc()).first()
                if not job:
                    time.sleep(1)
                    continue
                job.status = "processing"
                db.commit()
                image_id = job.image_id
            finally:
                db.close()

            process_one(conn, image_id)

            db = SessionLocal()
            try:
                job = db.query(TibaJob).filter(TibaJob.image_id == image_id).first()
                if job and job.status != "done" and job.status != "error":
                    job.status = "done"
                    db.commit()
            finally:
                db.close()


if __name__ == "__main__":
    run()
