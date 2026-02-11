<script setup lang="ts">
import { ref, nextTick, onMounted, computed, reactive } from 'vue'
import { Promotion, Warning, ChatLineRound, Plus, Delete, ChatDotSquare, Operation, Loading, ArrowDown, Close } from '@element-plus/icons-vue'
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
const agentPanelScroll = ref<HTMLElement | null>(null)
// 控制思考过程展开/收起
const showThoughts = ref<Record<string, boolean>>({})

// ===== Agent 工作面板相关 =====

// Agent 面板是否可见
const agentPanelVisible = ref(false)

// 当前高亮的 Agent 别名（聊天区和面板联动）
const highlightedAgent = ref<string | null>(null)

// Agent 工作日志数据结构
interface AgentWorkEntry {
    id: string
    agentName: string        // Agent 原始名称
    agentAlias: string       // Agent 别名（展示用）
    status: 'running' | 'success' | 'failed'
    startTime: number
    tools: { name: string; alias: string; status: string; output?: string }[]
    thinking: string         // Agent 的思考内容（流式累加）
    result: string           // Agent 最终产出
}

// 当前所有 Agent 工作记录
const agentWorkEntries = reactive<AgentWorkEntry[]>([])

// 当前活跃的 Agent（正在工作中）
const activeAgentName = ref<string | null>(null)

// 计算属性：使用 store 中的消息
const messages = computed(() => chatStore.messages)

// 自动滚动到底部
const scrollToBottom = async () => {
    await nextTick()
    if (scrollContainer.value) {
        scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
}

// Agent 面板自动滚动到底部
const scrollAgentPanelToBottom = async () => {
    await nextTick()
    if (agentPanelScroll.value) {
        agentPanelScroll.value.scrollTop = agentPanelScroll.value.scrollHeight
    }
}

// 点击聊天区中的 Agent 名称，高亮右侧面板对应条目
const handleAgentClick = (agentAlias: string) => {
    highlightedAgent.value = agentAlias
    // 如果面板未展开，自动展开
    if (!agentPanelVisible.value) {
        agentPanelVisible.value = true
    }
    // 滚动到对应 Agent 条目
    nextTick(() => {
        const el = document.getElementById(`agent-entry-${agentAlias}`)
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
    })
    // 3 秒后清除高亮
    setTimeout(() => {
        if (highlightedAgent.value === agentAlias) {
            highlightedAgent.value = null
        }
    }, 3000)
}

// 关闭 Agent 面板
const closeAgentPanel = () => {
    agentPanelVisible.value = false
    highlightedAgent.value = null
}

// 获取当前活跃的 AgentWorkEntry
const getActiveAgent = (): AgentWorkEntry | undefined => {
    return agentWorkEntries.find(e => e.status === 'running')
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
        // 切换会话时清理 Agent 面板
        agentPanelVisible.value = false
        agentWorkEntries.splice(0)
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
    
    // 每次新消息清理上一轮的 Agent 面板数据
    agentPanelVisible.value = false
    agentWorkEntries.splice(0)
    activeAgentName.value = null
    
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
        taskId: undefined,
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
                task_id: chatStore.currentTaskId
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
                                chatStore.setTaskId(event.task_id)

                            } else if (event.type === 'thinking') {
                                // 简单显示"正在思考"

                            } else if (event.type === 'node_start') {
                                // 结束上一个节点的 running 状态
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
                                // ====== Agent 进场：展开右侧面板 ======
                                const agentAlias = event.agent_alias || event.agent
                                const agentName = event.agent
                                
                                // 结束上一个运行中的思考步骤
                                if (aiMessage.thoughts && aiMessage.thoughts.length > 0) {
                                    const last = aiMessage.thoughts[aiMessage.thoughts.length - 1]
                                    if (last.status === 'running') last.status = 'success'
                                }

                                // 在聊天气泡中记录 Agent 启动
                                aiMessage.thoughts?.push({
                                    id: `agent-${Date.now()}-${Math.random()}`,
                                    type: 'agent_start',
                                    title: agentAlias,
                                    status: 'running',
                                    timestamp: Date.now(),
                                    content: ''
                                })

                                // 向右侧 Agent 面板添加工作条目
                                const entry: AgentWorkEntry = {
                                    id: `aw-${Date.now()}`,
                                    agentName,
                                    agentAlias,
                                    status: 'running',
                                    startTime: Date.now(),
                                    tools: [],
                                    thinking: '',
                                    result: ''
                                }
                                agentWorkEntries.push(entry)
                                activeAgentName.value = agentName

                                // 展开 Agent 面板
                                agentPanelVisible.value = true
                                scrollToBottom()
                                scrollAgentPanelToBottom()

                            } else if (event.type === 'tool_start') {
                                // 在聊天思考中记录
                                aiMessage.thoughts?.push({
                                    id: `tool-${Date.now()}-${Math.random()}`,
                                    type: 'tool_start',
                                    title: `执行工具: ${event.tool_alias || event.tool}`,
                                    status: 'running',
                                    timestamp: Date.now()
                                })
                                // 同步到 Agent 面板
                                const activeEntry = getActiveAgent()
                                if (activeEntry) {
                                    activeEntry.tools.push({
                                        name: event.tool,
                                        alias: event.tool_alias || event.tool,
                                        status: 'running'
                                    })
                                }
                                scrollAgentPanelToBottom()

                            } else if (event.type === 'tool_end') {
                                // 更新聊天思考中的工具状态
                                const thought = aiMessage.thoughts?.slice().reverse().find(
                                    t => t.type === 'tool_start' && t.title.includes(event.tool_alias || event.tool)
                                )
                                if (thought) {
                                    thought.status = 'success'
                                }
                                // 同步到 Agent 面板
                                const activeEntry = getActiveAgent()
                                if (activeEntry) {
                                    const tool = activeEntry.tools.slice().reverse().find(
                                        t => t.name === event.tool || t.alias === (event.tool_alias || event.tool)
                                    )
                                    if (tool) {
                                        tool.status = 'success'
                                        tool.output = event.output
                                    }
                                }
                                console.log(`[Tool Result] ${event.tool}:`, event.output)

                            } else if (event.type === 'node_result') {
                                // 标记节点完成
                                const nodeThought = aiMessage.thoughts?.slice().reverse().find(t => t.status === 'running')
                                if (nodeThought) {
                                    nodeThought.status = 'success'
                                }
                                // 如果当前有活跃 Agent，标记其完成
                                const activeEntry = getActiveAgent()
                                if (activeEntry && event.node === 'executor') {
                                    activeEntry.status = 'success'
                                    activeAgentName.value = null
                                }
                                console.log(`[Node Result] ${event.node}:`, event.output)

                            } else if (event.type === 'token') {
                                const { content, reasoning, is_thought, is_json, node } = event

                                // 过滤技术性的 JSON
                                if (is_json) continue

                                if (is_thought) {
                                    // ====== 思考流：分发到聊天气泡 + Agent 面板 ======
                                    let activeThought = aiMessage.thoughts?.slice().reverse().find(t => t.status === 'running')
                                    
                                    if (!activeThought) {
                                        const newThought = {
                                            id: `auto-${Date.now()}`,
                                            type: 'thinking' as const,
                                            title: (node === 'responder' ? '整理思路...' : '深度思考中...'),
                                            status: 'running' as const,
                                            timestamp: Date.now(),
                                            content: ''
                                        }
                                        aiMessage.thoughts?.push(newThought)
                                        activeThought = newThought
                                    }

                                    if (activeThought) {
                                        if (reasoning) activeThought.content += reasoning
                                        else if (content) activeThought.content += content
                                    }

                                    // 同步思考内容到 Agent 面板
                                    const activeEntry = getActiveAgent()
                                    if (activeEntry) {
                                        if (reasoning) activeEntry.thinking += reasoning
                                        else if (content) activeEntry.thinking += content
                                        scrollAgentPanelToBottom()
                                    }
                                    continue
                                }

                                // ====== 正文流 ======
                                if (content) {
                                    // 如果有活跃 Agent，同时追加到 Agent 面板的 result
                                    const activeEntry = getActiveAgent()
                                    if (activeEntry) {
                                        activeEntry.result += content
                                        scrollAgentPanelToBottom()
                                    }
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
                                    // 结束所有运行中的 Agent
                                    agentWorkEntries.forEach(e => {
                                        if (e.status === 'running') e.status = 'success'
                                    })
                                    activeAgentName.value = null
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

        <!-- 中间聊天区域（Agent 进场时宽度比例变为 9:16 ≈ 56%） -->
        <div :class="['chat-container flex flex-col bg-white overflow-hidden transition-all duration-500 ease-in-out',
             agentPanelVisible ? 'chat-area-shrink' : 'flex-1']"
        >
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
                    <div :class="['flex items-start max-w-[85%] space-x-3', msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : '']">
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
                                <!-- 思考过程展示（精简版，详细内容在右侧面板） -->
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
                                    
                                    <div v-show="showThoughts[msg.id || idx] || msg.status === 'running'" class="mt-2 text-xs space-y-1.5 bg-slate-50 p-2 rounded max-h-48 overflow-y-auto">
                                        <div v-for="thought in msg.thoughts" :key="thought.id" class="flex items-center">
                                            <div class="mr-2">
                                                <div v-if="thought.status === 'running'" class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                                                <div v-else-if="thought.type === 'node_start'" class="w-2 h-2 rounded-full bg-purple-400"></div>
                                                <div v-else-if="thought.type === 'agent_start'" class="w-2 h-2 rounded-full bg-indigo-400"></div>
                                                <div v-else-if="thought.type === 'tool_start'" class="w-2 h-2 rounded-full bg-amber-400"></div>
                                                <div v-else class="w-2 h-2 rounded-full bg-green-400"></div>
                                            </div>
                                            <div class="flex-1 min-w-0">
                                                <!-- Agent 名称可点击：联动右侧面板 -->
                                                <span 
                                                    v-if="thought.type === 'agent_start'"
                                                    class="font-medium text-indigo-600 cursor-pointer hover:underline"
                                                    @click="handleAgentClick(thought.title)"
                                                >
                                                    🤖 {{ thought.title }}
                                                </span>
                                                <span v-else class="font-medium text-gray-700 truncate">{{ thought.title }}</span>
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

        <!-- ====== 右侧 Agent 工作面板 ====== -->
        <transition name="agent-panel">
            <div v-if="agentPanelVisible" class="agent-panel border-l border-gray-200 bg-slate-50 flex flex-col overflow-hidden">
                <!-- 面板头部 -->
                <div class="px-4 py-3 border-b bg-white flex items-center justify-between">
                    <div class="flex items-center space-x-2">
                        <div class="w-7 h-7 rounded-lg bg-indigo-100 flex items-center justify-center">
                            <span class="text-sm">🤖</span>
                        </div>
                        <div>
                            <h3 class="text-sm font-bold text-gray-800">Agent 工作台</h3>
                            <p class="text-[10px] text-gray-400">智能体思考与执行过程</p>
                        </div>
                    </div>
                    <el-button :icon="Close" circle size="small" @click="closeAgentPanel" class="close-panel-btn" />
                </div>

                <!-- 面板内容：Agent 工作条目列表 -->
                <div ref="agentPanelScroll" class="flex-1 overflow-y-auto p-3 space-y-3">
                    <div v-if="agentWorkEntries.length === 0" class="text-center text-gray-400 text-xs py-12">
                        等待 Agent 进场...
                    </div>

                    <div 
                        v-for="entry in agentWorkEntries" 
                        :key="entry.id"
                        :id="`agent-entry-${entry.agentAlias}`"
                        :class="[
                            'agent-work-card rounded-xl p-3 border transition-all duration-300',
                            highlightedAgent === entry.agentAlias 
                                ? 'border-indigo-400 bg-indigo-50 ring-2 ring-indigo-200 shadow-md' 
                                : 'border-gray-200 bg-white shadow-sm',
                            entry.status === 'running' ? 'agent-card-active' : ''
                        ]"
                    >
                        <!-- Agent 头部 -->
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center space-x-2">
                                <div :class="['w-6 h-6 rounded-full flex items-center justify-center text-xs',
                                    entry.status === 'running' ? 'bg-indigo-500 text-white' : 'bg-green-500 text-white']">
                                    <span v-if="entry.status === 'running'" class="animate-pulse">⚡</span>
                                    <span v-else>✓</span>
                                </div>
                                <span class="text-sm font-semibold text-gray-800">{{ entry.agentAlias }}</span>
                            </div>
                            <el-tag 
                                :type="entry.status === 'running' ? 'primary' : 'success'" 
                                size="small" 
                                effect="dark"
                                round
                            >
                                {{ entry.status === 'running' ? '执行中' : '已完成' }}
                            </el-tag>
                        </div>

                        <!-- 工具调用 -->
                        <div v-if="entry.tools.length > 0" class="mb-2">
                            <div class="text-[10px] text-gray-500 font-medium mb-1 uppercase tracking-wider">工具调用</div>
                            <div class="space-y-1">
                                <div v-for="(tool, tidx) in entry.tools" :key="tidx" 
                                    class="flex items-center text-xs py-1 px-2 rounded bg-gray-50">
                                    <div :class="['w-1.5 h-1.5 rounded-full mr-2',
                                        tool.status === 'running' ? 'bg-amber-500 animate-pulse' : 'bg-green-500']"></div>
                                    <span class="text-gray-700">{{ tool.alias }}</span>
                                    <span v-if="tool.status === 'success'" class="ml-auto text-green-600">✓</span>
                                    <el-icon v-else class="ml-auto animate-spin text-gray-400"><Loading /></el-icon>
                                </div>
                            </div>
                        </div>

                        <!-- 思考过程 -->
                        <div v-if="entry.thinking" class="mb-2">
                            <div class="text-[10px] text-gray-500 font-medium mb-1 uppercase tracking-wider">思考过程</div>
                            <div class="text-xs text-gray-600 bg-gradient-to-br from-slate-50 to-indigo-50/30 p-2 rounded-lg max-h-40 overflow-y-auto font-mono leading-relaxed whitespace-pre-wrap break-all">
                                {{ entry.thinking }}
                                <span v-if="entry.status === 'running'" class="inline-block w-1.5 h-3 bg-indigo-400 animate-pulse ml-0.5 align-middle"></span>
                            </div>
                        </div>

                        <!-- 产出结果 -->
                        <div v-if="entry.result">
                            <div class="text-[10px] text-gray-500 font-medium mb-1 uppercase tracking-wider">执行产出</div>
                            <div class="text-xs text-gray-700 bg-white border border-gray-100 p-2 rounded-lg max-h-60 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                                {{ entry.result }}
                            </div>
                        </div>

                        <!-- 空状态 -->
                        <div v-if="!entry.thinking && !entry.result && entry.tools.length === 0" 
                            class="text-center text-gray-400 text-xs py-4">
                            <el-icon class="animate-spin mb-1"><Loading /></el-icon>
                            <p>Agent 正在启动...</p>
                        </div>
                    </div>
                </div>
            </div>
        </transition>
    </div>
</template>

<style scoped>
.chat-page {
    height: 100%;
}

/* ===== 聊天区域收缩动画 ===== */
.chat-area-shrink {
    /* 9:16 ≈ 56.25%，减去左侧侧边栏后的比例 */
    flex: 0 0 56%;
    min-width: 0;
}

/* ===== Agent 面板 ===== */
.agent-panel {
    flex: 1;
    min-width: 320px;
    max-width: 44%;
}

/* 面板入场/离场动画 */
.agent-panel-enter-active {
    animation: slideInRight 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.agent-panel-leave-active {
    animation: slideOutRight 0.3s cubic-bezier(0.4, 0, 1, 1);
}

@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes slideOutRight {
    from {
        transform: translateX(0);
        opacity: 1;
    }
    to {
        transform: translateX(100%);
        opacity: 0;
    }
}

/* 活跃 Agent 卡片左侧发光边框 */
.agent-card-active {
    border-left: 3px solid #6366f1;
    background: linear-gradient(135deg, #f8faff 0%, #eef2ff 100%);
}

/* 高亮联动时的缩放效果 */
.agent-work-card {
    transition: all 0.3s ease;
}

.agent-work-card:hover {
    box-shadow: 0 2px 12px rgba(99, 102, 241, 0.15);
}

/* 关闭按钮 */
.close-panel-btn {
    border: none;
    background: transparent;
    color: #94a3b8;
}

.close-panel-btn:hover {
    color: #475569;
    background: #f1f5f9;
}

/* ===== 原有样式 ===== */
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
