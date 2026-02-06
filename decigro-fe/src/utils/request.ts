import axios from 'axios'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api', // Proxy will handle this
  timeout: 5000
})

// Request interceptor
service.interceptors.request.use(
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
service.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response && error.response.status === 401) {
       const userStore = useUserStore()
       userStore.logout()
       location.reload()
       return Promise.reject(error)
    }
    
    // 获取后端返回的友好提示消息
    const msg = error.response?.data?.message || error.message || '系统异常'
    ElMessage.error(msg)
    
    return Promise.reject(error)
  }
)

export default service
