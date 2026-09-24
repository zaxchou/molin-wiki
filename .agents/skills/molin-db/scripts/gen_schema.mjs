#!/usr/bin/env node
/**
 * 生成 references/schema.md：两个库全部表的列定义、行数快照与领域注释。
 * 只读打开（readOnly: true），不写库；表结构变更后重跑本脚本。
 * 用法：node .agents/skills/molin-db/scripts/gen_schema.mjs
 */
import { DatabaseSync } from 'node:sqlite'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '../../../..')
const OUT = path.join(__dirname, '..', 'references', 'schema.md')

const DBS = [
  { rel: 'backend/data/calligraphy.db', title: 'wiki 主库（calligraphy.db）' },
  { rel: 'backend/data/knowledge.db', title: '知识库（knowledge.db）' },
]

// 表级领域注释（手写；gen 时保留）
const DESC = {
  // ── calligraphy.db ──
  ai_text_translations: '题跋释文中英对照翻译（zh/en，source 标注来源）。',
  alembic_version: 'Alembic 数据库迁移版本标记。',
  analysis_divergence: '主题/情感判定分歧记录（词典结果 vs LLM 复判，resolved 标记是否处理）。',
  analysis_summary: '按艺术家的情感/主题分析汇总报告（report_json 含明细）。',
  api_usage_logs: 'LLM/API 调用计量日志。',
  art_schools: '画派流派资料表（预留，暂无数据）。',
  artist_change_requests: '艺术家资料修改申请（old/new 值 + 审核状态流）。',
  artist_claims: '用户认领艺术家申请（apply_reason → 审核）。',
  artist_rules: '情绪引擎的艺术家基线：emotion_baseline、生平阶段、主题/情感期望分布、印章规则。',
  artist_stats_cache: '艺术家统计缓存（stats_data JSON，避免重复聚合）。',
  artists: '艺术家主表（约 473 位）。富文本字段（biography/chronology/relations 等）多为 JSON 或 Markdown；enabled/verified/featured 控制展示；dynasty 是常用过滤维度。',
  artwork_artists: '作品↔艺术家多对多关联（预留）。',
  artwork_libraries: '作品馆藏集/分册（visibility: public/private，owner_id 归属，artwork_count 缓存计数）。',
  auction_records: '拍卖记录（预留）。',
  change_requests: '作品字段修改申请（含 draft_data 草稿与 base_revision 冲突控制）。',
  characters: '碑帖单字（字形 feature_vector JSON、bounding_box、图片路径）。',
  chat_messages: '聊天消息（知识库问答与艺术家问答共用；sources 为引用来源 JSON）。',
  chat_sessions: '聊天会话（session_type 区分知识库/艺术家问答；artist_id 关联）。',
  collaborator_requests: '馆藏协作者邀请（from→to 用户，status 状态）。',
  composition_feedback: '起承转合构图报告的用户评分反馈。',
  composition_jobs: '起承转合构图分析任务：进度/阶段文案/ETA + report_json_path、pdf_path、overlay_heatmap_url 产物路径（服务器 /opt 下绝对路径，已归一为 / 分隔）。',
  library_collaborators: '馆藏协作者关系（role: editor/viewer）。',
  literature_references: '作品文献引用（预留）。',
  notifications: '站内通知（type/title/body + reference 指向对象）。',
  recognition_logs: '碑帖单字识别日志（similarity_score、top_matches JSON）。',
  research_notes: '用户对作品的研究笔记（visibility 控制公开性）。',
  role_permissions: '角色权限矩阵（role × permission_key，26 条）。',
  seal_images: '印章图片（path/thumbnail_path/sort_order，同印多版本翻页）。',
  seals: '印章主表（同名多版本已合并为一行，images JSON 汇总；artist_id 关联艺术家；source 为图录出处）。',
  site_settings: '站点设置 KV 表（hidden_artists 等运行时开关；公开 API 会剔除敏感 key，管理端可读全量）。',
  steles: '碑帖主表（朝代/书家/风格）。',
  subscriptions: '订阅支付记录（预留）。',
  tubi_analyses: '作品库图片分析核心表（800+ 行）：题跋/画面/空白面积占比、regions 与 heatmap JSON、题跋释文与内容分析、主题/材质/风格标签、标注图与缩略图路径、册页 album_name/album_index、归属（owner_id/library_id/visibility）。',
  tubi_jobs: '作品库分析任务状态机（status: queued/analyzing/analyzed/error + 错误码，按 image_id 关联 tubi_analyses）。',
  users: '用户表（role: reader/editor/admin/super_admin；password_hash 为独立密码体系，uid 为前端用户 ID；禁止在工具/SQL 输出中带出 password_hash、wechat_*、phone、email）。',
  work_revisions: '作品修改历史版本快照（operation_type + 申请人）。',
  // ── knowledge.db ──
  composition_figures: '起承转合构图图例（figure_type 分型，score_ref 关联评分，description 说明）。',
  composition_rules: '构图规则库（202 条）：category 起/承/转/合 + 子类、weight 权重、condition 与 quantitative_standard、ruleset_version 版本、is_active 启用位。',
  extracted_images: '书内插图抽取结果（bbox/image_hash/vector_id 关联 Qdrant，caption 图注，stored_url 访问路径）。',
  knowledge_tasks: '知识库入库任务（Celery：解析/切块/向量化各阶段的进度与错误）。',
  pdf_books: '书目主表（35 本）：PDF/期刊文献，full_md 全文、outline 大纲、document_type/source_type 分类、series_id 丛书、page_offset 页码偏移。',
  search_history: '知识库检索历史（query/filters/result_count）。',
  summary_cache: 'AI 问答摘要缓存（query_key 去重，sources 引用，hit_count 命中计数）。',
  text_chunks: 'RAG 文本块（3186 条）：book_id+chunk_index 定位，content 正文，vector_id 必须与 Qdrant 集合 id 一致（重建向量后必须同步，详见 SKILL.md）。',
}

let out = []
out.push('# molin-wiki 数据库 schema（自动生成）', '')
out.push('> 由 `scripts/gen_schema.mjs` 生成，请勿手改；表结构变更后重跑。行数为生成时快照。')
out.push('> 生成时间：' + new Date().toISOString(), '')

for (const db of DBS) {
  const abs = path.join(REPO_ROOT, db.rel)
  const con = new DatabaseSync(abs, { readOnly: true })
  const tables = con.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").all()
  out.push('## ' + db.title + ' — ' + tables.length + ' 张表', '')
  for (const { name } of tables) {
    const n = con.prepare('SELECT COUNT(*) AS c FROM "' + name + '"').get().c
    const cols = con.prepare('PRAGMA table_info("' + name + '")').all()
    out.push('### ' + name + '（' + n + ' 行）', '')
    if (DESC[name]) out.push(DESC[name], '')
    out.push('| 列 | 类型 | PK |', '|---|---|---|')
    for (const c of cols) {
      out.push('| ' + c.name + ' | ' + (c.type || '') + ' | ' + (c.pk ? '✅' : '') + ' |')
    }
    out.push('')
  }
  con.close()
}

fs.mkdirSync(path.dirname(OUT), { recursive: true })
fs.writeFileSync(OUT, out.join('\n'), 'utf8')
console.log('wrote ' + OUT)
