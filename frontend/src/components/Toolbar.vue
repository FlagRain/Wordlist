<template>
  <div class="toolbar">
    <div class="group">
      <button class="btn btn-primary" @click="exportXlsx" title="导出为 Excel">
        导出 Excel
      </button>

      <button class="btn" :disabled="readonly" @click="pickAudio" title="上传音频并新增一行">
        新增行（上传音频）
      </button>
      <input
        ref="audioInput"
        type="file"
        class="hidden-file"
        accept="audio/*"
        @change="addRowFromPicked"
      />

      <button class="btn" @click="pickExcel" title="从 Excel 导入">
        导入 Excel
      </button>
      <input
        ref="excelInput"
        type="file"
        class="hidden-file"
        accept=".xlsx,.xls"
        @change="importXlsxFromPicked"
      />

      <button class="btn" :disabled="readonly" @click="$emit('sync')" title="扫描目录，补登记音频">
        同步音频
      </button>
    </div>

    <div class="group">
      <div class="search">
        <input
          class="input"
          v-model="keyword"
          placeholder="搜索（col1 / col2 / 文件名）"
          @input="onSearchInput"
          @keyup.enter="emitSearch"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import * as XLSX from 'xlsx'
import { FileAPI, RowAPI } from '../api'
import { ref } from 'vue'

const emit = defineEmits(['created', 'search', 'sync', 'toast'])
const props = defineProps({ readonly: Boolean, onImported: Function })

const keyword = ref('')
let timer = null

const audioInput = ref(null)
const excelInput = ref(null)

/* ---------- 导出 ---------- */
async function exportXlsx() {
  try {
    const res = await FileAPI.exportExcel()
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = '音频表.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    emit('toast', { text: '已导出 Excel', type: 'success' })
  } catch (e) {
    console.error(e)
    emit('toast', { text: '导出失败，请检查后端', type: 'error' })
  }
}

/* ---------- 新增行（上传音频） ---------- */
function pickAudio() {
  if (props.readonly) {
    emit('toast', { text: '只读模式下不可新增，请先登录', type: 'error' })
    return
  }
  audioInput.value?.click()
}
async function addRowFromPicked(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  try {
    const { data } = await FileAPI.upload(file)
    const fd = new FormData()
    fd.append('col1', file.name.replace(/\.[^.]+$/, ''))
    fd.append('col2', '')
    fd.append('audio_id', data.audio_id)
    const r = await RowAPI.create(fd)
    emit('created', {
      id: r.data.id,
      col1: fd.get('col1'),
      col2: '',
      audio_id: data.audio_id,
      audio_filename: data.filename,
    })
    emit('toast', { text: `已新增一行并上传音频：${data.filename}`, type: 'success' })
  } catch (err) {
    console.error(err)
    emit('toast', { text: '新增失败，请检查网络与后端', type: 'error' })
  }
}

/* ---------- 导入 Excel ---------- */
function pickExcel() {
  excelInput.value?.click()
}

function readWorkbook(file) {
  return new Promise((resolve, reject) => {
    const isXlsx = /\.xlsx$/i.test(file.name)
    const reader = new FileReader()
    reader.onerror = e => reject(e)
    reader.onload = () => {
      try {
        let wb
        try {
          wb = XLSX.read(reader.result, { type: isXlsx ? 'array' : 'binary' })
        } catch {
          wb = XLSX.read(reader.result, { type: isXlsx ? 'binary' : 'array' })
        }
        resolve(wb)
      } catch (e) {
        reject(e)
      }
    }
    try {
      if (isXlsx) reader.readAsArrayBuffer(file)
      else reader.readAsBinaryString(file)
    } catch {
      reader.readAsArrayBuffer(file)
    }
  })
}

async function importXlsxFromPicked(e) {
  const f = e.target.files?.[0]
  e.target.value = ''
  if (!f) return
  try {
    const wb = await readWorkbook(f)
    const sheetName = wb.SheetNames[0]
    if (!sheetName) throw new Error('工作簿没有工作表')
    const ws = wb.Sheets[sheetName]
    let rows = XLSX.utils.sheet_to_json(ws, { header: 1 })
    if (rows.length > 0) rows = rows.slice(1)

    emit('toast', { text: `解析成功：${rows.length} 行，预览中…`, type: 'success' })
    props.onImported?.(rows)
  } catch (err) {
    console.error('解析 Excel 失败：', err)
    emit('toast', { text: '解析 Excel 失败：请确认文件格式', type: 'error' })
  }
}

/* ---------- 搜索 ---------- */
function emitSearch() {
  emit('search', keyword.value.trim())
}
function onSearchInput() {
  clearTimeout(timer)
  timer = setTimeout(emitSearch, 250)
}
</script>

<style scoped>
.hidden-file { display: none; }
</style>
