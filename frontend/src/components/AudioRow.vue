<template>
  <tr class="row">
    <td class="col-index" data-label="序号">{{ index + 1 }}</td>

    <td class="col-text" data-label="词义">
      <input
        class="input"
        :disabled="readonly || saving"
        v-model="local.col1"
        @change="saveField('col1', local.col1)"
        placeholder="第一列"
      />
    </td>

    <td class="col-text" data-label="记音">
      <input
        class="input"
        :disabled="readonly || saving"
        v-model="local.col2"
        @change="saveField('col2', local.col2)"
        placeholder="第二列"
      />
    </td>

    <td class="col-audio" data-label="音频">
      <div class="audio-wrap">
        <button class="btn btn-primary" :disabled="!local.audio_id || playing" @click="play">
          {{ playing ? '…' : '播放' }}
        </button>

        <span v-if="local.audio_filename" class="badge" :title="local.audio_filename">
          {{ local.audio_filename }}
        </span>
        <span v-else class="badge badge-muted">无音频</span>

        <button class="btn btn-ghost" :disabled="readonly || saving" @click="openFilePicker">
          {{ saving && picking ? '…' : '替换音频' }}
        </button>
        <input ref="fileInput" class="hidden-file" type="file" accept="audio/*" @change="onFilePicked" />

        <!-- 仅解绑，不删文件 -->
        <button class="btn btn-danger" :disabled="readonly || !local.audio_id || saving" @click="confirmUnlink">
          {{ saving && unlinking ? '…' : '移除音频' }}
        </button>
      </div>
    </td>

    <td class="col-actions" data-label="操作">
      <div class="action-wrap">
        <button class="btn btn-danger" :disabled="readonly || saving" @click="$emit('remove', local.id)">删除</button>
      </div>
    </td>
  </tr>
</template>

<script setup>
import { ref, watch } from 'vue'
import { audioUrl, FileAPI, RowAPI } from '../api'

const props = defineProps({ modelValue: Object, index: Number, readonly: Boolean })
const emit = defineEmits(['update:modelValue', 'duplicate', 'remove', 'toast'])

const local = ref({ ...(props.modelValue || {}) })
watch(() => props.modelValue, v => { local.value = { ...(v || {}) } }, { deep:false })

// 状态
const playing = ref(false)
const saving = ref(false)
const picking = ref(false)
const unlinking = ref(false)

// 播放
function play(){
  if(!local.value.audio_id){
    emit('toast', { text:'该行没有音频', type:'error' })
    return
  }
  try{
    playing.value = true
    const el = new Audio(audioUrl(local.value.audio_id))
    el.addEventListener('error', () => {
      emit('toast', { text:'无法播放：资源不可用或格式不支持', type:'error' })
      playing.value = false
    })
    el.addEventListener('ended', () => { playing.value = false })
    el.play().catch(() => {
      emit('toast', { text:'播放失败：可能被浏览器策略拦截', type:'error' })
      playing.value = false
    })
  }catch{
    playing.value = false
  }
}

// 替换音频
const fileInput = ref(null)
function openFilePicker(){
  if (props.readonly) return emit('toast', { text:'只读模式下不可替换音频', type:'error' })
  fileInput.value?.click()
}
async function onFilePicked(e){
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  try{
    saving.value = true; picking.value = true
    const { data } = await FileAPI.upload(file)
    const fd = new FormData()
    fd.append('audio_id', String(data.audio_id))  // 统一传字符串，后端会转
    await RowAPI.update(local.value.id, fd)
    const updated = { ...local.value, audio_id: data.audio_id, audio_filename: data.filename }
    local.value = updated
    emit('update:modelValue', updated)
    emit('toast', { text:`已替换音频：${data.filename}`, type:'success' })
  }catch(err){
    console.error(err)
    emit('toast', { text:'替换失败，请检查后端与网络', type:'error' })
  }finally{
    saving.value = false; picking.value = false
  }
}

// 保存字段
async function saveField(field, value){
  try{
    saving.value = true
    const fd = new FormData()
    fd.append(field, value ?? '')
    await RowAPI.update(local.value.id, fd)
    emit('update:modelValue', { ...local.value, [field]: value ?? '' })
  }catch(err){
    console.error(err)
    emit('toast', { text:'保存失败', type:'error' })
  }finally{
    saving.value = false
  }
}

// 解绑前确认
function confirmUnlink(){
  if (props.readonly || !local.value.audio_id) return
  emit('toast', {
    text: '确定移除本行与音频的绑定吗？（不删除文件）',
    type: 'error',
    actions: [
      { label: '移除', onClick: unlinkAudio },
      { label: '取消' }
    ]
  })
}

// 仅移除绑定（不删文件）
async function unlinkAudio(){
  try{
    saving.value = true; unlinking.value = true
    const fd = new FormData()
    fd.append('clear_audio', '1')   // 后端 update_row 已支持
    await RowAPI.update(local.value.id, fd)
    const updated = { ...local.value, audio_id: null, audio_filename: '' }
    local.value = updated
    emit('update:modelValue', updated)
    emit('toast', { text:'已移除该行音频', type:'success' })
  }catch(e){
    console.error(e)
    emit('toast', { text:'移除失败，请检查后端日志', type:'error' })
  }finally{
    saving.value = false; unlinking.value = false
  }
}
</script>

<style scoped>
/* ====== 列宽/布局 ====== */
.col-index{ width:56px; }
.col-text{ min-width:220px; }
.col-audio{ min-width:420px; } 
.col-actions{ width:160px; }

.audio-wrap{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.action-wrap{ display:flex; gap:10px; }

/* ====== 输入 ====== */
.input{
  width:100%;
  border:1px solid var(--border);
  border-radius:12px;
  padding:10px 12px;
  background: rgba(255,255,255,.02);
  color: var(--text);
  transition:border-color .15s, box-shadow .15s, background .15s;
}
.input::placeholder{ color: var(--muted); }
.input:focus{
  outline:none;
  border-color: rgba(96,165,250,.85);
  box-shadow: 0 0 0 4px rgba(96,165,250,.22);
  background: rgba(255,255,255,.04);
}

/* ====== 文件名 Chip ====== */
.badge{
  display:inline-flex; align-items:center;
  max-width:260px;
  padding:6px 12px;
  font-size:12px;
  color: var(--text);
  background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,0));
  border:1px solid var(--border);
  border-radius:999px;
  box-shadow: 0 8px 20px rgba(0,0,0,.18) inset, 0 6px 16px rgba(0,0,0,.14);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.badge-muted{
  color: var(--muted);
  background: rgba(255,255,255,.04);
  border:1px solid var(--border);
}

/* ====== 按钮· ====== */
.btn{
  border:1px solid var(--border);
  border-radius:999px;
  padding:8px 16px;
  font-size:14px;
  background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,0));
  color: var(--text);
  box-shadow: 0 6px 14px rgba(0,0,0,.18);
  transition: transform .05s, box-shadow .15s, border-color .15s, background .15s, opacity .15s;
  cursor:pointer;
}
.btn:hover{ border-color: var(--border-strong); box-shadow: 0 10px 22px rgba(0,0,0,.22); }
.btn:active{ transform: translateY(1px); }
.btn:disabled{
  opacity:.55; cursor:not-allowed;
  filter:saturate(.7);
}

/* 主按钮（播放） */
.btn-primary{
  color:#fff;
  background: linear-gradient(180deg, rgba(59,130,246,.28), rgba(59,130,246,.12));
  border-color: rgba(59,130,246,.75);
  box-shadow: 0 12px 26px rgba(59,130,246,.28);
}
.btn-primary:hover{
  background: linear-gradient(180deg, rgba(59,130,246,.35), rgba(59,130,246,.16));
  border-color: var(--primary);
}

/* 危险按钮（移除音频） */
.btn-danger{
  color:#fff;
  background: linear-gradient(180deg, rgba(239,68,68,.30), rgba(239,68,68,.14));
  border-color: rgba(239,68,68,.75);
  box-shadow: 0 12px 26px rgba(239,68,68,.26);
}
.btn-danger:hover{
  background: linear-gradient(180deg, rgba(239,68,68,.36), rgba(239,68,68,.18));
  border-color: var(--danger);
}

/* 次级按钮（替换音频） */
.btn-ghost{
  color: var(--text);
  background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,0));
  border-color: var(--border);
}
.btn-ghost:hover{ background: rgba(255,255,255,.08); }

/* 隐藏文件选择器 */
.hidden-file{ display:none; }

/* ====== 小图标版播放按钮 ====== */
.btn-primary::before{
  content:"▶";
  display:inline-block;
  margin-right:6px;
  font-weight:700;
  filter: drop-shadow(0 2px 4px rgba(0,0,0,.25));
}


tr.row:hover .btn,
tr.row:hover .badge{
  box-shadow: 0 14px 30px rgba(0,0,0,.25);
}
</style>

