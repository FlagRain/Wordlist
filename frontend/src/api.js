// src/api.js
import axios from 'axios'

// ---------- 基础配置 ----------
const API_BASE = import.meta.env.VITE_API_BASE
export const api = axios.create({ baseURL: API_BASE })

// ---------- 统一的 Token 管理（session/local 双通道） ----------
export function getStoredToken() {
  return sessionStorage.getItem('token') || localStorage.getItem('token') || ''
}

export function saveToken(token, remember = false) {
  clearToken()
  if (!token) return
  if (remember) {
    localStorage.setItem('token', token)     // 记住我：持久化
  } else {
    sessionStorage.setItem('token', token)   // 不勾选：仅当前会话
  }
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

export function clearToken() {
  delete api.defaults.headers.common['Authorization']
  sessionStorage.removeItem('token')
  localStorage.removeItem('token')
}

export function initAuthFromStorage() {
  const t = getStoredToken()
  if (t) api.defaults.headers.common['Authorization'] = `Bearer ${t}`
}

// 启动时尝试从存储恢复
initAuthFromStorage()

// ---------- 各类 API 封装 ----------
export const AuthAPI = {
  login: (username, password) =>
    api.post('/auth/login', new URLSearchParams({ username, password })),
  me: () => api.get('/auth/me'),
}

export const RowAPI = {
  list: ({ q = '', limit = 50, offset = 0 } = {}) =>
    api.get('/rows', { params: { q, limit, offset } }),

  create: (formData) => api.post('/rows', formData),

  update: (id, formData) => api.put(`/rows/${id}`, formData),

  remove: (id) => api.delete(`/rows/${id}`),

  // 批量导入（JSON）。后端应兼容 {col1,col2,audio_id?,audio?} 或二维数组
  bulkCreate: (rows) =>
    api.post('/rows/bulk', rows, {
      headers: { 'Content-Type': 'application/json' },
    }),
}

export const FileAPI = {
  upload: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/upload', fd)
  },
  exportExcel: () =>
    api.get('/export.xlsx', { responseType: 'blob' }),
}

export const MaintenanceAPI = {
  // 扫描 AUDIO_DIR，把磁盘上未登记的音频补进 Audio 表
  syncAudioDB: () => api.post('/maintenance/sync-audio-db'),
}

// ---------- 工具 ----------
export const audioUrl = (audio_id) => `${API_BASE}/audio/${audio_id}`
