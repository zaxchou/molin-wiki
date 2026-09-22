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
- [ ] **B7 artists.py**:async 路由内同步 requests 抓百度百科阻塞事件循环 → httpx.AsyncClient。

## P2 依赖与 CI 健康

- [ ] **B8 依赖修复**:python-multipart 0.0.6→0.0.20+(CVE-2024-24762,与 Dockerfile 漂移);
  torch 2.1.1→2.2.x(2.1 无 py3.12 轮子,本地装不上);passlib/bcrypt 版本冲突评估。
- [ ] **B9 CI 修正**:test.yml 手写 pip 列表与 requirements.txt 漂移 → 改用 requirements.txt;
  加 pip 缓存;compose worker 显式 image 名、qdrant 锁版。
  ⚠️ 附:deploy.sh 的 tar 同步只覆盖/新增、不传播删除——B4 已手动清理服务器残留;
  后续宜改 rsync --delete(仅限源码目录)或在部署后校验已删文件。

## P3 强模型红利——简化补偿性复杂度

- [ ] **B10 JSON 修复栈收敛**:siliconflow_service Level1-4 修复/括号计数/正则提取 → parse_json_loose
  一层 + response_format=json_object;llm_emotion_corrector 三层提取统一。
- [ ] **B11 情感判定统一**:三套算法并存(v3.1 delta 转换/v3.2 judge/admin 择优),content_analysis
  实际直接用 LLM 绝对分 → 以 judge 单路径为唯一,删 delta 死层与 apply_corrections 死代码;
  brush_ink 权重 0 却参与遍历;词典元数据硬编码 deepseek-v4-flash。
- [ ] **B12 知识检索降级**:rewrite→5路检索→heuristic rerank 三级过度,且 RRF 分与余弦分混加
  尺度失衡 → 砍 rewriter(hybrid 已有短查询自适应)、rerank 仅留 exact-match boost、删无调用方的
  llm_rerank;中期用 Qdrant 原生 sparse 替换内存 BM25 全量 scroll。
- [ ] **B13 构图模块收敛**:qichengzhuanhe 去掉"Qwen 预分析+GLM 主调"双次视觉级联;
  composition_llm/knowledge_chat(流式)迁网关(需先给网关加 stream)。
- [ ] **B14 模型名收编**:散落硬编码(admin.py:331、emotion_engine.py:213、providers.py:101、
  inscription_position_analyzer 弃 DashScope 原生 API 改兼容模式)统一读 config。
- [ ] **B15 前端大版本**:Vite 5(EOL)→7 + plugin-vue 连带升级 + engines 声明;
  echarts 6 / pdfjs 5 评估(独立分支,构建回归后再合)。
- [ ] **B16 embedding 升级**:text-embedding-v3→v4 / multimodal-v2(需重建集合,与下次重建合并)。

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
| B5 metadata_extractor 迁网关 | ✅ 2026-09-22 | 本批 |
| B6 tiba_worker 修断链+迁网关 | ✅ 2026-09-22 | 本批 |
| B7~B16 | 待做 | — |
