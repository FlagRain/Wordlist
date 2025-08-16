<template>
  <div class="flex gap-2 items-center">
    <span v-if="!loggedIn">访客 · 仅查看</span>
    <span v-else>已登录 · 可编辑</span>

    <template v-if="!loggedIn">
      <input class="input" v-model.trim="username" placeholder="用户名"
             autocomplete="off" autocapitalize="off" spellcheck="false" style="max-width:160px" />
      <input class="input" v-model.trim="password" placeholder="密码" type="password"
             autocomplete="new-password" autocapitalize="off" spellcheck="false" style="max-width:160px" />
      <label class="flex items-center gap-1" style="font-size:12px;color:#666;">
        <input type="checkbox" v-model="remember" /> 记住我
      </label>
      <button class="btn btn-primary" @click="login">登录</button>
    </template>

    <template v-else>
      <button class="btn btn-ghost" @click="logout">退出登录</button>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { AuthAPI, getStoredToken, saveToken, clearToken } from '../api'

const props = defineProps({ onLogin: Function })
const tokenRef = ref('')
const username = ref('')
const password = ref('')
const remember = ref(false)

const loggedIn = computed(() => !!tokenRef.value)

onMounted(() => {
  tokenRef.value = getStoredToken()
})

async function login() {
  const { data } = await AuthAPI.login(username.value, password.value)
  tokenRef.value = data.access_token
  saveToken(tokenRef.value, remember.value)
  props.onLogin?.()
}

function logout() {
  clearToken() 
  tokenRef.value = ''
  username.value = ''
  password.value = ''
  props.onLogin?.()
}
</script>
