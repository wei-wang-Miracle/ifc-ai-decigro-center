import axios from 'axios'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const aiService = axios.create({
  baseURL: '/api/v1/workflow',
  timeout: 60000 // AI 请求可能比较慢，设置长一点
})

// Request interceptor
aiService.interceptors.request.use(
  (config) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers['X-Auth-Token'] = userStore.token
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
aiService.interceptors.response.use(
  (response) => {
    // AI Engine 目前可能返回不同的结构，或者直接返回
    // 检查是否有 code (FastAPI 默认不带 code，但我们在 routes.py 中可能自己包装了)
    // 根据 ai-engine/src/ai_engine/api/routes.py:
    // 返回的是模型直接序列化，没有包装 code = 200
    // 但是错误时会 raise HTTPException -> 返回 { "detail": "..." }
    
    return response.data
  },
  (error) => {
    const msg = error.response?.data?.detail || error.message || 'AI 引擎响应异常'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default aiService
