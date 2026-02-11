<script setup lang="ts">
import { ref, nextTick, onMounted, computed, reactive } from 'vue'
import { Promotion, Warning, ChatLineRound, Plus, Delete, ChatDotSquare, Operation, Loading, ArrowDown } from '@element-plus/icons-vue'
import aiRequest from '../../utils/aiRequest'
import { useUserStore } from '../../stores/user'
import { useChatStore, type ChatMessage } from '../../stores/chatStore'
import { useAppStore } from '../../stores/app'
import { ElMessage, ElMessageBox } from 'element-plus'

const userStore = useUserStore()
const chatStore = useChatStore()
const appStore = useAppStore()
const inputMessage = ref('')
const isLoading = ref(false)
const scrollContainer = ref<HTMLElement | null>(null)
// 控制思考过程展开/收起
const showThoughts = ref<Record<string, boolean>>({})

// 计算属性：使用 store 中的消息
const messages = computed(() => chatStore.messages)

// 自动滚动到底部
const scrollToBottom = async () => {
    await nextTick()
    if (scrollContainer.value) {
        scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
}

// 初始化：加载会话列表 + 自动收起侧边栏
onMounted(async () => {
    // 自动收起侧边栏以提供沉浸式对话体验
    appStore.setSidebarCollapsed(true)
    
    await chatStore.fetchSessions()
    // 如果有会话，自动选中第一个
    if (chatStore.sessions.length > 0) {
        await chatStore.switchSession(chatStore.sessions[0].sessionId)
    }
})

// 新建会话
const handleNewSession = async () => {
    const session = await chatStore.createSession()
    if (session) {
        ElMessage.success('已创建新会话')
    }
}

// 删除会话
const handleDeleteSession = async (sessionId: string) => {
    try {
        await ElMessageBox.confirm('确定要删除这个会话吗？', '提示', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
        })
        const success = await chatStore.deleteSession(sessionId)
        if (success) {
            ElMessage.success('会话已删除')
        }
    } catch {
        // 取消删除
    }
}

// 切换会话
const handleSwitchSession = async (sessionId: string) => {
    if (sessionId !== chatStore.currentSessionId) {
        await chatStore.switchSession(sessionId)
        scrollToBottom()
    }
}

// 发送消息
const handleSend = async () => {
    if (!inputMessage.value.trim() || isLoading.value) return

    // 确保有当前会话
    if (!chatStore.currentSessionId) {
        const session = await chatStore.createSession()
        if (!session) {
            ElMessage.error('创建会话失败')
            return
        }
    }

    const userQuery = inputMessage.value
    inputMessage.value = ''
    
    // 添加用户消息
    const userMessage = reactive<ChatMessage>({
        sessionId: chatStore.currentSessionId!,
        taskId: chatStore.currentTaskId || undefined,
        role: 'user',
        content: userQuery,
        createTime: new Date()
    })
    chatStore.addMessage(userMessage)

    // 异步持久化用户消息到数据库（通过 bus-kernel）
    chatStore.saveMessageToServer({
        sessionId: chatStore.currentSessionId!,
        taskId: chatStore.currentTaskId || undefined,
        role: 'user',
        content: userQuery
    })

    // 首条消息发送后，异步更新会话标题为消息内容（通过 bus-kernel PUT 接口）
    if (chatStore.messages.length === 1 && chatStore.currentSession?.sessionTitle === '新会话') {
        chatStore.updateSessionTitle(chatStore.currentSessionId!, userQuery)
    }
    
    isLoading.value = true
    scrollToBottom()

    // 添加 AI 消息占位
    const aiMessage = reactive<ChatMessage>({
        sessionId: chatStore.currentSessionId!,
        taskId: undefined, // 暂时未定
        traceId: undefined,
        role: 'assistant',
        content: '',
        createTime: new Date(),
        status: 'running',
        requireReview: false,
        thoughts: []
    })
    chatStore.addMessage(aiMessage)
    
    isLoading.value = true
    scrollToBottom()

    try {
        // 使用 fetch 获取流式响应
        const response = await fetch('/api/v1/workflow/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Auth-Token': userStore.token || ''
            },
            body: JSON.stringify({
                query: userQuery,
                user_id: userStore.userInfo.userId || userStore.userInfo.username || 'guest',
                session_id: chatStore.currentSessionId,
                task_id: chatStore.currentTaskId // 传递当前任务 ID（如果有）
            })
        })

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        
        if (!reader) throw new Error('ReadableStream not supported')

        let partialLine = ''
        
        while (true) {
            const { done, value } = await reader.read()
            if (done) break
            
            const chunk = decoder.decode(value, { stream: true })
            const lines = (partialLine + chunk).split('\n\n')
            partialLine = lines.pop() || ''
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.slice(6)
                    if (dataStr === '[DONE]') continue
                    
                        try {
                            const event = JSON.parse(dataStr)
                            console.log('[SSE Event]', event)
                            
                            // 处理不同类型的事件
                            if (event.type === 'meta') {
                                aiMessage.taskId = event.task_id
                                aiMessage.traceId = event.trace_id
                                // 确保 taskId 用于消息映射
                                chatStore.setTaskId(event.task_id)
                            } else if (event.type === 'thinking') {
                                // 简单显示“正在思考”
                            } else if (event.type === 'node_start') {
                                // 先结束上一个节点的 running 状态
                                if (aiMessage.thoughts && aiMessage.thoughts.length > 0) {
                                    const last = aiMessage.thoughts[aiMessage.thoughts.length - 1]
                                    if (last.status === 'running') last.status = 'success'
                                }
                                
                                aiMessage.thoughts?.push({
                                    id: `node-${Date.now()}-${Math.random()}`,
                                    type: 'node_start',
                                    title: event.display_name || event.node,
                                    status: 'running',
                                    timestamp: Date.now(),
                                    content: ''
                                })
                            } else if (event.type === 'agent_start') {
                                if (aiMessage.thoughts && aiMessage.thoughts.length > 0) {
                                    const last = aiMessage.thoughts[aiMessage.thoughts.length - 1]
                                    if (last.status === 'running') last.status = 'success'
                                }

                                aiMessage.thoughts?.push({
                                    id: `agent-${Date.now()}-${Math.random()}`,
                                    type: 'agent_start',
                                    title: `Agent: ${event.agent_alias || event.agent}`,
                                    status: 'running',
                                    timestamp: Date.now(),
                                    content: ''
                                })
                                scrollToBottom()
                            } else if (event.type === 'tool_start') {
                                aiMessage.thoughts?.push({
                                    id: `tool-${Date.now()}-${Math.random()}`,
                                    type: 'tool_start',
                                    title: `执行工具: ${event.tool_alias || event.tool}`,
                                    status: 'running',
                                    timestamp: Date.now()
                                })
                            } else if (event.type === 'tool_end') {
                                // 找到对应的 tool_start 并更新
                                const thought = aiMessage.thoughts?.slice().reverse().find(t => t.type === 'tool_start' && t.title.includes(event.tool_alias || event.tool))
                                if (thought) {
                                    thought.status = 'success'
                                    // 节点的输出结果存于日志或内部状态，依用户要求“不必展示节点的输出结果”
                                    console.log(`[Tool Result] ${event.tool}:`, event.output)
                                }
                            } else if (event.type === 'node_result') {
                                // 节点执行结果：标记当前节点为成功，并记录日志，不展示在 UI 思考过程内容中
                                const nodeThought = aiMessage.thoughts?.slice().reverse().find(t => t.status === 'running')
                                if (nodeThought) {
                                    nodeThought.status = 'success'
                                }
                                console.log(`[Node Result] ${event.node}:`, event.output)
                            } else if (event.type === 'token') {
                                const { content, reasoning, is_thought, is_json } = event
                                
                                // 规则 1: 如果是 JSON 数据，标记为 is_thought 也不在 UI 思考框中追加
                                if (is_json) continue

                                if (is_thought) {
                                    // 规则 2: 思考过程流 -> 进入思考步骤详情
                                    const agentThought = aiMessage.thoughts?.slice().reverse().find(t => t.status === 'running')
                                    if (agentThought) {
                                        if (!agentThought.content) agentThought.content = ''
                                        if (reasoning) agentThought.content += reasoning
                                        else if (content) agentThought.content += content
                                    }
                                    continue
                                }

                                // 规则 3: 非思考过程 (is_thought === false) -> 直接进入聊天正文
                                if (content) {
                                    aiMessage.content += content
                                    scrollToBottom()
                                }
                            } else if (event.type === 'result') {
                                if (event.message) {
                                    aiMessage.content = event.message
                                }
                                aiMessage.status = event.status
                                aiMessage.requireReview = event.require_review
                                
                                 // 异步持久化 AI 回复到数据库
                                chatStore.saveMessageToServer({
                                    sessionId: chatStore.currentSessionId!,
                                    taskId: event.task_id,
                                    traceId: aiMessage.traceId,
                                    role: 'assistant',
                                    content: event.message,
                                    thoughts: aiMessage.thoughts
                                })

                                if (event.status === 'completed') {
                                    chatStore.clearTaskId()
                                }
                            }
                            
                            scrollToBottom()
                        } catch (e) {
                            console.warn('Parse SSE error:', e)
                        }
                }
            }
        }
        
    } catch (error) {
        console.error('Chat error:', error)
        ElMessage.error('发送消息失败')
        
        // 更新消息状态为失败
        aiMessage.content = '抱歉，响应过程中出现错误。'
        aiMessage.status = 'failed'
    } finally {
        isLoading.value = false
        scrollToBottom()
    }
}

// 处理审核
const handleReview = async (taskId: string, action: 'approve' | 'reject') => {
    try {
        const res = await aiRequest.post(`/review/${taskId}`, {
            action,
            feedback: action === 'reject' ? '已被用户驳回' : '通过'
        }) as any

        // 更新消息状态
        const msg = messages.value.find(m => m.taskId === taskId && m.requireReview)
        if (msg) {
            msg.content = res.message
            msg.status = res.status
            msg.requireReview = false
        }
        
        ElMessage.success(`操作成功: ${action === 'approve' ? '已批准' : '已驳回'}`)
    } catch (error) {
        console.error('Review error:', error)
        ElMessage.error('审核操作失败')
    }
}

// 格式化时间
const formatTime = (date: Date | string) => {
    const d = typeof date === 'string' ? new Date(date) : date
    return d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
}
</script>

<template>
    <div class="chat-page flex h-full">
        <!-- 左侧会话列表 -->
        <div class="session-sidebar w-38 bg-slate-50 border-r border-gray-200 flex flex-col">
            <!-- 新建会话按钮 -->
            <div class="p-3 border-b border-gray-200">
                <el-button type="primary" class="w-full" size="default" @click="handleNewSession">
                    <el-icon class="mr-1"><Plus /></el-icon>
                    新建会话
                </el-button>
            </div>
            
            <!-- 会话列表 -->
            <div class="flex-1 overflow-y-auto p-2 space-y-0.5">
                <div v-if="chatStore.sessions.length === 0" class="text-center text-gray-400 text-xs py-8">
                    暂无会话
                </div>
                <div
                    v-for="session in chatStore.sessions"
                    :key="session.sessionId"
                    :class="[
                        'session-item group flex items-center justify-between p-2 px-3 rounded-lg cursor-pointer transition-all',
                        session.sessionId === chatStore.currentSessionId
                            ? 'bg-brand-100 text-brand-700 font-medium'
                            : 'hover:bg-gray-100 text-gray-600'
                    ]"
                    @click="handleSwitchSession(session.sessionId)"
                >
                    <div class="flex items-center space-x-2 flex-1 min-w-0">
                        <el-icon :size="14" class="flex-shrink-0"><ChatDotSquare /></el-icon>
                        <span class="truncate text-xs">{{ session.sessionTitle }}</span>
                    </div>
                    <el-button
                        type="danger"
                        size="small"
                        link
                        :icon="Delete"
                        class="opacity-0 group-hover:opacity-100 transition-opacity p-0 h-auto"
                        @click.stop="handleDeleteSession(session.sessionId)"
                    />
                </div>
            </div>
        </div>

        <!-- 右侧聊天区域 -->
        <div class="chat-container flex-1 flex flex-col bg-white overflow-hidden">
            <!-- 头部 -->
            <div class="px-6 py-4 border-b bg-slate-50 flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center text-white shadow-lg">
                        <el-icon size="20"><Promotion /></el-icon>
                    </div>
                    <div>
                        <h2 class="text-base font-bold text-gray-800">
                            {{ chatStore.currentSession?.sessionTitle || 'AI 智能助理' }}
                        </h2>
                        <p class="text-xs text-gray-400">基于 LangGraph 的多智能体协作平台</p>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <el-tag v-if="chatStore.currentTaskId" size="small" type="info" effect="plain">
                        任务: {{ chatStore.currentTaskId.substring(0, 12) }}...
                    </el-tag>
                    <el-tag size="small" type="success" effect="plain">内核已连接</el-tag>
                    <el-tag size="small" type="primary" effect="plain">Kimi Engine</el-tag>
                </div>
            </div>

            <!-- 消息区域 -->
            <div ref="scrollContainer" class="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/30">
                <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center space-y-4">
                    <div class="w-16 h-16 bg-brand-50 rounded-2xl flex items-center justify-center mb-2">
                        <el-icon class="text-brand-600 text-2xl"><ChatLineRound /></el-icon>
                    </div>
                    <h3 class="text-lg font-bold text-gray-700">您好, {{ userStore.userInfo.username }}</h3>
                    <p class="text-sm text-gray-400 max-w-sm">我可以为您处理复杂的业务流程，例如标签挖掘、自动化管理和数据分析。您可以尝试输入指令开始聊天。</p>
                    <div class="flex gap-2 mt-4">
                        <button @click="inputMessage = '帮我查询所有客户标签'; handleSend()" class="btn-suggest">查询标签</button>
                        <button @click="inputMessage = '目前有哪些可用的智能体？'; handleSend()" class="btn-suggest">可用 Agent</button>
                    </div>
                </div>

                <div v-for="(msg, idx) in messages" :key="idx" 
                    :class="['flex w-full', msg.role === 'user' ? 'justify-end' : 'justify-start']"
                >
                    <div :class="['flex items-start max-w-[80%] space-x-3', msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : '']">
                        <!-- 头像 -->
                        <div :class="['w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center shadow-sm', 
                            msg.role === 'user' ? 'bg-brand-100 text-brand-700' : 'bg-brand-600 text-white']"
                        >
                            <el-icon v-if="msg.role === 'assistant'"><Promotion /></el-icon>
                            <span v-else class="text-xs font-bold">{{ userStore.userInfo.username?.[0]?.toUpperCase() }}</span>
                        </div>

                        <!-- 气泡 -->
                        <div class="space-y-1">
                            <div :class="['px-4 py-3 rounded-2xl text-sm shadow-sm relative', 
                                msg.role === 'user' 
                                    ? 'bg-brand-600 text-white rounded-tr-none' 
                                    : 'bg-white text-slate-700 border border-slate-100 rounded-tl-none']"
                            >
                                <!-- 思考过程展示 -->
                                <div v-if="msg.thoughts && msg.thoughts.length > 0" class="mb-3 border-b border-dashed border-gray-200 pb-2">
                                    <div 
                                        class="flex items-center text-xs text-gray-500 cursor-pointer hover:text-brand-600 select-none"
                                        @click="showThoughts[msg.id || idx] = !showThoughts[msg.id || idx]"
                                    >
                                        <el-icon class="mr-1 animate-spin" v-if="msg.status === 'running'"><Loading /></el-icon>
                                        <el-icon class="mr-1" v-else><Operation /></el-icon>
                                        <span>思考过程 ({{ msg.thoughts.length }} 步骤)</span>
                                        <el-icon class="ml-1 transition-transform" :class="{ 'rotate-180': showThoughts[msg.id || idx] }"><ArrowDown /></el-icon>
                                    </div>
                                    
                                    <div v-show="showThoughts[msg.id || idx] || msg.status === 'running'" class="mt-2 text-xs space-y-2 bg-slate-50 p-2 rounded max-h-60 overflow-y-auto">
                                        <div v-for="thought in msg.thoughts" :key="thought.id" class="flex items-start">
                                            <div class="mr-2 mt-0.5">
                                                <div v-if="thought.status === 'running'" class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                                                <div v-else-if="thought.type === 'node_start'" class="w-2 h-2 rounded-full bg-purple-400"></div>
                                                <div v-else-if="thought.type === 'agent_start'" class="w-2 h-2 rounded-full bg-indigo-400"></div>
                                                <div v-else-if="thought.type === 'tool_start'" class="w-2 h-2 rounded-full bg-amber-400"></div>
                                                <div v-else class="w-2 h-2 rounded-full bg-green-400"></div>
                                            </div>
                                            <div class="flex-1">
                                                <div class="font-medium text-gray-700">{{ thought.title }}</div>
                                                <div v-if="thought.content" class="text-gray-400 mt-1 font-mono text-[10px] whitespace-pre-wrap break-all">{{ thought.content }}</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="whitespace-pre-wrap leading-relaxed min-h-[1.5em]">{{ msg.content || (msg.status === 'running' ? '...' : '') }}</div>
                                
                                <!-- 审核区域 -->
                                <div v-if="msg.requireReview" class="mt-4 pt-4 border-t border-dashed border-slate-100">
                                    <p class="text-[11px] font-bold text-amber-600 mb-3 flex items-center uppercase tracking-wider">
                                        <el-icon class="mr-1"><Warning /></el-icon> 人工审核确认
                                    </p>
                                    <div class="flex space-x-3">
                                        <el-button type="success" size="small" @click="handleReview(msg.taskId!, 'approve')" plain>批准执行</el-button>
                                        <el-button type="danger" size="small" @click="handleReview(msg.taskId!, 'reject')" plain>驳回并中断</el-button>
                                    </div>
                                </div>
                            </div>
                            <div :class="['text-[10px] text-gray-400 px-1', msg.role === 'user' ? 'text-right' : 'text-left']">
                                {{ formatTime(msg.createTime) }}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 加载 -->
                <div v-if="isLoading" class="flex justify-start items-center space-x-2">
                    <div class="bg-white border border-slate-100 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm">
                        <div class="flex space-x-1.5">
                            <div class="w-1.5 h-1.5 bg-brand-300 rounded-full animate-bounce"></div>
                            <div class="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce delay-150"></div>
                            <div class="w-1.5 h-1.5 bg-brand-500 rounded-full animate-bounce delay-300"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 输入区域 -->
            <div class="p-6 bg-white border-t border-gray-100">
                <div class="relative flex items-end space-x-3 bg-slate-50 rounded-2xl p-2 pr-3 border border-gray-200 focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-50 transition-all">
                    <el-input
                        v-model="inputMessage"
                        type="textarea"
                        :rows="1"
                        autosize
                        placeholder="输入您的指令，按 Enter 发送..."
                        class="chat-input"
                        resize="none"
                        @keydown.enter.prevent="handleSend"
                    />
                    <el-button 
                        type="primary" 
                        circle 
                        :icon="Promotion" 
                        class="send-btn"
                        :loading="isLoading"
                        :disabled="!inputMessage.trim()"
                        @click="handleSend"
                    />
                </div>
                <p class="text-[10px] text-gray-400 mt-2 text-center">AI 引擎由 DeciGro 业务内核驱动，所有敏感操作均受安全策略限制。</p>
            </div>
        </div>
    </div>
</template>

<style scoped>
.chat-page {
    height: 100%;
}


.session-item:hover .el-button {
    opacity: 1;
}

.chat-input :deep(.el-textarea__inner) {
    background-color: transparent;
    border: none;
    box-shadow: none;
    padding-top: 8px;
    padding-bottom: 8px;
    font-size: 14px;
}

.btn-suggest {
    padding: 6px 14px;
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    font-size: 12px;
    color: #475569;
    transition: all 0.2s;
}

.btn-suggest:hover {
    border-color: #174EA6;
    color: #174EA6;
    background: #f0f7ff;
}

.send-btn {
    width: 36px;
    height: 36px;
    background-color: #174EA6;
    border-color: #174EA6;
}

.send-btn:hover {
    background-color: #1a5ac1;
    border-color: #1a5ac1;
}

.animate-bounce {
    animation: bounce 1s infinite;
}

@keyframes bounce {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-4px); }
}

.delay-150 { animation-delay: 0.15s; }
.delay-300 { animation-delay: 0.3s; }
</style>
