import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '../utils/request'

/**
 * 聊天会话状态管理
 * 功能: 管理会话列表、当前会话、当前任务状态
 */

// 会话接口定义
export interface ChatSession {
  sessionId: string
  userId: string
  sessionTitle: string
  createTime: string
  updateTime: string
}

// 消息接口定义
export interface ChatMessage {
  id?: number
  sessionId: string
  taskId?: string
  traceId?: string
  role: 'user' | 'assistant'
  content: string
  createTime: Date
  status?: string
  requireReview?: boolean
}

export const useChatStore = defineStore('chat', () => {
  // 会话列表
  const sessions = ref<ChatSession[]>([])
  
  // 当前会话 ID
  const currentSessionId = ref<string | null>(null)
  
  // 当前任务 ID（一个 plan 执行期间保持不变）
  const currentTaskId = ref<string | null>(null)
  
  // 当前会话的消息列表
  const messages = ref<ChatMessage[]>([])
  
  // 加载状态
  const loading = ref(false)

  // 计算当前会话
  const currentSession = computed(() => {
    return sessions.value.find(s => s.sessionId === currentSessionId.value)
  })

  /**
   * 获取会话列表
   */
  async function fetchSessions() {
    try {
      loading.value = true
      // request 拦截器已解包，返回的直接是 data 部分（数组）
      const data = await request.get('/ai/chat/sessions') as any
      if (Array.isArray(data)) {
        sessions.value = data.map((item: any) => ({
          sessionId: item.session_id,
          userId: item.user_id,
          sessionTitle: item.session_title,
          createTime: item.create_time,
          updateTime: item.update_time
        }))
      }
    } catch (error) {
      console.error('获取会话列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 创建新会话
   */
  async function createSession(title?: string) {
    try {
      // request 拦截器已解包，返回的直接是 data 对象
      const data = await request.post('/ai/chat/sessions', { title }) as any
      if (data && data.sessionId) {
        const newSession: ChatSession = {
          sessionId: data.sessionId,
          userId: data.userId,
          sessionTitle: data.sessionTitle || '新会话',
          createTime: new Date().toISOString(),
          updateTime: new Date().toISOString()
        }
        sessions.value.unshift(newSession)
        // 自动切换到新会话
        await switchSession(newSession.sessionId)
        return newSession
      }
    } catch (error) {
      console.error('创建会话失败:', error)
    }
    return null
  }

  /**
   * 切换当前会话
   */
  async function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
    currentTaskId.value = null // 重置任务 ID
    messages.value = []
    
    // 加载历史消息
    await fetchMessages(sessionId)
  }

  /**
   * 获取会话历史消息
   */
  async function fetchMessages(sessionId: string) {
    try {
      loading.value = true
      // request 拦截器已解包，返回的直接是 data 部分（数组）
      const data = await request.get(`/ai/chat/sessions/${sessionId}/messages`) as any
      if (Array.isArray(data)) {
        messages.value = data.map((item: any) => ({
          id: item.id,
          sessionId: item.session_id,
          taskId: item.task_id,
          traceId: item.trace_id,
          role: item.role,
          content: item.content,
          createTime: new Date(item.create_time)
        }))
      }
    } catch (error) {
      console.error('获取消息列表失败:', error)
    } finally {
      loading.value = false
    }
  }

  /**
   * 删除会话
   */
  async function deleteSession(sessionId: string) {
    try {
      // request 拦截器已解包，成功时不会抛异常
      await request.delete(`/ai/chat/sessions/${sessionId}`)
      sessions.value = sessions.value.filter(s => s.sessionId !== sessionId)
      // 如果删除的是当前会话，切换到第一个会话或清空
      if (currentSessionId.value === sessionId) {
        if (sessions.value.length > 0) {
          await switchSession(sessions.value[0].sessionId)
        } else {
          currentSessionId.value = null
          messages.value = []
        }
      }
      return true
    } catch (error) {
      console.error('删除会话失败:', error)
    }
    return false
  }

  /**
   * 添加消息到当前会话（仅本地）
   */
  function addMessage(message: ChatMessage) {
    messages.value.push(message)
  }

  /**
   * 将消息持久化到数据库（通过 bus-kernel POST /ai/chat/messages）
   * 异步调用，不阻塞主流程
   */
  async function saveMessageToServer(message: {
    sessionId: string
    taskId?: string
    traceId?: string
    role: string
    content: string
  }) {
    try {
      await request.post('/ai/chat/messages', message)
    } catch (error) {
      console.error('保存消息到服务器失败:', error)
    }
  }

  /**
   * 异步更新会话标题（通过 bus-kernel PUT 接口）
   * 截取内容前 30 个字符作为标题
   */
  async function updateSessionTitle(sessionId: string, title: string) {
    try {
      const trimmedTitle = title.length > 30 ? title.substring(0, 30) + '...' : title
      await request.put(`/ai/chat/sessions/${sessionId}`, { title: trimmedTitle })
      // 同步更新本地会话列表中的标题
      const session = sessions.value.find(s => s.sessionId === sessionId)
      if (session) {
        session.sessionTitle = trimmedTitle
      }
    } catch (error) {
      console.error('更新会话标题失败:', error)
    }
  }

  /**
   * 更新任务 ID
   */
  function setTaskId(taskId: string) {
    currentTaskId.value = taskId
  }

  /**
   * 清空任务 ID（plan 完成后调用）
   */
  function clearTaskId() {
    currentTaskId.value = null
  }

  return {
    sessions,
    currentSessionId,
    currentTaskId,
    messages,
    loading,
    currentSession,
    fetchSessions,
    createSession,
    switchSession,
    fetchMessages,
    deleteSession,
    addMessage,
    saveMessageToServer,
    updateSessionTitle,
    setTaskId,
    clearTaskId
  }
})
