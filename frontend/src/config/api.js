/**
 * API配置文件
 * 包含API基础URL和AI问答功能所需的API参数
 */

// API基础URL配置
export const apiConfig = {
  // 后端API基础URL
  baseURL: 'http://127.0.0.1:8000',
}

export const aiChatConfig = {
  // 改为调用后端代理接口，避免在前端暴露真实密钥
  apiEndpoint: `${apiConfig.baseURL}/api/ai/chat`,
  sessionsEndpoint: `${apiConfig.baseURL}/api/ai/sessions`,
  sessionMessagesEndpoint: (sessionId) => `${apiConfig.baseURL}/api/ai/sessions/${sessionId}/messages`,
  
  // 使用的模型
  model: 'qwen3-max-preview'
}
