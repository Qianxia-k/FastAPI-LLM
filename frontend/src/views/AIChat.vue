<template>
  <div class="ai-chat-container">
    <van-nav-bar title="AI问答" fixed>
      <template #left>
        <van-button size="small" plain type="primary" @click="createNewSession">新建</van-button>
      </template>
      <template #right>
        <van-button size="small" plain type="primary" @click="showSessionPopup = true">会话</van-button>
      </template>
    </van-nav-bar>

    <div class="session-meta">
      <span class="session-label">会话：</span>
      <span class="session-id">{{ displaySessionId }}</span>
    </div>
    
    <div class="chat-content">
      <div class="messages-container" ref="messagesContainer">
        <div 
          v-for="(message, index) in messages" 
          :key="index" 
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
        >
          <div class="message-content">
            <div v-if="message.role === 'assistant' && message.content === ''" class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div v-else v-html="formatMessage(message.content)"></div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button 
          type="primary" 
          class="send-button" 
          :disabled="isLoading || !userInput.trim()" 
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>

    <van-popup v-model:show="showSessionPopup" position="left" :style="{ width: '85%', height: '100%' }">
      <div class="session-panel">
        <div class="session-panel-header">
          <h3>历史会话</h3>
          <van-button size="small" type="primary" @click="createNewSession">新建会话</van-button>
        </div>
        <div class="session-list">
          <van-cell
            v-for="item in sessions"
            :key="item.session_id"
            :title="item.title || `会话 ${item.session_id.slice(0, 8)}`"
            :label="item.summary || '暂无摘要'"
            is-link
            @click="switchSession(item.session_id)"
          >
            <template #right-icon>
              <span class="session-time">{{ formatSessionTime(item.updated_at) }}</span>
            </template>
          </van-cell>
          <van-empty v-if="!sessions.length" description="暂无历史会话" />
        </div>
      </div>
    </van-popup>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch, computed } from 'vue';
import TabBar from '../components/TabBar.vue';
import { showToast } from 'vant';
import * as marked from 'marked';
import DOMPurify from 'dompurify';
import { aiChatConfig } from '../config/api';
import { useChatStore } from '../store/modules/chat';
import { useUserStore } from '../store/user';

const chatStore = useChatStore();
const userStore = useUserStore();

const messages = computed(() => chatStore.messages);
const sessions = computed(() => chatStore.sessions);
const currentSessionId = computed(() => chatStore.currentSessionId);

const userInput = ref('');
const messagesContainer = ref(null);
const isLoading = ref(false);
const showSessionPopup = ref(false);

// 从配置文件获取API设置
const apiEndpoint = ref(aiChatConfig.apiEndpoint);
const model = ref(aiChatConfig.model);
const displaySessionId = computed(() => currentSessionId.value || '新会话（未落库）');

const resolveToken = () => {
  // 优先使用 Pinia 状态中的 token
  if (userStore.token) return userStore.token;

  // 兼容历史逻辑：若有独立 token 键则读取
  const directToken = localStorage.getItem('token');
  if (directToken) return directToken;

  // 兼容 pinia-plugin-persistedstate 存储结构（key: user-store）
  const persisted = localStorage.getItem('user-store');
  if (!persisted) return '';
  try {
    const parsed = JSON.parse(persisted);
    return parsed?.token || '';
  } catch {
    return '';
  }
};

// 格式化消息内容（支持Markdown）
const formatMessage = (content) => {
  if (!content) return '';
  // 使用marked解析Markdown，并用DOMPurify清理HTML
  return DOMPurify.sanitize(marked.parse(content));
};

const formatSessionTime = (timeValue) => {
  if (!timeValue) return '';
  const d = new Date(timeValue);
  if (Number.isNaN(d.getTime())) return '';
  const y = d.getFullYear();
  const m = `${d.getMonth() + 1}`.padStart(2, '0');
  const day = `${d.getDate()}`.padStart(2, '0');
  const h = `${d.getHours()}`.padStart(2, '0');
  const min = `${d.getMinutes()}`.padStart(2, '0');
  return `${y}-${m}-${day} ${h}:${min}`;
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return;
  
  // 添加用户消息
  const userMessage = userInput.value.trim();
  chatStore.addMessage({ role: 'user', content: userMessage });
  userInput.value = '';
  
  // 添加AI消息占位
  chatStore.addMessage({ role: 'assistant', content: '' });
  
  // 滚动到底部
  await nextTick();
  scrollToBottom();
  
  // 发送请求
  isLoading.value = true;
  try {
    await fetchAIResponse(userMessage);
  } catch (error) {
    console.error('Error fetching AI response:', error);
    // 更新最后一条消息为错误信息
    chatStore.updateLastAssistantContent(`发生错误: ${error.message || '请检查网络连接和API设置'}`);
  } finally {
    isLoading.value = false;
    chatStore.isStreaming = false;
    await nextTick();
    scrollToBottom();
  }
};

// 获取AI响应（使用SSE）
const fetchAIResponse = async (userMessage) => {
  try {
    const token = resolveToken();
    if (!token) {
      throw new Error('请先登录后再使用AI问答');
    }

    chatStore.isStreaming = true;

    const response = await fetch(apiEndpoint.value, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        model: model.value,
        messages: [{ role: 'user', content: userMessage }],
        stream: true,
        session_id: currentSessionId.value || null,
      })
    });

    const responseSessionId = response.headers.get('X-Session-Id') || response.headers.get('x-session-id');
    if (responseSessionId) {
      chatStore.bindSessionId(responseSessionId);
    }
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(
        error.error?.message ||
        error.detail ||
        error.message ||
        `HTTP error! status: ${response.status}`
      );
    }
    
    // 处理SSE流
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiResponse = '';
  
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') continue;

        try {
          const json = JSON.parse(data);
          if (json?.error?.message) {
            throw new Error(json.error.message);
          }

          // 适配阿里云DashScope的返回格式
          const content = json.choices?.[0]?.delta?.content ||
            json.output?.text ||
            json.choices?.[0]?.message?.content || '';

          if (content) {
            aiResponse += content;
            chatStore.updateLastAssistantContent(aiResponse);
            await nextTick();
            scrollToBottom();
          }
        } catch (e) {
          if (e instanceof Error && e.message) {
            throw e;
          }
          console.error('Error parsing SSE data:', e);
        }
      }
    }
  
    // 如果没有收到任何内容
    if (!aiResponse) {
      chatStore.updateLastAssistantContent('抱歉，我无法生成回复。请检查API设置或稍后再试。');
    }

    if (responseSessionId) {
      await chatStore.fetchSessions();
    }
  } catch (error) {
    console.error('Fetch error:', error);
    throw error;
  }
};

const createNewSession = () => {
  chatStore.resetAsNewSession();
  showSessionPopup.value = false;
  showToast('已创建新会话');
};

const switchSession = async (sessionId) => {
  try {
    await chatStore.fetchSessionMessages(sessionId);
    showSessionPopup.value = false;
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error('switch session failed:', error);
    showToast(error?.response?.data?.detail || '切换会话失败');
  }
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(scrollToBottom);
}, { deep: true });

// 组件挂载时滚动到底部
onMounted(() => {
  (async () => {
    try {
      await chatStore.fetchSessions();
      if (chatStore.currentSessionId) {
        await chatStore.fetchSessionMessages(chatStore.currentSessionId);
      }
    } catch (error) {
      console.error('init chat sessions failed:', error);
    }
    await nextTick();
    scrollToBottom();
  })();
});
</script>

<style scoped>
.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
}

.session-meta {
  padding: 8px 12px;
  background: #f7f8fa;
  border-bottom: 1px solid #eee;
  font-size: 12px;
  color: #666;
}

.session-label {
  color: #333;
  font-weight: 600;
}

.session-id {
  word-break: break-all;
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.message {
  margin-bottom: 10px;
  max-width: 80%;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 10px;
  border-radius: 10px;
  word-break: break-word;
}

.user-message .message-content {
  background-color: #007aff;
  color: white;
}

.ai-message .message-content {
  background-color: #f2f2f2;
  color: #333;
}

.input-container {
  display: flex;
  padding: 10px;
  border-top: 1px solid #eee;
  background-color: #fff;
}

.chat-input {
  flex: 1;
  margin-right: 10px;
}

.send-button {
  align-self: flex-end;
}

.session-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.session-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px;
  border-bottom: 1px solid #eee;
}

.session-panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
}

.session-time {
  color: #999;
  font-size: 11px;
}

/* Markdown 样式 */
.message-content pre {
  background-color: #f8f8f8;
  padding: 10px;
  border-radius: 5px;
  overflow-x: auto;
}

.message-content code {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 4px;
  border-radius: 3px;
}

.message-content img {
  max-width: 100%;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  padding: 5px;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #999;
  border-radius: 50%;
  margin: 0 2px;
  display: inline-block;
  animation: bounce 1.5s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-5px);
  }
}

/* Markdown样式 */
:deep(pre) {
  background-color: #f0f0f0;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

:deep(code) {
  font-family: monospace;
  background-color: #f0f0f0;
  padding: 2px 4px;
  border-radius: 4px;
}

:deep(p) {
  margin: 8px 0;
}

:deep(ul), :deep(ol) {
  padding-left: 20px;
}

:deep(a) {
  color: #1989fa;
  text-decoration: none;
}
</style>