# 系统现代化改造路线图（2026-09-22 全面审计）

背景:项目主体完成于 2026 年上半年,当时 LLM/VL 能力弱,代码里存在大量"补偿弱模型"的设计。
本次四路并行审计(通用服务层 / tiba+构图模块 / 前端+基础设施 / 情感引擎+知识检索)后汇总。
原则:一个模块一个模块修,每批跑契约测试 + 自我 review + 提交 GitHub 备份。

## P0 正在线上坏的(必须最先修)

- [x] **B1 断链修复** `get_text_llm_config` 在网关重构(80d66a6)中被删,但 7 文件 24 处仍 import,
  ImportError 被 try/except 吞掉 → 搜索改写静默失效、AI 摘要静默为空、洞察静默失败。
  修法:在 qwen_llm_client.py 恢复该函数,内部走 resolve_provider(自动跟随 AI 接口开关)。
- [x] **B2 情感词典管理端写错文件** admin API 写 emotion_lexicon.json(v2.1/385词),
  运行时加载 emotion_lexicon_v3.json(1446词)→ 后台编辑从未生效。修法:写入路径改指 v3。
- [x] **B3 拆除重跑地雷** deploy/fast_reindex.py 用 str(cid) 且不回写 SQLite,
  重跑必复发"搜索 0 结果"事故(AGENTS.md 记载)。app/cli.py reindex-qdrant 已是正确实现,删旧脚本。

## P1 遗留迁移 + 死代码清理

- [x] **B4 死文件清理(低风险)**:deepseek_service.py、baidu_ocr_service.py、qwen_vl_ocr_router.py、
  inscription_summary_generator.py、emotion_lexicon_v2.json、app/tiba 孤儿管线
  (llm_classifier/vl_verifier/cv_mask_extractor/evaluation/learning_loop——线上实际走
  siliconflow_service 单次 VL)、USE_CV_FIRST_PIPELINE 死开关、前端 3 个孤儿 view
  (MyStats/Home/TibaRanking)、start_backend.py(8003 端口过时脚本)。
- [x] **B5 metadata_extractor 迁网关**:硬编码 DEEPSEEK 直连 → chat_completion_async(跟随 AI 开关)。
- [x] **B6 tiba_worker 迁网关**:修复 tubi→tiba 模型改名后 4 个月的断链导入(被 try/except 吞掉);
  删除 generate_heatmap_data 死代码(未导入 Dict 的 NameError);
  VL 调用从硬编码 siliconflow Qwen2.5-VL-32B → 网关 provider=qwen(视觉通道不随默认开关);
  新增 tests/test_worker_imports.py 导入级回归。
- [x] **B7 artists/artist_rules 异步化**:async 路由内 3 处同步 call_qwen_chat(LLM 最长阻塞数十秒)
  + 同步 requests 抓百度百科 → call_qwen_chat_async / httpx.AsyncClient;
  同步 baidu_crawler 走 run_in_threadpool(重写爬虫不在本批范围);
  新增 tests/test_artists_async.py 源码级回归(禁 requests.、禁同步 call_qwen_chat( 子串)。

## P2 依赖与 CI 健康

- [x] **B8 依赖修复**:requirements.txt 对齐生产——python-multipart 0.0.6→0.0.20(CVE-2024-24762,
  Dockerfile 早已 0.0.20,漂移在 requirements);torch 2.1.1→2.2.0 / torchvision 0.16.1→0.17.0
  (2.1 无 py3.12 轮子;与 Dockerfile/生产容器完全一致,py3.12 轮子可用);
  passlib/bcrypt 评估=死依赖(密码哈希实际走 hashlib pbkdf2,全仓库零 import),
  requirements 与 Dockerfile 同步移除 passlib[bcrypt]==1.7.4。
- [x] **B9 CI 修正**:test.yml 手写 pip 列表与 requirements.txt 漂移 → 改用 requirements.txt
  (faiss 1.7.4 无 cp312 轮子升 1.8.0.post1,opencv 转 headless,补 jieba/requests) + pip 缓存 +
  CPU 版 torch 预装;compose worker 显式 image 名、qdrant 锁版 v1.17.1;
  deploy.sh 加删除传播(限 backend/app|tests|顶层 *.py)+ worker 重启。
  🔥 部署时发现两个生产级问题一并修复:①本地 .env 每次部署覆盖服务器,
  QDRANT_URL=localhost 在容器内连不上被静默吞掉 → 生产搜索一直 0 结果,
  compose 注入 QDRANT_URL=http://qdrant:6333;②deploy.sh 从不同步 deploy/,
  服务器 Dockerfile 停在旧版 → 已加 Dockerfile/compose 同步(nginx.conf 除外),
  并当场重建镜像补上生产缺失的 faiss/open-clip。删 reindex_qdrant.py(B3 同款地雷)。

## P3 强模型红利——简化补偿性复杂度

- [x] **B10 JSON 修复栈收敛**:siliconflow_service Level1-4 修复/括号计数/正则提取 → parse_json_loose
  一层 + response_format=json_object(实测 zhipu/dashscope 兼容模式支持,400 拒绝时降级重试);
  llm_emotion_corrector 三层提取统一走 parse_json_loose(尾随文本容忍增强)。
- [x] **B11 情感判定统一**:content_analysis 弃 correct_dimensions(其 delta 换算被调用方无视,
  实际一直用 LLM 绝对分)改走 judge_independently,逐维择优规则抽成
  judge_score_for_dimension 与 admin 共用;删 correct_dimensions/_validate_corrections/
  _empty_corrections/apply_corrections 死代码(约 250 行);judge 输出去掉 brush_ink
  (权重 0 无数据);词典元数据不再硬编码(loader 保留原值回写)。
  🔥 冒烟时发现网关异步路径漏 await——B7 起生产所有 async LLM 调用
  (judge/admin 重分析等)静默失败,已修并拆 sync/async 双实现(asyncio.sleep 退避)。
- [x] **B12 知识检索降级**:删 query_rewriter(LLM 改写最多 10s 延迟 + N 倍 embedding 调用),
  检純回归单查询;reranker 收敛为 exact_match_boost(原 5 信号启发式把 RRF 分当余弦分
  混加,尺度失衡),删无调用方的 llm_rerank;响应去掉 query_rewrite 字段,前端 store 同步清理。
  中期项(Qdrant 原生 sparse 替换内存 BM25)保留待做。
- [x] **B13 构图模块收敛**:网关新增 chat_completion_stream_async(SSE 增量+统一计量);
  qichengzhuanhe standalone 去"Qwen 预分析+主调"双次视觉级联(延迟/成本减半,guided 保留);
  composition_llm 两段手写 httpx 收敛为网关调用;knowledge_chat 流式从硬编码
  DeepSeek 迁网关(跟随 AI 开关)。
- [x] **B14 模型名收编**:providers.py qwen 硬编码 → settings.QWEN_MODEL;admin /config
  展示 resolve_provider 实际生效模型;artists 游记元数据死标签 → 读响应真实 model;
  inscription_position_analyzer 弃 DashScope 原生 API 改兼容模式
  (原 URL 有 dashcope 域名笔误从未连通,VL 分类一直走规则兜底,迁移后恢复)。
- [x] **B15 前端大版本**:Vite 5→7 + plugin-vue 4→6 + engines node>=20.19,
  npm run build 回归通过;echarts 6 / pdfjs 5 评估后暂不升级(前者需回归按需注册与
  图表视觉,后者改 worker 打包,独立分支验证后再合)。
- [x] **B16 embedding 升级**:EMBEDDING_TEXT_MODEL/EMBEDDING_IMAGE_MODEL 可配置
  (默认维持 v3/v1,生产行为不变);升级执行手册 docs/plans/2026-09/embedding-rebuild-playbook.md
  (vector_id 回写工具要求/缓存失效/验证清单/回滚);实际切换留给下次重建窗口。

## 已知事实(修复时注意)

- 网关 client.messages 原样透传 → VL(image_url content)迁移无协议障碍;流式不支持(B13 前置)。
- embedding 模型永远不跟"AI 接口"开关走(换模型=向量空间不一致)。
- nginx.conf 为三站点共用生产配置,非必要不动 server 块。
- 每批完成:pytest 全绿 → git commit → push。

## 进度

| 批次 | 状态 | 提交 |
|---|---|---|
| B1 断链修复 | ✅ 2026-09-22 | 9d6b118 |
| B2 词典写入路径 | ✅ 2026-09-22 | 9d6b118 |
| B3 下架 fast_reindex | ✅ 2026-09-22 | 9d6b118 |
| B4 死代码清理(-11872 行) | ✅ 2026-09-22 | 1ebe019 |
| B5 metadata_extractor 迁网关 | ✅ 2026-09-22 | fc4eb40 |
| B6 tiba_worker 修断链+迁网关 | ✅ 2026-09-22 | fc4eb40 |
| B7 artists/artist_rules 异步化 | ✅ 2026-09-22 | f69a368 |
| B8 依赖修复（multipart/torch/passlib） | ✅ 2026-09-22 | 775b643 |
| B9 CI/部署修正 + 生产搜索修复 | ✅ 2026-09-22 | ef8849c + 79c65c5 |
| B10 JSON 修复栈收敛 | ✅ 2026-09-22 | 512fb94 |
| B11 judge 单路径 + 网关 async 修复 | ✅ 2026-09-22 | d8418b4 + 1977bc9 |
| B12 知识检索降级 | ✅ 2026-09-22 | 03b3219 |
| B13 构图收敛 + 网关 stream | ✅ 2026-09-22 | d789b9a |
| B14 模型名收编 | ✅ 2026-09-22 | d652421 |
| B15 Vite 7 升级 | ✅ 2026-09-22 | 508b336 |
| B16 embedding 可配置 + 预案 | ✅ 2026-09-22 | 89b3ce7 |

## 后续待办（本次未做）

- Qdrant 原生 sparse 替换内存 BM25 全量 scroll（B12 中期项）
- echarts 6 / pdfjs 5 独立分支升级验证（B15 评估后暂缓）
- embedding v3→v4 / multimodal-v2 实际切换（B16 预案就绪，与下次重建合并）
- nginx.conf 纳入 deploy.sh 同步范围前，先核对仓库版与服务器版完全一致
