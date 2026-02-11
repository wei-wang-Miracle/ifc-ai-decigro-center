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
const agentPanelScroll = ref<HTMLElement | null>(null)
// 控制思考过程展开/收起
const showThoughts = ref<Record<string, boolean>>({})
// 控制 Agent 面板中思考过程的展开/收起
const expandedThinking = ref<Record<string, boolean>>({})

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
const handleAgentClick = (agentAlias: string, msg?: ChatMessage) => {
    // 如果消息带有持久化的 Agent 日志，且当前面板为空或版本不一致，则进行恢复
    if (msg && msg.agentLog && msg.agentLog.length > 0) {
        // 如果当前是空或者是历史会话刚刚加载，我们恢复该条消息关联的 Agent 日志
        // 只有在非运行状态下才覆盖，避免干扰当前正在进行的流
        if (!isLoading.value) {
            agentWorkEntries.splice(0, agentWorkEntries.length, ...msg.agentLog)
            // 恢复历史记录时，重置所有展示状态为收起
            expandedThinking.value = {}
        }
    }

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
        await handleSwitchSession(chatStore.sessions[0].sessionId)
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
        // 切换会话时清理 Agent 面板，但尝试从历史消息中恢复最后一次 Agent 活动
        agentPanelVisible.value = false
        agentWorkEntries.splice(0)
        expandedThinking.value = {}

        // 查找最后一条带有 Agent 日志的消息进行恢复，保证刷新后依然有内容
        const lastAssistantMsg = [...chatStore.messages].reverse().find(m => m.role === 'assistant' && m.agentLog && m.agentLog.length > 0)
        if (lastAssistantMsg && lastAssistantMsg.agentLog) {
            agentWorkEntries.push(...lastAssistantMsg.agentLog)
        }
        
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
    expandedThinking.value = {}
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
                                    thoughts: aiMessage.thoughts,
                                    agentLog: [...agentWorkEntries]
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
                                                    @click="handleAgentClick(thought.title, msg)"
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
            <div v-if="agentPanelVisible" class="agent-panel flex flex-col overflow-hidden">
                <!-- 面板头部：回滚至深受喜欢的工牌条风格 -->
                <div class="ap-header">
                    <div class="ap-header-left">
                        <div class="ap-header-icon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                        </div>
                        <div>
                            <div class="ap-header-title">协作面板</div>
                            <div class="ap-header-sub">{{ agentWorkEntries.length }} 位同事参与中</div>
                        </div>
                    </div>
                    <button class="ap-close-btn" @click="closeAgentPanel" title="关闭面板">✕</button>
                </div>

                <!-- 面板内容：结构化流 -->
                <div ref="agentPanelScroll" class="ap-scroll-flat">
                    <!-- 空状态 -->
                    <div v-if="agentWorkEntries.length === 0" class="ap-empty-flat">
                        <p>等待指令分发...</p>
                    </div>

                    <!-- Agent 汇报条目 -->
                    <div 
                        v-for="entry in agentWorkEntries" 
                        :key="entry.id"
                        :id="`agent-entry-${entry.agentAlias}`"
                        :class="['ap-entry-flat', { 'ap-entry-highlight': highlightedAgent === entry.agentAlias }]"
                    >
                        <!-- 身份区：极简水平排版 -->
                        <div class="ap-id-flat">
                            <img 
                                :src="`https://api.dicebear.com/9.x/notionists/svg?seed=${entry.agentName}`" 
                                class="ap-avatar-flat"
                            />
                            <div class="ap-info-flat">
                                <div class="ap-name-wrap">
                                    <span class="ap-name-main">{{ entry.agentAlias }}</span>
                                    <span class="ap-name-tag">{{ entry.agentName }}</span>
                                </div>
                                <div class="ap-status-line">
                                    <span :class="['ap-indicator', entry.status === 'running' ? 'is-running' : 'is-done']"></span>
                                    <span class="ap-status-text">{{ entry.status === 'running' ? '正在执行任务' : '执行已终结' }}</span>
                                </div>
                            </div>
                        </div>

                        <!-- 结构化任务流 -->
                        <div class="ap-flow-flat">
                            <!-- 工具调用 -->
                            <div v-if="entry.tools.length > 0" class="ap-section-flat">
                                <div class="ap-section-head">调用 / TOOLS</div>
                                <div class="ap-tool-box-flat">
                                    <div v-for="(tool, tidx) in entry.tools" :key="tidx" class="ap-tool-item-flat">
                                        <span :class="['ap-tool-status', tool.status === 'running' ? 'is-tool-running' : 'is-tool-done']"></span>
                                        <span class="ap-tool-label">{{ tool.alias }}</span>
                                        <span v-if="tool.status === 'success'" class="ap-tool-result-tag">OK</span>
                                    </div>
                                </div>
                            </div>

                            <!-- 思考内容：弱化显示 & 完成后自动折叠 -->
                            <div v-if="entry.thinking" class="ap-section-flat has-thought">
                                <div class="ap-section-head flex justify-between items-center group">
                                    <span>逻辑 / THINKING</span>
                                    <button 
                                        v-if="entry.status !== 'running'"
                                        class="ap-toggle-btn"
                                        @click="expandedThinking[entry.id || entry.agentName] = !expandedThinking[entry.id || entry.agentName]"
                                    >
                                        {{ expandedThinking[entry.id || entry.agentName] ? '收起更多记录' : '展开全文' }}
                                    </button>
                                </div>
                                <div :class="['ap-thought-text-flat', { 'is-collapsed': entry.status !== 'running' && !expandedThinking[entry.id || entry.agentName] }]">
                                    {{ entry.thinking }}
                                    <span v-if="entry.status === 'running'" class="ap-cursor-flat">_</span>
                                </div>
                            </div>

                            <!-- 执行结果 -->
                            <div v-if="entry.result" class="ap-section-flat has-result">
                                <div class="ap-section-head">汇总 / REPORT</div>
                                <div class="ap-result-text-flat">{{ entry.result }}</div>
                            </div>

                            <!-- 启动占位 -->
                            <div v-if="!entry.thinking && !entry.result && entry.tools.length === 0" class="ap-section-waiting">
                                初始化环境中...
                            </div>
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

/* ===== 布局收缩 ===== */
.chat-area-shrink {
    flex: 0 0 54%;
    min-width: 0;
}

/* ===== Agent 面板 ===== */
.agent-panel {
    flex: 1;
    min-width: 340px;
    max-width: 46%;
    background: #ffffff;
    border-left: 1px solid #f0f0f0;
}

.agent-panel-enter-active { animation: slideIn 0.3s ease-out; }
.agent-panel-leave-active { animation: slideOut 0.2s ease-in; }

@keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
@keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(20px); opacity: 0; } }

/* === 面板头部：工牌卡片风格 === */
.ap-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    background: #fff;
    border-bottom: 1px solid #eaeef3;
}
.ap-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}
.ap-header-icon {
    width: 32px;
    height: 32px;
    background: #1a1a1a;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
}
.ap-header-title {
    font-size: 14px;
    font-weight: 800;
    color: #1a202c;
    letter-spacing: -0.3px;
}
.ap-header-sub {
    font-size: 11px;
    color: #94a3b8;
}
.ap-close-btn {
    width: 28px;
    height: 28px;
    border: none;
    background: transparent;
    border-radius: 6px;
    color: #94a3b8;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
}
.ap-close-btn:hover {
    background: #f1f5f9;
    color: #475569;
}

/* === 滚动与内容 === */
.ap-scroll-flat { flex: 1; overflow-y: auto; padding: 24px; }
.ap-empty-flat { text-align: center; margin-top: 100px; color: #ccc; font-size: 12px; }

.ap-entry-flat { margin-bottom: 40px; transition: opacity 0.3s; }

/* 身份区 */
.ap-id-flat { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.ap-avatar-flat { width: 32px; height: 32px; border-radius: 6px; background: #f5f7f9; }
.ap-info-flat { flex: 1; }
.ap-name-wrap { display: flex; align-items: baseline; gap: 8px; }
.ap-name-main { font-size: 15px; font-weight: 700; color: #111; }
.ap-name-tag { font-size: 10px; color: #aaa; font-family: monospace; }
.ap-status-line { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.ap-indicator { width: 6px; height: 6px; border-radius: 50%; }
.is-running { background: #00c853; animation: pulse 1.5s infinite; }
.is-done { background: #e0e0e0; }
@keyframes pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }
.ap-status-text { font-size: 11px; color: #888; }

/* 流程执行区 */
.ap-flow-flat { border-left: 1px solid #f0f0f0; padding-left: 16px; margin-left: 15px; }
.ap-section-flat { margin-bottom: 24px; }
.ap-section-head {
    font-size: 10px;
    color: #bbb;
    font-weight: 700;
    margin-bottom: 10px;
    letter-spacing: 0.5px;
}

/* 工具 */
.ap-tool-box-flat { display: flex; flex-wrap: wrap; gap: 8px; }
.ap-tool-item-flat { display: flex; align-items: center; gap: 6px; background: #f8f8f8; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
.ap-tool-status { width: 8px; height: 2px; background: #ddd; }
.is-tool-running { background: #f59e0b; width: 12px; }
.is-tool-done { background: #111; width: 12px; }
.ap-tool-label { color: #666; font-weight: 500; }
.ap-tool-result-tag { font-size: 9px; color: #00c853; font-weight: 900; }

/* 思考流（弱化显示 & 折叠） */
.ap-section-flat.has-thought {
    border-left: 2px solid #e2e8f0;
    padding-left: 12px;
    margin-left: -1px;
}
.ap-thought-text-flat {
    font-size: 13px;
    color: #94a3b8; /* 字体颜色弱化 */
    line-height: 1.6;
    white-space: pre-wrap;
    transition: max-height 0.4s ease-out;
}
.ap-thought-text-flat.is-collapsed {
    max-height: 4.8em; /* 约三行高度 */
    overflow: hidden;
    mask-image: linear-gradient(to bottom, black 60%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, black 60%, transparent 100%);
}
.ap-toggle-btn {
    font-size: 10px;
    color: #3b82f6;
    background: transparent;
    border: 1px solid #dbeafe;
    padding: 1px 6px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}
.ap-toggle-btn:hover { background: #eff6ff; }
.ap-cursor-flat { color: #94a3b8; font-weight: 900; animation: blink 0.8s infinite; }
@keyframes blink { 50% { opacity: 0; } }

/* 结果流 */
.ap-section-flat.has-result {
    border-left: 2px solid #111;
    padding-left: 12px;
    margin-left: -1px;
}
.ap-result-text-flat { font-size: 13px; color: #111; font-weight: 250; line-height: 1.6; }

.ap-section-waiting { font-size: 12px; color: #ccc; font-style: italic; }

/* ===== 原有样式适配 ===== */
.session-item:hover .el-button { opacity: 1; }
.chat-input :deep(.el-textarea__inner) { background-color: transparent; border: none; box-shadow: none; padding: 8px 0; font-size: 14px; }
.btn-suggest { padding: 6px 14px; background: white; border: 1px solid #E2E8F0; border-radius: 10px; font-size: 12px; color: #475569; transition: all 0.2s; }
.btn-suggest:hover { border-color: #174EA6; color: #174EA6; background: #f0f7ff; }
.send-btn { width: 36px; height: 36px; background-color: #174EA6; border-color: #174EA6; }
.send-btn:hover { background-color: #1a5ac1; border-color: #1a5ac1; }
.animate-bounce { animation: bounce 1s infinite; }
@keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }
.delay-150 { animation-delay: 0.15s; }
.delay-300 { animation-delay: 0.3s; }
</style>
