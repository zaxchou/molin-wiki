# molin-wiki 数据库 schema（自动生成）

> 由 `scripts/gen_schema.mjs` 生成，请勿手改；表结构变更后重跑。行数为生成时快照。
> 生成时间：2026-09-24T16:53:09.836Z

## wiki 主库（calligraphy.db） — 36 张表

### ai_text_translations（250 行）

题跋释文中英对照翻译（zh/en，source 标注来源）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| zh | TEXT |  |
| en | TEXT |  |
| source | VARCHAR(50) |  |
| created_at | DATETIME |  |

### alembic_version（1 行）

Alembic 数据库迁移版本标记。

| 列 | 类型 | PK |
|---|---|---|
| version_num | VARCHAR(32) | ✅ |

### analysis_divergence（0 行）

主题/情感判定分歧记录（词典结果 vs LLM 复判，resolved 标记是否处理）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| record_id | INTEGER |  |
| image_id | TEXT |  |
| artist | TEXT |  |
| inscription_content | TEXT |  |
| v4_themes | TEXT |  |
| v4_sentiment | TEXT |  |
| v4_confidence | REAL |  |
| llm_themes | TEXT |  |
| llm_sentiment | TEXT |  |
| divergence_type | TEXT |  |
| divergence_detail | TEXT |  |
| resolved | INTEGER |  |
| created_at | TEXT |  |

### analysis_summary（6 行）

按艺术家的情感/主题分析汇总报告（report_json 含明细）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artist | TEXT |  |
| summary | TEXT |  |
| stats_snapshot | TEXT |  |
| record_count | INTEGER |  |
| generated_at | TEXT |  |
| report_json | TEXT |  |

### api_usage_logs（0 行）

LLM/API 调用计量日志。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| user_id | INTEGER |  |
| endpoint | TEXT |  |
| model_name | TEXT |  |
| tokens_used | INTEGER |  |
| duration_ms | INTEGER |  |
| created_at | DATETIME |  |

### art_schools（0 行）

画派流派资料表（预留，暂无数据）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| name | TEXT |  |
| description | TEXT |  |
| dynasty | TEXT |  |
| origin | TEXT |  |
| rep_artists | TEXT |  |
| style_features | TEXT |  |
| created_at | TIMESTAMP |  |
| updated_at | TIMESTAMP |  |

### artist_change_requests（0 行）

艺术家资料修改申请（old/new 值 + 审核状态流）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artist_id | INTEGER |  |
| request_type | VARCHAR(30) |  |
| field_name | VARCHAR(100) |  |
| old_value | TEXT |  |
| new_value | TEXT |  |
| change_summary | TEXT |  |
| submitter_id | INTEGER |  |
| reviewer_id | INTEGER |  |
| status | VARCHAR(20) |  |
| review_comment | TEXT |  |
| created_at | TIMESTAMP |  |
| reviewed_at | TIMESTAMP |  |

### artist_claims（0 行）

用户认领艺术家申请（apply_reason → 审核）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| user_id | INTEGER |  |
| artist_name | VARCHAR(255) |  |
| claim_type | VARCHAR(20) |  |
| status | VARCHAR(20) |  |
| apply_reason | TEXT |  |
| reviewed_by | INTEGER |  |
| created_at | DATETIME |  |
| reviewed_at | DATETIME |  |

### artist_rules（3 行）

情绪引擎的艺术家基线：emotion_baseline、生平阶段、主题/情感期望分布、印章规则。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artist_name | TEXT |  |
| emotion_baseline | REAL |  |
| life_stages | TEXT |  |
| sentiment_note | TEXT |  |
| theme_note | TEXT |  |
| theme_exceptions | TEXT |  |
| expected_theme_distribution | TEXT |  |
| expected_sentiment_distribution | TEXT |  |
| rules_version | TEXT |  |
| created_at | TEXT |  |
| updated_at | TEXT |  |
| seal_rules | TEXT |  |

### artist_stats_cache（33 行）

艺术家统计缓存（stats_data JSON，避免重复聚合）。

| 列 | 类型 | PK |
|---|---|---|
| artist_id | INTEGER | ✅ |
| stats_data | TEXT |  |
| updated_at | TIMESTAMP |  |

### artists（473 行）

艺术家主表（约 473 位）。富文本字段（biography/chronology/relations 等）多为 JSON 或 Markdown；enabled/verified/featured 控制展示；dynasty 是常用过滤维度。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| name | VARCHAR(100) |  |
| birth_year | INTEGER |  |
| background | TEXT |  |
| sentiment_note | TEXT |  |
| theme_note | TEXT |  |
| theme_aliases | VARCHAR(500) |  |
| keyword_rules | TEXT |  |
| specialties | TEXT |  |
| enabled | INTEGER |  |
| created_at | TEXT |  |
| updated_at | TEXT |  |
| alias | TEXT |  |
| dynasty | TEXT |  |
| hometown | TEXT |  |
| avatar_url | TEXT |  |
| death_year | INTEGER |  |
| biography | TEXT |  |
| bio_events | TEXT |  |
| art_school | TEXT |  |
| masterpieces | TEXT |  |
| tags | TEXT |  |
| baidu_url | TEXT |  |
| view_count | INTEGER |  |
| featured | INTEGER |  |
| banner_url | TEXT |  |
| summary | TEXT |  |
| nationality | TEXT |  |
| occupation | TEXT |  |
| main_achievements | TEXT |  |
| representative_works_text | TEXT |  |
| art_style | TEXT |  |
| influence | TEXT |  |
| historical_evaluation | TEXT |  |
| character_relations | TEXT |  |
| anecdotes | TEXT |  |
| art_chronology | TEXT |  |
| published_works | TEXT |  |
| gallery_images | TEXT |  |
| references | TEXT |  |
| verified | INTEGER |  |
| photos | TEXT |  |
| travel_notes | TEXT |  |

### artwork_artists（0 行）

作品↔艺术家多对多关联（预留）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artwork_id | INTEGER |  |
| artist_id | INTEGER |  |
| role | VARCHAR(20) |  |
| sort_order | INTEGER |  |
| created_at | TIMESTAMP |  |

### artwork_libraries（8 行）

作品馆藏集/分册（visibility: public/private，owner_id 归属，artwork_count 缓存计数）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| name | VARCHAR(255) |  |
| artist_name | VARCHAR(255) |  |
| description | TEXT |  |
| owner_id | INTEGER |  |
| visibility | VARCHAR(20) |  |
| artwork_count | INTEGER |  |
| created_at | TIMESTAMP |  |
| updated_at | TIMESTAMP |  |

### auction_records（0 行）

拍卖记录（预留）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artwork_id | INTEGER |  |
| auction_house | TEXT |  |
| sale_date | TEXT |  |
| lot_number | TEXT |  |
| estimate_low | FLOAT |  |
| estimate_high | FLOAT |  |
| hammer_price | FLOAT |  |
| currency | TEXT |  |
| notes | TEXT |  |
| created_at | DATETIME |  |

### change_requests（3 行）

作品字段修改申请（含 draft_data 草稿与 base_revision 冲突控制）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| library_id | INTEGER |  |
| artwork_id | INTEGER |  |
| request_type | VARCHAR(30) |  |
| field_name | VARCHAR(100) |  |
| old_value | TEXT |  |
| new_value | TEXT |  |
| change_summary | TEXT |  |
| submitter_id | INTEGER |  |
| reviewer_id | INTEGER |  |
| status | VARCHAR(20) |  |
| review_comment | TEXT |  |
| created_at | DATETIME |  |
| reviewed_at | DATETIME |  |
| draft_data | TEXT |  |
| base_revision | INTEGER |  |

### characters（10 行）

碑帖单字（字形 feature_vector JSON、bounding_box、图片路径）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| stele_id | INTEGER |  |
| character | VARCHAR(10) |  |
| unicode | VARCHAR(10) |  |
| image_path | VARCHAR(255) |  |
| feature_vector | JSON |  |
| stroke_count | INTEGER |  |
| bounding_box | JSON |  |
| meta_info | JSON |  |
| created_at | DATETIME |  |

### chat_messages（108 行）

聊天消息（知识库问答与艺术家问答共用；sources 为引用来源 JSON）。

| 列 | 类型 | PK |
|---|---|---|
| id | TEXT(36) | ✅ |
| session_id | TEXT(36) |  |
| role | TEXT |  |
| content | TEXT |  |
| sources | TEXT |  |
| token_index | INTEGER |  |
| created_at | TIMESTAMP |  |

### chat_sessions（19 行）

聊天会话（session_type 区分知识库/艺术家问答；artist_id 关联）。

| 列 | 类型 | PK |
|---|---|---|
| id | TEXT(36) | ✅ |
| user_id | INTEGER |  |
| title | TEXT |  |
| message_count | INTEGER |  |
| created_at | TIMESTAMP |  |
| updated_at | TIMESTAMP |  |
| session_type | TEXT |  |
| artist_id | INTEGER |  |

### collaborator_requests（0 行）

馆藏协作者邀请（from→to 用户，status 状态）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| library_id | INTEGER |  |
| from_user_id | INTEGER |  |
| to_user_id | INTEGER |  |
| status | TEXT |  |
| message | TEXT |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |

### composition_feedback（0 行）

起承转合构图报告的用户评分反馈。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| task_id | VARCHAR(64) |  |
| rating | INTEGER |  |
| comments | TEXT |  |
| client_id | VARCHAR(128) |  |
| created_at | DATETIME |  |

### composition_jobs（12 行）

起承转合构图分析任务：进度/阶段文案/ETA + report_json_path、pdf_path、overlay_heatmap_url 产物路径（服务器 /opt 下绝对路径，已归一为 / 分隔）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(64) | ✅ |
| status | VARCHAR(32) |  |
| progress | INTEGER |  |
| stage | VARCHAR(64) |  |
| stage_text | VARCHAR(64) |  |
| message | VARCHAR(255) |  |
| eta_seconds | INTEGER |  |
| eta_confidence | FLOAT |  |
| queue_eta_seconds | INTEGER |  |
| celery_task_id | VARCHAR(128) |  |
| upload_path | VARCHAR(512) |  |
| original_url | VARCHAR(512) |  |
| report_json_path | VARCHAR(512) |  |
| pdf_path | VARCHAR(512) |  |
| overlay_heatmap_url | VARCHAR(512) |  |
| error_code | VARCHAR(64) |  |
| error_message | TEXT |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |

### library_collaborators（0 行）

馆藏协作者关系（role: editor/viewer）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| library_id | INTEGER |  |
| user_id | INTEGER |  |
| role | VARCHAR(20) |  |
| added_at | DATETIME |  |

### literature_references（0 行）

作品文献引用（预留）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artwork_id | INTEGER |  |
| reference_type | TEXT |  |
| title | TEXT |  |
| author | TEXT |  |
| year | INTEGER |  |
| publisher | TEXT |  |
| page | TEXT |  |
| notes | TEXT |  |
| created_at | DATETIME |  |

### notifications（7 行）

站内通知（type/title/body + reference 指向对象）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| user_id | INTEGER |  |
| type | VARCHAR(30) |  |
| title | VARCHAR(255) |  |
| body | TEXT |  |
| reference_type | VARCHAR(30) |  |
| reference_id | INTEGER |  |
| is_read | INTEGER |  |
| created_at | DATETIME |  |

### recognition_logs（1 行）

碑帖单字识别日志（similarity_score、top_matches JSON）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| user_id | INTEGER |  |
| uploaded_image_path | VARCHAR(255) |  |
| recognized_character | VARCHAR(10) |  |
| matched_stele_id | INTEGER |  |
| similarity_score | FLOAT |  |
| top_matches | JSON |  |
| processing_time_ms | INTEGER |  |
| created_at | DATETIME |  |

### research_notes（0 行）

用户对作品的研究笔记（visibility 控制公开性）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| user_id | INTEGER |  |
| artwork_id | INTEGER |  |
| content | TEXT |  |
| visibility | TEXT |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |
| title | TEXT |  |

### role_permissions（26 行）

角色权限矩阵（role × permission_key，26 条）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| role | TEXT |  |
| permission_key | TEXT |  |

### seal_images（409 行）

印章图片（path/thumbnail_path/sort_order，同印多版本翻页）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| seal_id | INTEGER |  |
| path | TEXT |  |
| description | TEXT |  |
| sort_order | INTEGER |  |
| created_at | TIMESTAMP |  |
| thumbnail_path | TEXT |  |

### seals（240 行）

印章主表（同名多版本已合并为一行，images JSON 汇总；artist_id 关联艺术家；source 为图录出处）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| name | TEXT |  |
| artist_id | INTEGER |  |
| artist_name | TEXT |  |
| seal_type | TEXT |  |
| images | TEXT |  |
| description | TEXT |  |
| created_at | TEXT |  |
| updated_at | TEXT |  |
| source | TEXT |  |

### site_settings（7 行）

站点设置 KV 表（hidden_artists 等运行时开关；公开 API 会剔除敏感 key，管理端可读全量）。

| 列 | 类型 | PK |
|---|---|---|
| key | TEXT | ✅ |
| value | TEXT |  |
| updated_at | TIMESTAMP |  |

### steles（1 行）

碑帖主表（朝代/书家/风格）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| name | VARCHAR(100) |  |
| dynasty | VARCHAR(50) |  |
| calligrapher | VARCHAR(100) |  |
| style | VARCHAR(50) |  |
| description | TEXT |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |

### subscriptions（0 行）

订阅支付记录（预留）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| user_id | INTEGER |  |
| plan_tier | TEXT |  |
| amount_paid | INTEGER |  |
| currency | TEXT |  |
| started_at | DATETIME |  |
| expires_at | DATETIME |  |
| payment_ref | TEXT |  |
| created_at | DATETIME |  |

### tubi_analyses（816 行）

作品库图片分析核心表（800+ 行）：题跋/画面/空白面积占比、regions 与 heatmap JSON、题跋释文与内容分析、主题/材质/风格标签、标注图与缩略图路径、册页 album_name/album_index、归属（owner_id/library_id/visibility）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| image_id | VARCHAR(100) |  |
| filename | VARCHAR(255) |  |
| filepath | VARCHAR(500) |  |
| title | VARCHAR(255) |  |
| artist | VARCHAR(100) |  |
| year | INTEGER |  |
| period | VARCHAR(50) |  |
| notes | TEXT |  |
| image_width | INTEGER |  |
| image_height | INTEGER |  |
| inscription_percent | FLOAT |  |
| painting_percent | FLOAT |  |
| blank_percent | FLOAT |  |
| regions | JSON |  |
| heatmap_data | JSON |  |
| analysis_note | TEXT |  |
| annotated_image_path | VARCHAR(500) |  |
| status | VARCHAR(20) |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |
| position_analysis | TEXT |  |
| thumbnail_path | VARCHAR(500) |  |
| inscription_content | TEXT |  |
| period_phase | VARCHAR(10) |  |
| char_count | INTEGER |  |
| word_count | INTEGER |  |
| theme_tags | VARCHAR(200) |  |
| content_analysis | TEXT |  |
| inscription_verified | INTEGER |  |
| inscription_verified_at | DATETIME |  |
| seal_content | TEXT |  |
| seal_verified | INTEGER |  |
| seal_verified_at | DATETIME |  |
| inscription_modern | TEXT |  |
| material_tags | TEXT |  |
| error_code | VARCHAR(50) |  |
| artwork_width_cm | REAL |  |
| artwork_height_cm | REAL |  |
| album_name | VARCHAR(200) |  |
| album_index | INTEGER |  |
| tags | TEXT |  |
| is_manual_annotated | INTEGER |  |
| owner_id | INTEGER |  |
| library_id | INTEGER |  |
| visibility | TEXT |  |
| created_by | TEXT |  |
| material | TEXT |  |
| mounting_format | TEXT |  |
| current_location | TEXT |  |
| provenance | TEXT |  |
| style_tags | TEXT |  |
| subject_tags | TEXT |  |
| technique_tags | TEXT |  |
| free_tags | TEXT |  |
| inscription_author | TEXT |  |
| inscription_date | TEXT |  |
| work_type | TEXT |  |
| page_role | VARCHAR(20) |  |
| inscription_en | TEXT |  |

### tubi_jobs（377 行）

作品库分析任务状态机（status: queued/analyzing/analyzed/error + 错误码，按 image_id 关联 tubi_analyses）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| image_id | VARCHAR(100) |  |
| status | VARCHAR(20) |  |
| last_error | VARCHAR(500) |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |
| error_code | VARCHAR(50) |  |
| last_error_detail | TEXT |  |
| mode | VARCHAR(30) |  |

### users（8 行）

用户表（role: reader/editor/admin/super_admin；password_hash 为独立密码体系，uid 为前端用户 ID；禁止在工具/SQL 输出中带出 password_hash、wechat_*、phone、email）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| wechat_openid | TEXT |  |
| wechat_unionid | TEXT |  |
| nickname | TEXT |  |
| avatar_url | TEXT |  |
| email | TEXT |  |
| phone | TEXT |  |
| role | TEXT |  |
| subscription_tier | TEXT |  |
| subscription_expires_at | DATETIME |  |
| storage_used_bytes | INTEGER |  |
| ai_calls_this_month | INTEGER |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |
| password_hash | TEXT |  |
| uid | TEXT |  |
| nickname_changed_at | TIMESTAMP |  |
| score | INTEGER |  |

### work_revisions（3 行）

作品修改历史版本快照（operation_type + 申请人）。

| 列 | 类型 | PK |
|---|---|---|
| id | INTEGER | ✅ |
| artwork_id | INTEGER |  |
| revision_number | INTEGER |  |
| snapshot | TEXT |  |
| change_summary | TEXT |  |
| operation_type | VARCHAR(30) |  |
| approved_by | INTEGER |  |
| submitted_by | INTEGER |  |
| change_request_id | INTEGER |  |
| created_at | DATETIME |  |

## 知识库（knowledge.db） — 10 张表

### chat_messages（0 行）

聊天消息（知识库问答与艺术家问答共用；sources 为引用来源 JSON）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| session_id | VARCHAR(36) |  |
| role | VARCHAR(20) |  |
| content | TEXT |  |
| sources | JSON |  |
| token_index | INTEGER |  |
| created_at | DATETIME |  |

### chat_sessions（2 行）

聊天会话（session_type 区分知识库/艺术家问答；artist_id 关联）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| user_id | INTEGER |  |
| title | VARCHAR(100) |  |
| message_count | INTEGER |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |
| session_type | TEXT |  |
| artist_id | INTEGER |  |

### composition_figures（83 行）

起承转合构图图例（figure_type 分型，score_ref 关联评分，description 说明）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| figure_id | VARCHAR(20) |  |
| figure_type | VARCHAR(20) |  |
| score_ref | INTEGER |  |
| description | TEXT |  |
| source | VARCHAR(20) |  |
| ruleset_version | VARCHAR(20) |  |
| created_at | DATETIME |  |

### composition_rules（202 行）

构图规则库（202 条）：category 起/承/转/合 + 子类、weight 权重、condition 与 quantitative_standard、ruleset_version 版本、is_active 启用位。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| rule_id | VARCHAR(20) |  |
| rule_name | VARCHAR(100) |  |
| condition | TEXT |  |
| quantitative_standard | TEXT |  |
| weight | INTEGER |  |
| category_name | VARCHAR(50) |  |
| category_code | VARCHAR(10) |  |
| subcategory_name | VARCHAR(100) |  |
| reference_figures | JSON |  |
| source | VARCHAR(20) |  |
| ruleset_version | VARCHAR(20) |  |
| is_active | INTEGER |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |

### extracted_images（1298 行）

书内插图抽取结果（bbox/image_hash/vector_id 关联 Qdrant，caption 图注，stored_url 访问路径）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| book_id | VARCHAR(36) |  |
| file_name | VARCHAR(255) |  |
| stored_path | VARCHAR(500) |  |
| stored_url | VARCHAR(500) |  |
| page | INTEGER |  |
| figure_id | VARCHAR(100) |  |
| bbox | JSON |  |
| image_hash | VARCHAR(64) |  |
| vector_id | VARCHAR(100) |  |
| associated_chunks | JSON |  |
| meta_data | JSON |  |
| created_at | DATETIME |  |
| caption | TEXT |  |

### knowledge_tasks（35 行）

知识库入库任务（Celery：解析/切块/向量化各阶段的进度与错误）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| book_id | VARCHAR(36) |  |
| task_type | VARCHAR(50) |  |
| status | VARCHAR(20) |  |
| progress | INTEGER |  |
| stage | VARCHAR(100) |  |
| message | TEXT |  |
| result | JSON |  |
| error_message | TEXT |  |
| celery_task_id | VARCHAR(100) |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |

### pdf_books（35 行）

书目主表（35 本）：PDF/期刊文献，full_md 全文、outline 大纲、document_type/source_type 分类、series_id 丛书、page_offset 页码偏移。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| file_name | VARCHAR(255) |  |
| stored_path | VARCHAR(500) |  |
| stored_url | VARCHAR(500) |  |
| title | VARCHAR(255) |  |
| author | VARCHAR(255) |  |
| total_pages | INTEGER |  |
| status | VARCHAR(20) |  |
| created_at | DATETIME |  |
| updated_at | DATETIME |  |
| full_md | TEXT |  |
| outline | TEXT |  |
| series_id | VARCHAR(36) |  |
| page_offset | INTEGER |  |
| owner_id | INTEGER |  |
| visibility | TEXT |  |
| artist_id | INTEGER |  |
| document_type | TEXT |  |
| journal | TEXT |  |
| publish_year | INTEGER |  |
| doi | TEXT |  |
| abstract | TEXT |  |
| keywords | TEXT |  |
| source_type | TEXT |  |

### search_history（35 行）

知识库检索历史（query/filters/result_count）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| query | VARCHAR(500) |  |
| query_type | VARCHAR(20) |  |
| filters | JSON |  |
| result_count | INTEGER |  |
| created_at | DATETIME |  |

### summary_cache（10 行）

AI 问答摘要缓存（query_key 去重，sources 引用，hit_count 命中计数）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| query_key | VARCHAR(500) |  |
| query_original | VARCHAR(500) |  |
| answer | TEXT |  |
| confidence | INTEGER |  |
| sources | JSON |  |
| created_at | DATETIME |  |
| hit_count | INTEGER |  |
| extra_data | TEXT |  |

### text_chunks（3186 行）

RAG 文本块（3186 条）：book_id+chunk_index 定位，content 正文，vector_id 必须与 Qdrant 集合 id 一致（重建向量后必须同步，详见 SKILL.md）。

| 列 | 类型 | PK |
|---|---|---|
| id | VARCHAR(36) | ✅ |
| book_id | VARCHAR(36) |  |
| chunk_index | INTEGER |  |
| chapter_title | VARCHAR(255) |  |
| page_start | INTEGER |  |
| page_end | INTEGER |  |
| content | TEXT |  |
| content_hash | VARCHAR(64) |  |
| vector_id | VARCHAR(100) |  |
| associated_images | JSON |  |
| meta_data | JSON |  |
| created_at | DATETIME |  |
| bbox | JSON |  |
| owner_id | INTEGER |  |
| visibility | TEXT |  |
