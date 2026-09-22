<template>
  <div class="ss-page">
    <div class="ss-header">
      <h2 class="ss-title">系统设置</h2>
      <p class="ss-desc">修改后即时生效，无需重新部署。游客看到的标题、副标题、页脚等都会同步更新。</p>
    </div>

    <!-- AI 接口切换卡片 -->
    <div class="ss-card" v-loading="aiLoading">
      <div class="ss-section" style="margin-bottom: 0;">
        <h3 class="ss-section-title">AI 接口</h3>
        <p class="ss-ai-desc">默认文本 AI 供应商，保存后立即生效（约 5 秒内全站切换），无需重新部署。题跋识别、构图讲评等视觉专用链路不受此开关影响。</p>
        <div class="ss-ai-row">
          <div class="ss-field" style="flex: 1;">
            <label class="ss-label">默认供应商</label>
            <select class="ss-input" v-model="ai.provider">
              <option value="auto">自动（按可用密钥）</option>
              <option value="custom" :disabled="!aiKeys.custom">自定义 OpenAI 兼容（需配 AI_BASE_URL）</option>
              <option value="deepseek" :disabled="!aiKeys.deepseek">DeepSeek</option>
              <option value="qwen" :disabled="!aiKeys.qwen">通义千问 Qwen</option>
              <option value="siliconflow" :disabled="!aiKeys.siliconflow">硅基流动 SiliconFlow</option>
              <option value="zhipu" :disabled="!aiKeys.zhipu">智谱 GLM</option>
            </select>
            <span class="ss-hint">「自动」= custom → DeepSeek → Qwen → 智谱，按服务器已配置的密钥顺序取用</span>
          </div>
          <div class="ss-field" style="flex: 1;">
            <label class="ss-label">模型覆盖（可选）</label>
            <input class="ss-input" v-model="ai.model" placeholder="留空用该供应商默认模型"
                   @input="aiDirty = true" />
            <span class="ss-hint">如 deepseek-chat / qwen3.5-plus /glm-5v-turbo；仅对此开关管辖的文本 AI 生效</span>
          </div>
        </div>
        <div class="ss-ai-keys">
          <span v-for="(ok, name) in aiKeys" :key="name" class="ss-ai-key" :class="{ on: ok }">
            {{ aiProviderNames[name] || name }} {{ ok ? '已配置' : '未配置' }}
          </span>
        </div>
        <div class="ss-actions" style="margin-top: 16px; padding-top: 16px;">
          <button class="ss-btn-save" :disabled="aiSaving" @click="saveAI">
            <el-icon v-if="aiSaving" class="is-loading"><Loading /></el-icon>
            {{ aiSaving ? '保存中...' : '保存切换' }}
          </button>
          <button class="ss-btn-reset" :disabled="aiTesting" @click="testAI">
            {{ aiTesting ? '测试中...' : '测试连通' }}
          </button>
          <span v-if="aiMsg" class="ss-msg" :class="{ error: aiMsgErr }">{{ aiMsg }}</span>
        </div>
        <div v-if="aiTestResult" class="ss-ai-test" :class="{ fail: !aiTestResult.ok }">
          <template v-if="aiTestResult.ok">
            ✓ {{ aiTestResult.model || '未知模型' }} · {{ aiTestResult.latency }}s · 回复「{{ aiTestResult.reply }}」
          </template>
          <template v-else>✗ {{ aiTestResult.error }}（{{ aiTestResult.latency }}s）</template>
        </div>
        <div v-if="Object.keys(aiUsage).length" class="ss-ai-usage">
          <div class="ss-ai-usage-title">进程内调用计量（重启清零）</div>
          <table class="ss-ai-usage-table">
            <thead><tr><th>供应商:模型</th><th>调用</th><th>失败</th><th>tokens</th><th>均延迟</th></tr></thead>
            <tbody>
              <tr v-for="(st, key) in aiUsage" :key="key">
                <td>{{ key }}</td><td>{{ st.calls }}</td><td>{{ st.failures }}</td>
                <td>{{ st.tokens || '—' }}</td>
                <td>{{ st.calls ? (st.latency_sum / st.calls).toFixed(2) + 's' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="ss-card" v-loading="loading">
      <!-- 错误提示 -->
      <div v-if="loadError" class="ss-alert ss-alert-error">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ loadError }}</span>
        <button class="ss-alert-retry" @click="load">重试</button>
      </div>

      <!-- 分组：品牌信息 -->
      <div class="ss-section">
        <h3 class="ss-section-title">品牌信息</h3>
        <div class="ss-grid">
          <div class="ss-field" v-for="item in brandFields" :key="item.key">
            <label class="ss-label">{{ item.label }}</label>
            <input
              class="ss-input"
              v-model="form[item.key]"
              :placeholder="item.placeholder"
              @input="onFieldChange"
            />
            <span class="ss-hint">{{ item.hint }}</span>
          </div>
        </div>
      </div>

      <!-- 分组：页脚与署名 -->
      <div class="ss-section">
        <h3 class="ss-section-title">页脚与署名</h3>
        <div class="ss-grid">
          <div class="ss-field" v-for="item in footerFields" :key="item.key">
            <label class="ss-label">{{ item.label }}</label>
            <input
              class="ss-input"
              v-model="form[item.key]"
              :placeholder="item.placeholder"
              @input="onFieldChange"
            />
            <span class="ss-hint">{{ item.hint }}</span>
          </div>
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="ss-actions">
        <button class="ss-btn-save" :disabled="saving || !dirty" @click="save">
          <el-icon v-if="saving" class="is-loading"><Loading /></el-icon>
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
        <button class="ss-btn-reset" :disabled="saving || !dirty" @click="reset">
          取消
        </button>
        <span v-if="msg" class="ss-msg" :class="{ error: msgErr }">{{ msg }}</span>
      </div>
    </div>

    <!-- 预览卡片 -->
    <div class="ss-preview" v-if="!loading && !loadError">
      <h3 class="ss-preview-title">预览效果</h3>
      <div class="ss-preview-card">
        <div class="preview-logo">
          <span class="preview-title">{{ form.title || '墨林百科' }}</span>
          <span class="preview-subtitle">{{ form.subtitle || '最智能的中国画与书法大库' }}</span>
        </div>
        <div class="preview-browser">
          <span class="preview-tab">{{ form.full_title || '墨林百科 - 最智能的中国画与书法大库' }}</span>
        </div>
        <div class="preview-footer">
          {{ form.footer || '墨林百科 © 2026' }}
          <span v-if="form.author"> · {{ form.author }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { WarningFilled, Loading } from '@element-plus/icons-vue'
import api from '../../api'

const loading = ref(true)
const saving = ref(false)
const msg = ref('')
const msgErr = ref(false)
const loadError = ref('')
const dirty = ref(false)
const initialForm = {}

const brandFields = [
  { key: 'title',      label: '网站标题',      placeholder: '墨林百科',       hint: '导航栏 logo、登录页标题' },
  { key: 'subtitle',   label: '副标题',        placeholder: '最智能的中国画与书法大库', hint: 'logo 下方、首页 hero 区' },
  { key: 'full_title', label: '全称',          placeholder: '墨林百科 - 最智能的中国画与书法大库', hint: '浏览器标签页标题' },
  { key: 'domain',     label: '域名',          placeholder: 'molin.wiki',    hint: '当前域名' },
]

const footerFields = [
  { key: 'footer',     label: '页脚文案',      placeholder: '墨林百科 © 2026', hint: '页面底部' },
  { key: 'author',     label: '作者署名',      placeholder: '周豪 Zax',       hint: '页脚署名' },
]

const form = reactive({
  title: '', subtitle: '', full_title: '', domain: '', footer: '', author: '',
})

// ── AI 接口切换 ──
const aiLoading = ref(false)
const aiSaving = ref(false)
const aiTesting = ref(false)
const aiMsg = ref('')
const aiMsgErr = ref(false)
const aiDirty = ref(false)
const aiKeys = ref({})
const aiUsage = ref({})
const aiTestResult = ref(null)
const ai = reactive({ provider: 'auto', model: '' })
const aiProviderNames = {
  auto: '自动', custom: '自定义', deepseek: 'DeepSeek',
  qwen: 'Qwen', siliconflow: 'SiliconFlow', zhipu: '智谱 GLM',
}

async function loadAI() {
  aiLoading.value = true
  try {
    const d = await api.get('/admin/ai-provider')
    ai.provider = d.provider || 'auto'
    ai.model = d.model || ''
    aiKeys.value = d.keys_present || {}
    aiUsage.value = d.usage || {}
    aiDirty.value = false
    aiMsg.value = ''
  } catch (e) {
    // 权限不足等场景静默：品牌设置区的 loadError 已有提示
    console.error('加载 AI 接口配置失败', e)
  } finally {
    aiLoading.value = false
  }
}

async function saveAI() {
  aiSaving.value = true
  aiMsg.value = ''
  try {
    const d = await api.put('/admin/ai-provider', {
      provider: ai.provider,
      model: ai.model.trim(),
    })
    aiMsg.value = `已切换到「${aiProviderNames[d.provider] || d.provider}」，约 5 秒内全站生效`
    aiMsgErr.value = false
    aiDirty.value = false
    loadAI()
  } catch (e) {
    const data = e.response?.data
    aiMsg.value = data?.detail || `HTTP ${e.response?.status || ''}`
    aiMsgErr.value = true
  } finally {
    aiSaving.value = false
  }
}

async function testAI() {
  aiTesting.value = true
  aiTestResult.value = null
  try {
    const d = await api.post('/admin/ai-provider/test', {
      provider: ai.provider === 'auto' ? '' : ai.provider,
      model: ai.model.trim(),
    })
    aiTestResult.value = { ...d, provider: d.model ? (d.provider || ai.provider) : ai.provider }
  } catch (e) {
    aiTestResult.value = { ok: false, error: e.response?.data?.detail || e.message, latency: 0 }
  } finally {
    aiTesting.value = false
  }
}

function onFieldChange() {
  dirty.value = true
}

onMounted(async () => {
  await load()
  loadAI()
})

async function load() {
  loading.value = true
  loadError.value = ''
  msg.value = ''
  try {
    const data = await api.get('/admin/site-settings')
    const s = data.settings || {}
    for (const f of [...brandFields, ...footerFields]) {
      if (s[f.key] !== undefined) {
        form[f.key] = s[f.key]
        initialForm[f.key] = s[f.key]
      }
    }
  } catch (e) {
    if (e.response && (e.response.status === 401 || e.response.status === 403)) {
      loadError.value = '您没有管理员权限，无法加载系统设置。请确认已登录管理员账号。'
    } else if (e.response) {
      // 尝试取后端错误消息，失败则用状态码
      const errMsg = e.response.data?.detail || `HTTP ${e.response.status}`
      loadError.value = `加载失败：${errMsg}`
    } else {
      loadError.value = '网络请求失败：' + e.message
    }
  } finally {
    loading.value = false
  }
}

function reset() {
  for (const f of [...brandFields, ...footerFields]) {
    form[f.key] = initialForm[f.key] || ''
  }
  dirty.value = false
  msg.value = ''
}

async function save() {
  saving.value = true
  msg.value = ''
  try {
    // 只发送有值的字段 + 已修改的字段（防止空值覆盖现有数据）
    const payload = {}
    for (const f of [...brandFields, ...footerFields]) {
      const val = form[f.key]?.trim()
      if (val) {
        payload[f.key] = val
      }
    }

    await api.put('/admin/site-settings', { settings: payload })

    // 更新 initialForm 以匹配已保存的值
    for (const f of [...brandFields, ...footerFields]) {
      initialForm[f.key] = form[f.key]
    }
    // 写入 localStorage 作为前端缓存
    localStorage.setItem('molin_site_config', JSON.stringify({ ...form }))
    dirty.value = false
    msg.value = '设置已保存，刷新页面即可看到效果'
    msgErr.value = false
  } catch (e) {
    if (e.response) {
      // 尝试取后端错误消息（detail 或纯文本），失败则用状态码
      const data = e.response.data
      const detail = data?.detail || (typeof data === 'string' ? data.substring(0, 80) : '')
      msg.value = detail || `HTTP ${e.response.status}`
    } else {
      msg.value = '请求失败: ' + e.message
    }
    msgErr.value = true
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.ss-page {
  padding: 20px 24px;
}

/* 头部 */
.ss-header {
  margin-bottom: 18px;
}
.ss-title {
  font-size: 22px;
  font-weight: 700;
  color: #3a3222;
  margin: 0 0 6px;
  font-family: 'Noto Serif SC', serif;
}
.ss-desc {
  font-size: 13px;
  color: #8c7a5c;
  margin: 0;
  line-height: 1.6;
}

/* 卡片容器 */
.ss-card {
  background: #fff;
  border: 1px solid #e8e4d8;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 20px;
}

/* 错误提示 */
.ss-alert {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 20px;
}
.ss-alert-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}
.ss-alert-retry {
  margin-left: auto;
  padding: 4px 12px;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  background: #fff;
  color: #b91c1c;
  font-size: 12px;
  cursor: pointer;
}
.ss-alert-retry:hover {
  background: #fef2f2;
}

/* 分组 */
.ss-section {
  margin-bottom: 24px;
}
.ss-section:last-of-type {
  margin-bottom: 0;
}
.ss-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #5c5346;
  margin: 0 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0ebe0;
}

/* 字段网格 */
.ss-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ss-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ss-label {
  font-size: 13px;
  font-weight: 500;
  color: #5c5346;
}
.ss-input {
  width: 100%;
  padding: 9px 12px;
  font-size: 14px;
  border: 1px solid #d0ccc0;
  border-radius: 8px;
  background: #faf9f5;
  color: #2c2416;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.ss-input:focus {
  border-color: #c8a45c;
  box-shadow: 0 0 0 3px rgba(200,164,92,0.12);
  background: #fff;
}
.ss-hint {
  font-size: 11px;
  color: #b0a890;
}

/* ── AI 接口切换 ── */
.ss-ai-desc {
  font-size: 12px;
  color: #8c7a5c;
  line-height: 1.6;
  margin: -6px 0 14px;
}
.ss-ai-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.ss-ai-keys {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.ss-ai-key {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 10px;
  border: 1px solid #e0dbc8;
  background: #faf9f5;
  color: #b0a890;
}
.ss-ai-key.on {
  border-color: #cfe3c2;
  background: #f3f9ee;
  color: #4a7a35;
}
.ss-ai-test {
  margin-top: 12px;
  font-size: 12.5px;
  padding: 9px 14px;
  border-radius: 8px;
  background: #f3f9ee;
  border: 1px solid #cfe3c2;
  color: #4a7a35;
}
.ss-ai-test.fail {
  background: #fef2f2;
  border-color: #fecaca;
  color: #b91c1c;
  word-break: break-all;
}
.ss-ai-usage {
  margin-top: 16px;
}
.ss-ai-usage-title {
  font-size: 11px;
  color: #b0a890;
  margin-bottom: 6px;
}
.ss-ai-usage-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.ss-ai-usage-table th, .ss-ai-usage-table td {
  text-align: left;
  padding: 5px 10px;
  border-bottom: 1px solid #f0ebe0;
  color: #5c5346;
}
.ss-ai-usage-table th {
  color: #b0a890;
  font-weight: 500;
  font-size: 11px;
}

/* 操作栏 */
.ss-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f0ebe0;
}
.ss-btn-save {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  background: #c45a3c;
  color: #fff;
  transition: opacity 0.2s;
}
.ss-btn-save:hover:not(:disabled) { opacity: 0.9; }
.ss-btn-save:disabled { opacity: 0.45; cursor: not-allowed; }

.ss-btn-reset {
  padding: 9px 16px;
  border: 1px solid #d0ccc0;
  border-radius: 8px;
  font-size: 13px;
  background: #fff;
  color: #8c7a5c;
  cursor: pointer;
  transition: all 0.2s;
}
.ss-btn-reset:hover:not(:disabled) {
  border-color: #c45a3c;
  color: #c45a3c;
}
.ss-btn-reset:disabled { opacity: 0.4; cursor: not-allowed; }

.ss-msg {
  font-size: 13px;
  margin-left: 4px;
}
.ss-msg:not(.error) { color: #5a8a4a; }
.ss-msg.error { color: #d03030; }

/* 预览卡片 */
.ss-preview {
  margin-top: 0;
}
.ss-preview-title {
  font-size: 13px;
  font-weight: 600;
  color: #8c7a5c;
  margin: 0 0 10px;
}
.ss-preview-card {
  background: #fff;
  border: 1px solid #e8e4d8;
  border-radius: 12px;
  overflow: hidden;
}

.preview-logo {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-bottom: 1px solid #f0ebe0;
}
.preview-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 18px;
  font-weight: 700;
  color: #c45a3c;
}
.preview-subtitle {
  font-size: 12px;
  color: #8c7a5c;
}

.preview-browser {
  padding: 8px 24px;
  background: #faf9f5;
  border-bottom: 1px solid #f0ebe0;
}
.preview-tab {
  font-size: 11px;
  color: #b0a890;
}

.preview-footer {
  padding: 14px 24px;
  font-size: 12px;
  color: #b0a890;
  text-align: center;
}
</style>
