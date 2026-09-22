# Embedding 模型升级预案（v3 → v4 / multimodal-v2）

> B16 产出。本文档是**执行手册**：升级 embedding 模型时按此操作，不要即兴发挥。

## 背景

- 文本向量：`text-embedding-v3`（1024 维）— 知识库文本检索
- 图像向量：`multimodal-embedding-v1`（1024 维）— 图像检索 / 跨模态配图
- 模型名已可配置（B16）：`backend/.env` 的 `EMBEDDING_TEXT_MODEL` / `EMBEDDING_IMAGE_MODEL`
  （`app/core/config.py` 定义，默认值即当前生产模型）

## ⚠️ 铁律

1. **换模型 = 换向量空间**。新向量与旧向量不可比，混用 = 搜索全废。
   改 `.env` 里这两个变量的**同一批次内**必须完成 Qdrant 重建。
2. **embedding 模型永远不跟「AI 接口」开关走**（管理后台切 MiMo/DeepSeek 不影响 embedding）。
3. **用对工具**：重建用 `app/cli.py reindex-qdrant`（会回写 `text_chunks.vector_id`）。
   ⚠️ 永远不要用"recreate 集合但不回写 vector_id"的脚本——AGENTS.md 记载的搜索 0 结果事故即源于此。
4. `deploy.sh` 不会同步 `data/` 与 Qdrant 数据——服务器侧重建要在服务器上做（或先 SCP 数据库）。

## 升级步骤（生产）

```bash
# 0. 前置：确认新模型维度（阿里云百炼文档）
#    text-embedding-v4 支持 64~2048 维（默认 1024）；multimodal-embedding-v2 为 1024 维。
#    若维度变化，qdrant 集合 vector size 也要变（reindex-qdrant 的 ensure_collection 参数）。

# 1. 服务器上停写入（避免重建过程中新 ingest 打进旧向量）
ssh xcx "cd /opt/molin-wiki/deploy && sudo docker compose stop worker"

# 2. 服务器 /opt/molin-wiki/backend/.env 设置新模型
#    EMBEDDING_TEXT_MODEL=text-embedding-v4
#    EMBEDDING_IMAGE_MODEL=multimodal-embedding-v2
#    （注意：deploy.sh 的代码同步会用本地 .env 覆盖它——本地 .env 也改，或部署后服务器再改）

# 3. 重建文本集合（容器内执行，自动回写 text_chunks.vector_id）
ssh xcx "cd /opt/molin-wiki/deploy && sudo docker compose start worker \
  && sudo docker exec deploy-worker-1 python -m app.cli reindex-qdrant"

# 4. 清 embedding 持久缓存（旧模型向量缓存必须失效！）
ssh xcx "rm -rf /opt/molin-wiki/backend/data/.embedding_cache/*"

# 5. 图像集合重建：multimodal 模型变了，knowledge_images 集合需重新入库。
#    走管理后台的知识库重新摄取任务（knowledge_ingest_v2 图像流程），
#    或专用重嵌脚本；确认 points_count 恢复到重建前水平（当前 ~784）。

# 6. 重启 + 使 BM25 缓存失效（重启即自动重载）
ssh xcx "cd /opt/molin-wiki/deploy && sudo docker compose restart backend worker \
  && sudo docker restart deploy-nginx-1"   # recreate 过容器必须重启 nginx（502 事故教训）

# 7. 验证
#    - POST /api/v1/knowledge/search 检查 results 非空且 ai_summary 正常
#    - 以图搜画 / 跨模态配图返回相关结果
#    - docker logs 无 '孤立向量' / 'Qdrant 连接失败'
```

## 回滚

重建前 `qdrant_data` 卷内旧集合即被 `recreate=True` 覆盖——**没有热回滚**。
兜底：把两个 env 改回 v3/v1，再跑一遍步骤 3-7（用旧模型重新嵌入全量数据，
text-embedding-v3 全量约 3190 条，成本可控）。

## 与本批次的边界

- 本批（B16）只做**可配置化 + 本预案**，不实际切换生产模型。
- 实际切换放到下次 Qdrant 全量重建窗口（与数据重建合并执行）。
