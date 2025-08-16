<template>
  <div class="container">
    <!-- 顶部栏 -->
    <div class="toolbar">
      <div class="group">
        <h1 class="h1">词表</h1>
        <span class="small subtle">状态：{{ readonly ? '只读' : '可编辑' }}</span>
      </div>
      <div class="group">
        <LoginBar :onLogin="refreshAuth" />
      </div>
    </div>

    <div style="height:12px"></div>

    <!-- 工具栏（含 同步音频） -->
    <div class="toolbar">
      <Toolbar
        class="w-full"
        :readonly="readonly"
        :onImported="onImported"
        @created="onCreated"
        @search="onSearch"
        @sync="onSyncAudio"
        @toast="toast"
      />
    </div>

    <div style="height:12px"></div>

    <!-- 表格（外层滚动容器 + 响应式卡片模式由全局CSS控制） -->
    <div class="table-wrap">
      <table class="rtable">
        <thead>
          <tr>
            <th style="width:60px;">#</th>
            <th>词义</th>
            <th>记音</th>
            <th>音频</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <AudioTable
            :rows="rows"
            :total="total"
            :readonly="readonly"
            @duplicate="duplicateRow"
            @remove="deleteRow"
            @toast="toast"
          />
        </tbody>
      </table>
    </div>

    <div style="height:12px"></div>

    <!-- 分页 -->
    <div class="pagination">
      <button class="btn" :disabled="page<=1" @click="prev">上一页</button>
      <span class="small subtle">第 {{ page }} 页</span>
      <button class="btn" :disabled="page*limit>=total" @click="next">下一页</button>
    </div>

    <!-- 右下角悬浮提示窗（Toast） -->
    <div class="toast-wrap">
      <div v-for="t in toasts" :key="t.id" class="toast fade-in" :class="t.type">
        <div class="toast-text">{{ t.text }}</div>
        <div v-if="t.actions && t.actions.length" class="toast-actions">
          <button
            v-for="(a, i) in t.actions"
            :key="i"
            class="btn btn-ghost"
            @click="() => runToastAction(t.id, a)"
          >
            {{ a.label }}
          </button>
        </div>
        <button class="toast-close" @click="dismissToast(t.id)">×</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import LoginBar from './components/LoginBar.vue'
import Toolbar from './components/Toolbar.vue'
import AudioTable from './components/AudioTable.vue'
import { RowAPI, MaintenanceAPI, getStoredToken, initAuthFromStorage } from './api'

/* ------- 状态 ------- */
const rows = ref([])
const total = ref(0)
const page = ref(1)
const limit = ref(50)
const q = ref('')
const readonly = ref(true)

/* ------- Toast（悬浮提示窗） ------- */
let toastSeq = 1
const toasts = ref([])
/** @param {{text:string, type?:'info'|'success'|'error', timeout?:number, actions?:{label:string,onClick?:Function}[]}} opt */
function toast(opt) {
  const id = toastSeq++
  const t = {
    id,
    text: opt.text,
    type: opt.type || 'info',
    actions: opt.actions || [],
    timeout: typeof opt.timeout === 'number'
      ? opt.timeout
      : (opt.actions && opt.actions.length ? 0 : 3000),
  }
  toasts.value.push(t)
  if (t.timeout > 0) setTimeout(() => dismissToast(id), t.timeout)
  return id
}
function dismissToast(id) {
  toasts.value = toasts.value.filter(x => x.id !== id)
}
async function runToastAction(id, action) {
  try { await action.onClick?.() } finally { dismissToast(id) }
}

/* ------- 生命周期 ------- */
onMounted(() => {
  initAuthFromStorage()               // 从存储恢复 token -> axios 默认头
  readonly.value = !getStoredToken()  // 控制可编辑/只读
  load()
})

/* ------- 列表与分页 ------- */
async function load() {
  const offset = (page.value - 1) * limit.value
  const { data } = await RowAPI.list({ q: q.value, limit: limit.value, offset })
  rows.value = data.items
  total.value = data.total
}
function prev() { if (page.value > 1) { page.value--; load() } }
function next() { if (page.value * limit.value < total.value) { page.value++; load() } }
function onSearch(keyword) { q.value = keyword; page.value = 1; load() }

/* ------- 登录切换 ------- */
function refreshAuth() {
  readonly.value = !getStoredToken()
  page.value = 1
  load()
  toast({ text: readonly.value ? '已退出，进入只读模式' : '已登录，进入可编辑模式', type: readonly.value ? 'info' : 'success' })
}

/* ------- Excel 导入 & 批量写库 ------- */
function normalizeFilename(name) {
  if (!name) return ''
  return String(name).trim().replace(/\u3000/g, ' ').replace(/[\r\n\t]/g, '').normalize('NFC')
}
async function onImported(arr) {
  // 预览（支持纯数组或对象）
  const preview = arr.map((r, i) => ({
    id: i + 1,
    col1: (r?.col1 ?? r?.[0] ?? '') + '',
    col2: (r?.col2 ?? r?.[1] ?? '') + '',
    audio_id: typeof (r?.audio_id ?? r?.[2]) === 'number' ? (r?.audio_id ?? r?.[2]) : null,
    audio_filename: typeof (r?.audio_filename ?? r?.audio ?? r?.filename ?? r?.[2]) === 'string'
      ? normalizeFilename(r?.audio_filename ?? r?.audio ?? r?.filename ?? r?.[2])
      : ''
  }))
  rows.value = preview
  total.value = preview.length

  if (readonly.value) {
    toast({ text: `已导入 ${preview.length} 行（仅预览，未写库）。请先登录`, type: 'error', timeout: 5000 })
    return
  }

  toast({
    text: `解析成功：${preview.length} 行。是否写入数据库？`,
    type: 'info',
    actions: [
      {
        label: '写入数据库',
        onClick: async () => {
          await importToBackendBulk(preview)
          page.value = 1
          await load()
          toast({ text: '已写入数据库并刷新列表', type: 'success' })
        }
      },
      { label: '取消' }
    ]
  })
}
async function importToBackendBulk(list) {
  const payload = list.map(r => ({
    col1: r.col1 ?? r[0] ?? '',
    col2: r.col2 ?? r[1] ?? '',
    audio: normalizeFilename(
      (typeof r.audio_filename === 'string' && r.audio_filename) ? r.audio_filename
      : (typeof r[2] === 'string' ? r[2] : '')
    )
  }))
  console.log('bulk payload sample:', payload[0])
  await RowAPI.bulkCreate(payload) // 发送 JSON
}

/* ------- 新增 / 复制 / 删除 ------- */
function onCreated(row) {
  rows.value.unshift(row)
  total.value++
  toast({ text: '已新增一行', type: 'success' })
}

async function deleteRow(id) {
  if (readonly.value) return toast({ text: '只读模式下不能删除', type: 'error' })
  toast({
    text: '确定要删除这一行吗？',
    type: 'error',
    actions: [
      {
        label: '删除',
        onClick: async () => {
          await RowAPI.remove(id)
          rows.value = rows.value.filter(r => r.id !== id)
          total.value--
          toast({ text: '已删除该行', type: 'success' })
        }
      },
      { label: '取消' }
    ]
  })
}

/* ------- 同步音频（扫描 AUDIO_DIR 补登记到 Audio 表） ------- */
async function onSyncAudio() {
  if (readonly.value) return toast({ text: '只读模式下不可同步，请先登录', type: 'error' })
  try {
    const { data } = await MaintenanceAPI.syncAudioDB()
    toast({ text: `同步完成：新增 ${data.added} 条音频记录`, type: 'success' })
  } catch (e) {
    console.error(e)
    toast({ text: '同步失败，请检查后端日志与 AUDIO_DIR', type: 'error' })
  }
}
</script>

<style>
.w-full { width: 100%; }
</style>


