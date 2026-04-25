import { defineStore } from 'pinia'
import axios from 'axios'
import { aiChatConfig } from '../../config/api'
import { useUserStore } from '../user'

const WELCOME_MESSAGE = {
  role: 'assistant',
  content: '你好！我是AI助手，有什么可以帮助你的吗？'
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    currentSessionId: '',
    sessions: [],
    messages: [WELCOME_MESSAGE],
    model: aiChatConfig.model,
    isStreaming: false,
  }),

  getters: {
    hasMessages: (state) => state.messages.length > 0,
    currentSession: (state) => state.sessions.find((s) => s.session_id === state.currentSessionId) || null,
  },

  actions: {
    getAuthHeader() {
      const userStore = useUserStore()
      let token = userStore.token || localStorage.getItem('token') || ''

      // 兼容 pinia 持久化：user-store 里保存了 token
      if (!token) {
        const persistedUserStore = localStorage.getItem('user-store')
        if (persistedUserStore) {
          try {
            token = JSON.parse(persistedUserStore)?.token || ''
          } catch {
            token = ''
          }
        }
      }

      return {
        Authorization: token ? `Bearer ${token}` : '',
      }
    },

    resetAsNewSession() {
      this.currentSessionId = ''
      this.messages = [WELCOME_MESSAGE]
    },

    setMessages(messages = []) {
      if (!Array.isArray(messages) || messages.length === 0) {
        this.messages = [WELCOME_MESSAGE]
        return
      }
      this.messages = messages
    },

    addMessage(message) {
      this.messages.push(message)
    },

    updateLastAssistantContent(content) {
      if (!this.messages.length) return
      const lastIndex = this.messages.length - 1
      if (this.messages[lastIndex].role !== 'assistant') return
      this.messages[lastIndex].content = content
    },

    upsertSession(session) {
      if (!session?.session_id) return
      const idx = this.sessions.findIndex((s) => s.session_id === session.session_id)
      if (idx === -1) {
        this.sessions.unshift(session)
      } else {
        this.sessions[idx] = { ...this.sessions[idx], ...session }
      }
    },

    bindSessionId(sessionId) {
      if (!sessionId) return
      this.currentSessionId = sessionId
      this.upsertSession({ session_id: sessionId, updated_at: new Date().toISOString() })
    },

    async fetchSessions() {
      const headers = this.getAuthHeader()
      if (!headers.Authorization) return

      const response = await axios.get(aiChatConfig.sessionsEndpoint, { headers })
      const list = response?.data?.data || []
      this.sessions = Array.isArray(list) ? list : []

      if (this.currentSessionId && !this.sessions.some((s) => s.session_id === this.currentSessionId)) {
        this.currentSessionId = ''
      }
    },

    async fetchSessionMessages(sessionId) {
      if (!sessionId) {
        this.resetAsNewSession()
        return
      }

      const headers = this.getAuthHeader()
      const url = aiChatConfig.sessionMessagesEndpoint(sessionId)
      const response = await axios.get(url, { headers })
      const rawData = response?.data?.data
      const rows = Array.isArray(rawData) ? rawData : (rawData?.messages || [])
      const formatted = rows.map((item) => ({ role: item.role, content: item.content }))
      this.currentSessionId = sessionId
      this.setMessages(formatted)
    },
  },

  persist: {
    enabled: true,
    strategies: [
      {
        key: 'chat-store',
        storage: localStorage,
      },
    ],
  },
})
