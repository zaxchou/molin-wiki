---
name: molin-db
description: |
  molin-wiki 数据库只读 MCP + schema 上下文：dbhub 双源（wiki 主库 / knowledge 知识库），
  只读自由 SQL、表结构自省、15 个领域查询工具；附逐表 schema 文档与 60 项断言验证探针。
  供其他 agent 做二次开发时快速取用数据库上下文。
  触发词：数据库、schema、SQL、表结构、查库、dbhub、MCP、数据上下文。
---

# molin-db — Wiki 数据库只读 MCP

把 molin-wiki 的两个 SQLite 库以**强制只读**方式暴露成 MCP，供任意 agent 秒级拿到
表结构、真实数据与领域查询能力。零写风险：连接级 readOnly + `PRAGMA query_only` +
语句分类器三层拦截，探针里 9 种写攻击（UPDATE/DELETE/INSERT/DROP/CREATE/ATTACH/多语句/PRAGMA 写/select-into）全部验证过会被拒。

## 组成

| 文件 | 作用 |
|---|---|
| `dbhub.wiki.toml` | wiki 主库（`backend/data/calligraphy.db`，36 表）：只读 SQL + 自省 + 9 个领域工具 |
| `dbhub.knowledge.toml` | 知识库（`backend/data/knowledge.db`，10 表）：只读 SQL + 自省 + 6 个领域工具 |
| `references/schema.md` | 逐表 schema：列/类型/PK/行数快照 + 每表领域注释（**自动生成，勿手改**） |
| `scripts/gen_schema.mjs` | 重新生成 schema.md（只读打开库） |
| `scripts/mcp_probe.mjs` | 协议级自验证：握手、只读拦截、领域工具、敏感列泄漏，共 60 项断言 |

## 接入（MCP 客户端）

**已内置**：仓库根 `.mcp.json` 注册了 `molin-db` 与 `molin-knowledge` 两个条目，
Claude Code / Cursor 等读取 `.mcp.json` 的客户端开箱即用。其他客户端等价配置：

```json
{
  "mcpServers": {
    "molin-db": {
      "command": "npx",
      "args": ["--yes", "@bytebase/dbhub@1.3.1", "--transport", "stdio",
               "--config", "<仓库根>/.agents/skills/molin-db/dbhub.wiki.toml"]
    },
    "molin-knowledge": {
      "command": "npx",
      "args": ["--yes", "@bytebase/dbhub@1.3.1", "--transport", "stdio",
               "--config", "<仓库根>/.agents/skills/molin-db/dbhub.knowledge.toml"]
    }
  }
}
```

前置：Node ≥ 22.5（dbhub 依赖内置 `node:sqlite`）。首次运行 npx 会拉包，约几秒。
换机器/改克隆路径时：改两份 toml 里的 DSN 绝对路径 + 上面两处 `--config` 路径。

## 工具清单

### molin-db（wiki 主库）

| 工具 | 说明 |
|---|---|
| `execute_sql` | 自由 SQL。**强制只读**，max_rows=500；入参名 `sql` |
| `search_objects` | 表结构自省。`object_type` 是枚举：`schema/table/view/column/procedure/function/index` |
| `list_artists` | 艺术家列表，`dynasty` 子串过滤 + `limit`，附题跋/印章计数 |
| `get_artist` | 按 `name` 精确取单个艺术家完整档案 + 统计 |
| `list_tiba_analyses` | 作品库分析列表（`artist` 子串 / `status` / `limit`），按 id 倒序 |
| `get_tiba_analysis` | 按 `image_id` 取完整分析（释文、内容分析、面积占比、标注图路径） |
| `list_seals` | 印章列表（`artist` 子串），附图片数 |
| `list_libraries` | 馆藏集/分册（含 visibility、作品数） |
| `list_composition_jobs` | 起承转合构图任务（状态/进度/产物路径） |
| `list_users` | 用户概览——**只返回安全列**（nickname/role/uid 等，无 password_hash/openid/phone/email） |
| `get_site_settings` | 站点设置 KV 全量（含 hidden_artists） |

### molin-knowledge（知识库）

| 工具 | 说明 |
|---|---|
| `execute_sql` | 自由 SQL，强制只读，max_rows=500 |
| `search_objects` | 表结构自省（同上枚举） |
| `list_pdf_books` | 书目列表（类型过滤 + 每本 chunk 计数） |
| `get_pdf_book` | 按 `id` 取书目详情 + 文本块/插图计数 |
| `search_text_chunks` | 正文关键词检索（书名/章节/内容 LIKE）。**`query`/`query2`/`query3` 传同一个值**（SQLite 位置参数限制） |
| `list_composition_rules` | 构图规则（分类子串 + `active_only` 0/1 + limit） |
| `list_composition_figures` | 构图图例（类型子串过滤） |
| `list_extracted_images` | 抽取插图（可按 `book_id` 过滤；`book_id`/`book_id2` 传同一值） |

## 领域地图（详见 references/schema.md）

- **艺术家**：`artists`（主表 473 行）、`artist_rules`（情绪引擎基线）、`artist_stats_cache`、`artist_claims` / `artist_change_requests`（认领与修改审核流）
- **作品库（题跋分析）**：`tubi_analyses`（核心，816 行：面积占比/释文/标签/标注图）、`tubi_jobs`（任务状态机）、`ai_text_translations`、`analysis_summary` / `analysis_divergence`
- **印章 / 碑帖**：`seals` + `seal_images`（同名多版本合并，sort_order 翻页）、`steles`、`characters`（单字特征）、`recognition_logs`
- **馆藏与编辑流**：`artwork_libraries`、`library_collaborators`、`change_requests`、`work_revisions`、`research_notes`（visibility 控制公开性）
- **起承转合**：任务在主库 `composition_jobs` / `composition_feedback`；规则与图例在 knowledge 库 `composition_rules`（202 条）/ `composition_figures`
- **用户权限**：`users`（role: reader/editor/admin/super_admin）、`role_permissions`（26 条矩阵）
- **设置**：`site_settings`（KV）
- **知识库 RAG**：`pdf_books`（35 本）、`text_chunks`（3186 块）、`extracted_images`、`knowledge_tasks`、`summary_cache`
- **聊天**：两库各有一套 `chat_sessions` / `chat_messages`（session_type 区分知识库问答/艺术家问答）

## 约定与坑（二次开发必读）

1. **artist 隐藏开关**：`site_settings.hidden_artists` 是 JSON 数组（如 `["刘海勇"]`）。公开 API 会剔除这个 key 且 artists 列表/朝代/统计都会过滤；**库里数据行原样存在**，MCP 直接 SQL 仍能查到——这是预期行为（隐藏≠删除）。
2. **`text_chunks.vector_id` ↔ Qdrant**：重建 Qdrant 后两者会漂移，必须按 AGENTS.md 的同步流程回写，否则搜索返回 0（后端有孤立向量回退兜底）。
3. **`users` 敏感列**：`password_hash`、`wechat_*`、`phone`、`email` 永远不要 SELECT 出来给 agent/日志；用 `list_users` 工具。探针对此有专项断言。
4. **产物路径**：`composition_jobs.report_json_path` 等是服务器 `/opt/molin-wiki/...` 绝对路径（已归一为 `/` 分隔），本地不一定存在。
5. **只暴露两个库**：`calligraphy_new.db`、`calligraphy_utf8.db` 是历史遗留快照，`molin_wiki.db` / `app/data/calligraphy.db` 是 0 字节占位——都不要读不要用。
6. **本地即事实源**：`backend/data/*.db` 为源，`deploy.sh` SCP 同步到服务器；MCP 读的就是最新数据。
7. **行数上限**：自由 SQL 结果最多 500 行（TOML 里可调）；SQLite 不支持 query_timeout，超大表查询请自己带 LIMIT。
8. **改表结构后的义务**：重跑 `scripts/gen_schema.mjs` 更新 schema.md，再跑 `scripts/mcp_probe.mjs` 确认全绿，两者一起提交。

## 验证

```bash
# 协议 + 只读安全 + 领域工具，60 项断言，全绿退出码 0
node .agents/skills/molin-db/scripts/mcp_probe.mjs

# 表结构变更后重新生成 schema 文档
node .agents/skills/molin-db/scripts/gen_schema.mjs
```

验证过的行为快照（2026-09-25，dbhub@1.3.1）：9 种写攻击全部被拒；max_rows=500 生效；
`list_artists(dynasty=明)` 只返回明代行；`list_users` 无任何敏感列；两库自省正常。
