import axios from 'axios'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api/dg', // Proxy will handle this
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
    const res = response.data
    
    // 如果返回的 code 不是 200，说明业务逻辑出错
    if (res.code !== 200) {
      ElMessage.error(res.message || 'Error')
      
      // 401: 未登录或凭证过期
      if (res.code === 401) {
        const userStore = useUserStore()
        userStore.logout()
        location.reload()
      }
      
      return Promise.reject(new Error(res.message || 'Error'))
    } else {
      // 业务逻辑成功，直接返回 data 部分
      return res.data
    }
  },
  (error) => {
    // 处理 HTTP 状态码层面的错误（如网络不通、404、500等）
    if (error.response && error.response.status === 401) {
       const userStore = useUserStore()
       userStore.logout()
       location.reload()
    }
    
    // 获取后端返回的友好提示消息
    const msg = error.response?.data?.message || error.message || '系统异常'
    ElMessage.error(msg)
    
    return Promise.reject(error)
  }
)

export default service
