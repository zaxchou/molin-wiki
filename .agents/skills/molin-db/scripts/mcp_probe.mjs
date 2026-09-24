#!/usr/bin/env node
/**
 * molin-db MCP 自验证探针
 *
 * 对 dbhub 的两个 stdio MCP server（wiki 主库 / knowledge 知识库）做协议级验证：
 *   1. initialize 握手 + tools/list（含服务器版本）
 *   2. 只读安全：UPDATE/DELETE/INSERT/DROP/CREATE/ATTACH/多语句/PRAGMA 写 全部必须被拒
 *   3. max_rows 行数上限生效
 *   4. 每个领域工具 happy-path 可调用且返回预期内容（基于真实行数据断言，防"空转通过"）
 *   5. list_users 绝不泄漏 password_hash / wechat_openid / phone / email 等敏感列
 *
 * 用法：node .agents/skills/molin-db/scripts/mcp_probe.mjs
 * 退出码：0 = 全部通过；1 = 有失败项
 */
import { spawn } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const SKILL_DIR = path.resolve(__dirname, '..')
// scripts → molin-db → skills → .agents → 仓库根
const REPO_ROOT = path.resolve(__dirname, '../../../..')
const DBHUB_VERSION = '1.3.1'

const results = []
function check(name, cond, detail = '') {
  results.push({ name, ok: !!cond, detail })
  console.log((cond ? 'PASS  ' : 'FAIL  ') + name + (cond ? '' : '  :: ' + String(detail).slice(0, 600)))
}

// ── 极简 MCP stdio 客户端（newline-delimited JSON-RPC 2.0） ──
class McpClient {
  constructor(label, args, timeoutFirstMs = 120000) {
    this.label = label
    this.args = args
    this.timeoutFirstMs = timeoutFirstMs
    this.nextId = 1
    this.pending = new Map()
    this.stderr = ''
    this.buffer = ''
  }

  start() {
    if (process.platform === 'win32') {
      // shell 模式下把参数拼成单条命令行，避免 DEP0190 警告
      const cmdline = 'npx ' + this.args.map((a) => '"' + a + '"').join(' ')
      this.child = spawn(cmdline, { cwd: REPO_ROOT, shell: true, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] })
    } else {
      this.child = spawn('npx', this.args, { cwd: REPO_ROOT, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] })
    }
    this.child.stdout.setEncoding('utf8')
    this.child.stdout.on('data', (chunk) => this._onData(chunk))
    this.child.stderr.setEncoding('utf8')
    this.child.stderr.on('data', (chunk) => { this.stderr += chunk })
    this.child.on('error', (err) => {
      this.stderr += '\nSPAWN ERROR: ' + err.message
      for (const [, p] of this.pending) p.reject(err)
      this.pending.clear()
    })
    this.child.on('close', (code, signal) => {
      for (const [, p] of this.pending) {
        p.reject(new Error(`server exited (code=${code}, signal=${signal})\nstderr:\n${this.stderr.slice(-2000)}`))
      }
      this.pending.clear()
    })
  }

  _onData(chunk) {
    this.buffer += chunk
    let idx
    while ((idx = this.buffer.indexOf('\n')) >= 0) {
      const line = this.buffer.slice(0, idx).trim()
      this.buffer = this.buffer.slice(idx + 1)
      if (!line) continue
      let msg
      try { msg = JSON.parse(line) } catch { continue }
      if (msg.id !== undefined && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        if (msg.error) p.reject(new Error(JSON.stringify(msg.error).slice(0, 1500)))
        else p.resolve(msg.result)
      }
    }
  }

  request(method, params, timeoutMs = 30000) {
    const id = this.nextId++
    const payload = { jsonrpc: '2.0', id, method, params }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`timeout ${timeoutMs}ms waiting for ${method}\nstderr:\n${this.stderr.slice(-2000)}`))
      }, timeoutMs)
      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v) },
        reject: (e) => { clearTimeout(timer); reject(e) },
      })
      this.child.stdin.write(JSON.stringify(payload) + '\n')
    })
  }

  notify(method, params = {}) {
    this.child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n')
  }

  async initialize() {
    const res = await this.request('initialize', {
      protocolVersion: '2025-06-18',
      capabilities: {},
      clientInfo: { name: 'molin-db-probe', version: '1.0.0' },
    }, this.timeoutFirstMs)
    this.notify('notifications/initialized')
    return res
  }

  async listTools() {
    const res = await this.request('tools/list', {})
    return res.tools || []
  }

  async callTool(name, args, timeoutMs = 30000) {
    return this.request('tools/call', { name, arguments: args }, timeoutMs)
  }

  close() {
    try {
      if (this.child && !this.child.killed) {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/PID', String(this.child.pid), '/T', '/F'], { windowsHide: true })
        } else {
          this.child.kill('SIGTERM')
        }
      }
    } catch { /* best effort */ }
  }
}

// ── 结果解析工具 ──
function dump(res) {
  try { return JSON.stringify(res) } catch { return String(res) }
}
function toolText(res) {
  if (!res || !Array.isArray(res.content)) return ''
  return res.content.map((c) => (c && c.text) ? c.text : '').join('\n')
}
/** 解析 dbhub 工具返回文本里的行数组：{success,data:{statements:[{sql,rows...}]}} */
function toolRows(res) {
  const text = toolText(res)
  let obj
  try { obj = JSON.parse(text) } catch { return null }
  const st = obj && obj.data && Array.isArray(obj.data.statements) ? obj.data.statements[0] : null
  if (!st) return null
  const rows = st.rows
  if (Array.isArray(rows)) {
    if (rows.length === 0) return []
    if (Array.isArray(rows[0]) && Array.isArray(st.columns)) {
      const cols = st.columns.map((c) => (typeof c === 'string' ? c : (c && (c.name || c.column)) || String(c)))
      return rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])))
    }
    if (typeof rows[0] === 'object') return rows
  }
  return null
}
/** 从输入 schema 构造合法参数：必填项按类型/枚举填默认值，可选串型项覆盖为 overrides */
function buildArgs(tools, toolName, overrides = {}) {
  const t = tools.find((x) => x.name === toolName)
  const props = (t && t.inputSchema && t.inputSchema.properties) || {}
  const required = (t && t.inputSchema && t.inputSchema.required) || Object.keys(props)
  const args = {}
  for (const key of required) {
    if (key in overrides) { args[key] = overrides[key]; continue }
    const p = props[key] || {}
    if (Array.isArray(p.enum)) args[key] = p.enum.includes('table') ? 'table' : p.enum[0]
    else if (p.type === 'integer' || p.type === 'number') args[key] = p.default !== undefined ? p.default : 10
    else if (p.type === 'boolean') args[key] = p.default !== undefined ? p.default : false
    else args[key] = p.default !== undefined ? p.default : ''
  }
  return args
}
function uuidIn(text) {
  const m = text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)
  return m ? m[0] : null
}
function countOccurrences(text, sub) {
  let n = 0, i = 0
  while ((i = text.indexOf(sub, i)) >= 0) { n++; i += sub.length }
  return n
}

const ATTACKS = [
  ['UPDATE', 'UPDATE users SET role = role WHERE 1 = 1'],
  ['DELETE', 'DELETE FROM api_usage_logs WHERE 0'],
  ['INSERT', "INSERT INTO site_settings (key, value) VALUES ('probe_attack', 'x')"],
  ['DROP', 'DROP TABLE analysis_divergence'],
  ['CREATE', 'CREATE TABLE probe_canary (x INTEGER)'],
  ['ATTACH', "ATTACH DATABASE ':memory:' AS probe_attach"],
  ['multi-statement', "SELECT 1; DELETE FROM users"],
  ['pragma-write', 'PRAGMA query_only = OFF'],
  ['select-into', 'CREATE TABLE probe_canary2 AS SELECT 1 AS x'],
]

async function verifyServer(spec) {
  console.log('\n===== ' + spec.label + ' =====')
  const client = new McpClient(spec.label, ['--yes', '@bytebase/dbhub@' + DBHUB_VERSION, '--transport', 'stdio', '--config', spec.config])
  client.start()
  try {
    const init = await client.initialize()
    const ver = (init.serverInfo && (init.serverInfo.name + '@' + init.serverInfo.version)) || 'unknown'
    check(spec.label + ': initialize 握手（' + ver + '）', !!init && !!init.protocolVersion, dump(init).slice(0, 400))

    const tools = await client.listTools()
    const names = tools.map((t) => t.name)
    check(spec.label + ': tools/list 含内置 execute_sql + search_objects', names.includes('execute_sql') && names.includes('search_objects'), 'got: ' + names.join(', '))
    for (const want of spec.customTools) {
      check(spec.label + ': 领域工具 ' + want, names.includes(want), 'missing; got: ' + names.join(', '))
    }

    const sqlArg = buildSqlArgName(tools, 'execute_sql')

    // ── 只读安全 ──
    for (const [kind, sql] of ATTACKS) {
      let res, err = null
      try { res = await client.callTool('execute_sql', { [sqlArg]: sql }) } catch (e) { err = e }
      const rejected = err !== null || (res && res.isError === true)
      check(spec.label + ': 只读拦截 ' + kind, rejected, (err ? String(err.message) : 'NOT rejected, response: ' + dump(res).slice(0, 500)))
    }
    const ok = await client.callTool('execute_sql', { [sqlArg]: spec.sanitySql })
    check(spec.label + ': execute_sql 正常 SELECT 可用', !ok.isError && toolText(ok).includes(spec.sanityToken), dump(ok).slice(0, 400))

    // ── max_rows 上限 ──
    if (spec.maxRowsCheck) {
      const big = await client.callTool('execute_sql', { [sqlArg]: spec.maxRowsCheck.sql })
      const bigTxt = toolText(big)
      const rows = toolRows(big)
      const n = rows ? rows.length : countOccurrences(bigTxt, spec.maxRowsCheck.needle)
      check(spec.label + ': max_rows 生效（返回 ' + n + ' 行 ≤ 500）',
        !big.isError && n > 0 && n <= 500,
        (rows === null ? 'rows 解析失败(按 needle 计数) ' : '') + 'n=' + n + ' resp=' + bigTxt.slice(0, 300))
    }

    // ── search_objects（object_type 枚举 + 可选过滤串） ──
    const t = tools.find((x) => x.name === 'search_objects')
    const props = (t && t.inputSchema && t.inputSchema.properties) || {}
    const strKey = Object.keys(props).find((k) => k !== 'object_type' && props[k] && props[k].type === 'string')
    const soArgs = { object_type: 'table' }
    if (strKey) soArgs[strKey] = spec.searchObjectsToken
    const so = await client.callTool('search_objects', soArgs)
    check(spec.label + ': search_objects(table) 自省到 ' + spec.searchObjectsToken,
      !so.isError && toolText(so).includes(spec.searchObjectsToken),
      dump(so).slice(0, 400))

    // ── 领域工具（label 传字符串） ──
    await spec.customChecks(client, tools, spec.label)
    return client
  } catch (e) {
    check(spec.label + ': 会话异常', false, String((e && e.message) || e) + '\nstderr:\n' + client.stderr.slice(-800))
    return client
  }
}

function buildSqlArgName(tools, toolName) {
  const t = tools.find((x) => x.name === toolName)
  const props = (t && t.inputSchema && t.inputSchema.properties) || {}
  for (const c of ['sql', 'query', 'statement']) if (props[c]) return c
  return Object.keys(props)[0] || 'sql'
}

// ── wiki server 断言 ──
const wikiSpec = {
  label: 'molin-db',
  config: path.join(SKILL_DIR, 'dbhub.wiki.toml').replace(/\\/g, '/'),
  customTools: ['list_artists', 'get_artist', 'list_tiba_analyses', 'get_tiba_analysis', 'list_seals', 'list_libraries', 'list_composition_jobs', 'list_users', 'get_site_settings'],
  sanitySql: "SELECT 'MCP_PROBE_OK' AS marker",
  sanityToken: 'MCP_PROBE_OK',
  maxRowsCheck: null,
  searchObjectsToken: 'artists',
  async customChecks(client, tools, label) {
    // list_artists：朝代过滤 + limit 都必须在真实行上生效
    const rArtists = await client.callTool('list_artists', { dynasty: '明', limit: 5 })
    const aRows = toolRows(rArtists)
    if (aRows) {
      check(label + ': list_artists(dynasty=明) 返回 1~5 行且每行都是明代', !rArtists.isError && aRows.length >= 1 && aRows.length <= 5 && aRows.every((row) => String(row.dynasty || '').includes('明')), 'rows=' + JSON.stringify(aRows).slice(0, 300))
    } else {
      const txt = toolText(rArtists)
      check(label + ': list_artists(dynasty=明)（行解析降级）', !rArtists.isError && txt.includes('明'), txt.slice(0, 300))
    }

    const rArtist = await client.callTool('get_artist', { name: '徐渭' })
    const gRows = toolRows(rArtist)
    check(label + ': get_artist(徐渭) 命中单行', !rArtist.isError && Array.isArray(gRows) && gRows.length === 1 && gRows[0].name === '徐渭',
      (gRows ? JSON.stringify(gRows).slice(0, 300) : toolText(rArtist).slice(0, 300)))

    const rList = await client.callTool('list_tiba_analyses', { artist: '', status: '%', limit: 3 })
    const lRows = toolRows(rList)
    let imgId = null
    if (Array.isArray(lRows) && lRows.length >= 1) {
      imgId = lRows[0].image_id || null
      check(label + ': list_tiba_analyses 返回 ≤3 行', lRows.length <= 3, 'rows=' + lRows.length)
    }
    if (!imgId) imgId = (toolText(rList).match(/"image_id":\s*"([^"]+)"/) || [])[1]
    if (imgId) {
      const rTiba = await client.callTool('get_tiba_analysis', { image_id: imgId })
      const tRows = toolRows(rTiba)
      check(label + ': get_tiba_analysis(' + String(imgId).slice(0, 24) + '…) 命中单行',
        !rTiba.isError && Array.isArray(tRows) && tRows.length === 1 && tRows[0].image_id === imgId,
        (tRows ? JSON.stringify(tRows).slice(0, 300) : toolText(rTiba).slice(0, 300)))
    } else {
      check(label + ': get_tiba_analysis（提取 image_id）', false, 'list_tiba_analyses 未返回 image_id: ' + toolText(rList).slice(0, 400))
    }

    const rSeals = await client.callTool('list_seals', { artist: '', limit: 5 })
    const sRows = toolRows(rSeals)
    check(label + ': list_seals 返回 1~5 行含 name/artist_name', !rSeals.isError && Array.isArray(sRows) && sRows.length >= 1 && sRows.length <= 5 && 'name' in sRows[0] && 'artist_name' in sRows[0],
      (sRows ? JSON.stringify(sRows).slice(0, 300) : toolText(rSeals).slice(0, 300)))

    const rLibs = await client.callTool('list_libraries', { limit: 5 })
    const liRows = toolRows(rLibs)
    check(label + ': list_libraries 返回行含 name/visibility', !rLibs.isError && Array.isArray(liRows) && liRows.length >= 1 && 'name' in liRows[0] && 'visibility' in liRows[0],
      (liRows ? JSON.stringify(liRows).slice(0, 300) : toolText(rLibs).slice(0, 300)))

    const rJobs = await client.callTool('list_composition_jobs', { status: '', limit: 5 })
    const jRows = toolRows(rJobs)
    check(label + ': list_composition_jobs 返回行含 status/progress', !rJobs.isError && Array.isArray(jRows) && jRows.length >= 1 && 'status' in jRows[0] && 'progress' in jRows[0],
      (jRows ? JSON.stringify(jRows).slice(0, 300) : toolText(rJobs).slice(0, 300)))

    // list_users：安全列
    const rUsers = await client.callTool('list_users', { limit: 10 })
    const uTxt = toolText(rUsers)
    const uRows = toolRows(rUsers)
    check(label + ': list_users 返回 nickname/role 且 ≥1 行', !rUsers.isError && Array.isArray(uRows) && uRows.length >= 1 && 'nickname' in uRows[0] && 'role' in uRows[0],
      (uRows ? JSON.stringify(uRows).slice(0, 300) : uTxt.slice(0, 300)))
    check(label + ': list_users 不泄漏 password_hash', !uTxt.includes('password_hash'), 'LEAKED')
    check(label + ': list_users 不泄漏 wechat_openid', !uTxt.includes('wechat_openid'), 'LEAKED')
    check(label + ': list_users 不泄漏 phone/email 列', !uTxt.includes('"phone"') && !uTxt.includes('"email"'), 'LEAKED')

    const rSet = await client.callTool('get_site_settings', {})
    const setRows = toolRows(rSet)
    check(label + ': get_site_settings 返回 KV 行', !rSet.isError && Array.isArray(setRows) && setRows.length >= 1 && 'key' in setRows[0] && 'value' in setRows[0],
      (setRows ? JSON.stringify(setRows).slice(0, 300) : toolText(rSet).slice(0, 300)))
  },
}

// ── knowledge server 断言 ──
const knowledgeSpec = {
  label: 'molin-knowledge',
  config: path.join(SKILL_DIR, 'dbhub.knowledge.toml').replace(/\\/g, '/'),
  customTools: ['list_pdf_books', 'get_pdf_book', 'search_text_chunks', 'list_composition_rules', 'list_composition_figures', 'list_extracted_images'],
  sanitySql: "SELECT 'KNOW_PROBE_OK' AS marker",
  sanityToken: 'KNOW_PROBE_OK',
  maxRowsCheck: { sql: 'SELECT id FROM text_chunks', needle: '"id":' },
  searchObjectsToken: 'text_chunks',
  async customChecks(client, tools, label) {
    const rBooks = await client.callTool('list_pdf_books', { document_type: '%', limit: 5 })
    const bRows = toolRows(rBooks)
    check(label + ': list_pdf_books 返回 1~5 行含 title/status', !rBooks.isError && Array.isArray(bRows) && bRows.length >= 1 && bRows.length <= 5 && 'title' in bRows[0] && 'status' in bRows[0],
      (bRows ? JSON.stringify(bRows).slice(0, 300) : toolText(rBooks).slice(0, 300)))
    const bookId = (Array.isArray(bRows) && bRows[0] && bRows[0].id) || uuidIn(toolText(rBooks))
    if (bookId) {
      const rBook = await client.callTool('get_pdf_book', { id: bookId })
      const kRows = toolRows(rBook)
      check(label + ': get_pdf_book(' + String(bookId).slice(0, 8) + '…) 命中单行含 chunk_count',
        !rBook.isError && Array.isArray(kRows) && kRows.length === 1 && kRows[0].id === bookId && 'chunk_count' in kRows[0],
        (kRows ? JSON.stringify(kRows).slice(0, 300) : toolText(rBook).slice(0, 300)))
    } else {
      check(label + ': get_pdf_book（提取 book id）', false, 'list_pdf_books 未返回可解析的 UUID: ' + toolText(rBooks).slice(0, 400))
    }

    const rChunks = await client.callTool('search_text_chunks', { query: '画', query2: '画', query3: '画', limit: 5 })
    const cRows = toolRows(rChunks)
    check(label + ': search_text_chunks(画) 返回 ≤5 行含 book_title/content_preview',
      !rChunks.isError && Array.isArray(cRows) && cRows.length >= 1 && cRows.length <= 5 && 'book_title' in cRows[0] && 'content_preview' in cRows[0],
      (cRows ? JSON.stringify(cRows).slice(0, 300) : toolText(rChunks).slice(0, 300)))

    const rRules = await client.callTool('list_composition_rules', { category: '', active_only: 1, limit: 5 })
    const ruRows = toolRows(rRules)
    check(label + ': list_composition_rules(active) 返回 1~5 行', !rRules.isError && Array.isArray(ruRows) && ruRows.length >= 1 && ruRows.length <= 5 && 'rule_id' in ruRows[0],
      (ruRows ? JSON.stringify(ruRows).slice(0, 300) : toolText(rRules).slice(0, 300)))

    const rFigs = await client.callTool('list_composition_figures', { figure_type: '', limit: 5 })
    const fRows = toolRows(rFigs)
    check(label + ': list_composition_figures 返回行含 figure_id/figure_type', !rFigs.isError && Array.isArray(fRows) && fRows.length >= 1 && 'figure_id' in fRows[0] && 'figure_type' in fRows[0],
      (fRows ? JSON.stringify(fRows).slice(0, 300) : toolText(rFigs).slice(0, 300)))

    const rImgs = await client.callTool('list_extracted_images', { book_id: '', book_id2: '', limit: 5 })
    const iRows = toolRows(rImgs)
    check(label + ': list_extracted_images 返回行含 file_name/page', !rImgs.isError && Array.isArray(iRows) && iRows.length >= 1 && 'file_name' in iRows[0] && 'page' in iRows[0],
      (iRows ? JSON.stringify(iRows).slice(0, 300) : toolText(rImgs).slice(0, 300)))
  },
}

// ── 主流程 ──
const c1 = await verifyServer(wikiSpec)
c1.close()
const c2 = await verifyServer(knowledgeSpec)
c2.close()

const failed = results.filter((x) => !x.ok)
console.log('\n========== RESULT: ' + (results.length - failed.length) + ' passed, ' + failed.length + ' failed ==========')
for (const f of failed) console.log('  FAIL: ' + f.name + ' :: ' + String(f.detail).slice(0, 500))
process.exit(failed.length ? 1 : 0)
