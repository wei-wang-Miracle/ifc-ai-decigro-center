<script setup lang="ts">
import { ref, nextTick, onMounted, computed, reactive } from 'vue'
import { Promotion, Warning, ChatLineRound, Plus, Delete, ChatDotSquare, Operation, Loading, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'
import { useChatStore, type ChatMessage } from '../../stores/chatStore'
import { useAppStore } from '../../stores/app'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 marked：使用 GFM 语法，换行保留
marked.setOptions({ breaks: true, gfm: true })

const renderMarkdown = (text: string): string => {
    if (!text) return ''
    return DOMPurify.sanitize(marked.parse(text) as string)
}

const userStore = useUserStore()
const chatStore = useChatStore()
const appStore = useAppStore()
const inputMessage = ref('')
const isLoading = ref(false)
const scrollContainer = ref<HTMLElement | null>(null)
const agentPanelScroll = ref<HTMLElement | null>(null)
// 控制思考过程展开/收起（整体面板）
const showThoughts = ref<Record<string, boolean>>({})
// 控制单个节点的思考内容展开/收起
const expandedNodeThinking = ref<Record<string, boolean>>({})
// 控制 Agent 面板中思考过程的展开/收起
const expandedThinking = ref<Record<string, boolean>>({})

// ===== Agent 工作面板相关 =====

// Agent 面板是否可见
const agentPanelVisible = ref(false)

// 当前高亮的 Agent 别名（聊天区和面板联动）
const highlightedAgent = ref<string | null>(null)

// Agent 工作日志数据结构
interface AgentToolCall {
    name: string
    alias: string
    status: string
    input?: Record<string, any>   // 工具调用入参（白盒化）
    output?: string               // 工具返回结果（白盒化）
    expanded?: boolean            // 是否展开详情
}

interface AgentWorkEntry {
    id: string
    agentName: string        // Agent 原始名称
    agentAlias: string       // Agent 别名（展示用）
    status: 'running' | 'success' | 'failed'
    startTime: number
    tools: AgentToolCall[]
    thinking: string         // Agent 的思考内容（流式累加）
    result: string           // Agent 最终产出
}

// 当前所有 Agent 工作记录
const agentWorkEntries = reactive<AgentWorkEntry[]>([])

// 当前活跃的 step_id（用于精确绑定工具/思考流到对应 Agent 条目）
const activeStepId = ref<string | null>(null)

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
    // 联动时，重置所有面板内逻辑块的展开状态为收起
    expandedThinking.value = {}

    // 如果消息带有持久化的 Agent 日志，则进行恢复
    if (msg && msg.agentLog && msg.agentLog.length > 0) {
        // 只有在非运行状态（非当前实时生成）下才覆盖，避免干扰当前正在进行的流
        if (!isLoading.value) {
            const restoredLog = msg.agentLog.map(e => ({
                ...e,
                // 历史记录必须标记为已完成，才能触发 CSS 自动收起逻辑
                status: (e.status === 'running' || !e.status) ? 'success' : e.status
            }))
            agentWorkEntries.splice(0, agentWorkEntries.length, ...restoredLog)
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

// 通过 step_id 查找 AgentWorkEntry（精确绑定，多 Agent 场景不错位）
const getEntryByStepId = (stepId: string | null): AgentWorkEntry | undefined => {
    if (!stepId) return undefined
    return agentWorkEntries.find(e => e.id === stepId)
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
            const restoredLog = lastAssistantMsg.agentLog.map(e => ({
                ...e,
                status: e.status === 'running' ? 'success' : e.status
            }))
            agentWorkEntries.push(...restoredLog)
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
    activeStepId.value = null

    // 前端生成 trace_id（每次用户发起提问时生成）
    const traceId = `trace_${crypto.randomUUID().replace(/-/g, '').substring(0, 16)}`

    // 前端生成 task_id：review 场景复用已有 task_id，新任务发起时生成新的
    const isReview = Boolean(chatStore.currentTaskId)
    const taskId = isReview ? chatStore.currentTaskId! : `task_${crypto.randomUUID().replace(/-/g, '').substring(0, 12)}`

    // 添加用户消息
    const userMessage = reactive<ChatMessage>({
        sessionId: chatStore.currentSessionId!,
        taskId: taskId,
        role: 'user',
        content: userQuery,
        createTime: new Date()
    })
    chatStore.addMessage(userMessage)

    // 首条消息发送后，异步更新会话标题为消息内容（通过 bus-kernel PUT 接口）
    if (chatStore.messages.length === 1 && chatStore.currentSession?.sessionTitle === '新会话') {
        chatStore.updateSessionTitle(chatStore.currentSessionId!, userQuery)
    }

    isLoading.value = true
    scrollToBottom()

    // 添加 AI 消息占位
    const aiMessage = reactive<ChatMessage>({
        sessionId: chatStore.currentSessionId!,
        taskId: taskId,
        traceId: traceId,
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
                task_id: taskId,
                trace_id: traceId
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
                                // task_id 和 trace_id 由前端生成，meta 事件仅作日志确认
                                chatStore.setTaskId(taskId)

                            } else if (event.type === 'thinking') {
                                // 简单显示"正在思考"

                            } else if (event.type === 'node_start') {
                                // 结束上一个节点的 running 状态
                                if (aiMessage.thoughts && aiMessage.thoughts.length > 0) {
                                    const last = aiMessage.thoughts[aiMessage.thoughts.length - 1]
                                    if (last.status === 'running') last.status = 'success'
                                }

                                aiMessage.thoughts?.push({
                                    id: `node-${event.node}-${Date.now()}`,
                                    type: 'node_start',
                                    nodeName: event.node,
                                    title: event.display_name || event.node,
                                    status: 'running',
                                    timestamp: Date.now(),
                                    content: '',
                                    thinking: '',       // 流式推理内容
                                    conclusion: ''      // 节点最终输出
                                })

                            } else if (event.type === 'agent_start') {
                                // ====== Agent 进场：展开右侧面板 ======
                                const agentAlias = event.agent_alias || event.agent
                                const agentName = event.agent
                                const stepId = event.step_id || `aw-${Date.now()}`

                                // 结束上一个运行中的思考步骤
                                if (aiMessage.thoughts && aiMessage.thoughts.length > 0) {
                                    const last = aiMessage.thoughts[aiMessage.thoughts.length - 1]
                                    if (last.status === 'running') last.status = 'success'
                                }

                                // 在聊天气泡中记录 Agent 启动
                                aiMessage.thoughts?.push({
                                    id: `agent-${stepId}`,
                                    type: 'agent_start',
                                    title: agentAlias,
                                    status: 'running',
                                    timestamp: Date.now(),
                                    content: ''
                                })

                                // 向右侧 Agent 面板添加工作条目（以 step_id 作为唯一 id）
                                const entry: AgentWorkEntry = {
                                    id: stepId,
                                    agentName,
                                    agentAlias,
                                    status: 'running',
                                    startTime: Date.now(),
                                    tools: [],
                                    thinking: '',
                                    result: ''
                                }
                                agentWorkEntries.push(entry)
                                activeStepId.value = stepId

                                // 展开 Agent 面板
                                agentPanelVisible.value = true
                                scrollToBottom()
                                scrollAgentPanelToBottom()

                            } else if (event.type === 'agent_end') {
                                // ====== Agent 结束：标记完成，清空活跃 step ======
                                const stepId = event.step_id
                                const entry = getEntryByStepId(stepId)
                                if (entry) {
                                    entry.status = event.success === false ? 'failed' : 'success'
                                }
                                // 在气泡中将对应 agent_start thought 标记完成
                                const agentThought = aiMessage.thoughts?.find(
                                    t => t.id === `agent-${stepId}`
                                )
                                if (agentThought) agentThought.status = 'success'
                                // 若当前活跃 step 就是本 step，清空
                                if (activeStepId.value === stepId) {
                                    activeStepId.value = null
                                }

                            } else if (event.type === 'tool_start') {
                                // 在聊天思考中记录
                                aiMessage.thoughts?.push({
                                    id: `tool-${Date.now()}-${Math.random()}`,
                                    type: 'tool_start',
                                    title: `执行工具: ${event.tool_alias || event.tool}`,
                                    status: 'running',
                                    timestamp: Date.now()
                                })
                                // 同步到 Agent 面板（优先用事件携带的 step_id，回退到 activeStepId）
                                const toolStepId = event.step_id || activeStepId.value
                                const toolEntry = getEntryByStepId(toolStepId)
                                if (toolEntry) {
                                    toolEntry.tools.push({
                                        name: event.tool,
                                        alias: event.tool_alias || event.tool,
                                        status: 'running',
                                        input: event.input || {},
                                        expanded: false
                                    })
                                }
                                scrollAgentPanelToBottom()

                            } else if (event.type === 'tool_end') {
                                // 更新聊天思考中的工具状态
                                const toolAlias = event.tool_alias || event.tool
                                const thought = aiMessage.thoughts?.slice().reverse().find(
                                    (t: any) => t.type === 'tool_start' && t.title.includes(toolAlias)
                                )
                                if (thought) {
                                    thought.status = 'success'
                                }
                                // 同步到 Agent 面板（优先用事件携带的 step_id，回退到 activeStepId）
                                const toolStepId = event.step_id || activeStepId.value
                                const toolEntry = getEntryByStepId(toolStepId)
                                if (toolEntry) {
                                    const tool = toolEntry.tools.slice().reverse().find(
                                        (t: AgentToolCall) => t.name === event.tool || t.alias === toolAlias
                                    )
                                    if (tool) {
                                        tool.status = 'success'
                                        tool.output = event.output
                                    }
                                }
                                console.log(`[Tool Result] ${event.tool}:`, event.output)

                            } else if (event.type === 'node_result') {
                                // 标记节点完成
                                const nodeThought = aiMessage.thoughts?.slice().reverse().find((t: any) => t.status === 'running' && t.type === 'node_start')
                                if (nodeThought) {
                                    nodeThought.status = 'success'
                                }
                                console.log(`[Node Result] ${event.node}:`, event.output)

                            } else if (event.type === 'node_thinking') {
                                // 后端为结构化节点解析出的可读思考内容（intent_recognition / planner）
                                const targetNode = aiMessage.thoughts?.slice().reverse().find(
                                    (t: any) => t.type === 'node_start' && t.nodeName === event.node
                                )
                                if (targetNode && event.thinking) {
                                    targetNode.thinking = event.thinking
                                }
                                console.log(`[Node Thinking] ${event.node}:`, event.thinking)

                            } else if (event.type === 'token') {
                                const { content, reasoning, is_thought, is_json, node } = event

                                // 过滤技术性的 JSON
                                if (is_json) continue

                                if (is_thought) {
                                    // ====== 思考流：优先追加到当前活跃 node_start 节点 ======
                                    const activeNode = aiMessage.thoughts?.slice().reverse().find(
                                        (t: any) => t.type === 'node_start' && t.status === 'running'
                                    )

                                    if (activeNode) {
                                        // 追加到节点的 thinking 字段（executor 节点的思考由协作面板处理）
                                        if (reasoning) activeNode.thinking = (activeNode.thinking || '') + reasoning
                                        else if (content) activeNode.thinking = (activeNode.thinking || '') + content
                                    } else {
                                        // 没有活跃节点时，fallback 到独立 thinking 气泡
                                        let activeThought = aiMessage.thoughts?.slice().reverse().find((t: any) => t.type === 'thinking' && t.status === 'running')
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
                                        if (reasoning) activeThought.content = (activeThought.content || '') + reasoning
                                        else if (content) activeThought.content = (activeThought.content || '') + content
                                    }

                                    // 同步思考内容到 Agent 面板（精确绑定到当前活跃 step）
                                    const thinkEntry = getEntryByStepId(activeStepId.value)
                                    if (thinkEntry) {
                                        if (reasoning) thinkEntry.thinking += reasoning
                                        else if (content) thinkEntry.thinking += content
                                        scrollAgentPanelToBottom()
                                    }
                                    continue
                                }

                                // ====== 正文流 ======
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

                                // 将 agentLog 同步回消息对象，使点击联动时能恢复面板数据
                                aiMessage.agentLog = [...agentWorkEntries]

                                // 顺序持久化：先存用户消息，再存 AI 回复，保证 create_time 顺序正确
                                ;(async () => {
                                    await chatStore.saveMessageToServer({
                                        sessionId: chatStore.currentSessionId!,
                                        taskId: taskId,
                                        traceId: traceId,
                                        role: 'user',
                                        content: userQuery
                                    })
                                    await chatStore.saveMessageToServer({
                                        sessionId: chatStore.currentSessionId!,
                                        taskId: taskId,
                                        traceId: traceId,
                                        role: 'assistant',
                                        content: event.message,
                                        thoughts: aiMessage.thoughts,
                                        agentLog: [...agentWorkEntries]
                                    })
                                })()

                                if (event.status === 'completed') {
                                    chatStore.clearTaskId()
                                    // 结束所有仍在运行中的 Agent（兜底）
                                    agentWorkEntries.forEach(e => {
                                        if (e.status === 'running') e.status = 'success'
                                    })
                                    activeStepId.value = null
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

// 格式化时间
const formatTime = (date: Date | string) => {
    const d = typeof date === 'string' ? new Date(date) : date
    return d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
}

// 将扁平的思考过程转化为树状结构 (用于聊天气泡展示)
const getThoughtTree = (thoughts?: any[]) => {
    if (!thoughts) return []
    const tree: any[] = []
    let lastNode: any = null
    let lastAgent: any = null

    thoughts.forEach(t => {
        if (t.type === 'node_start') {
            // 透传 thinking/conclusion/nodeName 字段，保持响应式引用
            lastNode = t
            if (!lastNode.children) lastNode.children = []
            tree.push(lastNode)
            lastAgent = null
        } else if (t.type === 'agent_start') {
            lastAgent = t
            if (!lastAgent.children) lastAgent.children = []
            if (lastNode) {
                if (!lastNode.children.includes(lastAgent)) lastNode.children.push(lastAgent)
            } else {
                tree.push(lastAgent)
            }
        } else if (t.type === 'tool_start') {
            if (lastAgent) {
                if (!lastAgent.children.includes(t)) lastAgent.children.push(t)
            } else if (lastNode) {
                if (!lastNode.children.includes(t)) lastNode.children.push(t)
            } else {
                tree.push(t)
            }
        }
    })
    return tree
}
</script>

<template>
    <div class="flex h-full chat-page">
        <!-- 左侧会话列表 -->
        <div class="flex flex-col border-r border-gray-200 session-sidebar w-38 bg-slate-50">
            <!-- 新建会话按钮 -->
            <div class="p-3 border-b border-gray-200">
                <el-button type="primary" class="w-full" size="default" @click="handleNewSession">
                    <el-icon class="mr-1"><Plus /></el-icon>
                    新建会话
                </el-button>
            </div>
            
            <!-- 会话列表 -->
            <div class="flex-1 overflow-y-auto p-2 space-y-0.5">
                <div v-if="chatStore.sessions.length === 0" class="py-8 text-xs text-center text-gray-400">
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
                    <div class="flex items-center flex-1 min-w-0 space-x-2">
                        <el-icon :size="14" class="flex-shrink-0"><ChatDotSquare /></el-icon>
                        <span class="text-xs truncate">{{ session.sessionTitle }}</span>
                    </div>
                    <el-button
                        type="danger"
                        size="small"
                        link
                        :icon="Delete"
                        class="h-auto p-0 transition-opacity opacity-0 group-hover:opacity-100"
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
            <div class="flex items-center justify-between px-6 py-4 border-b bg-slate-50">
                <div class="flex items-center space-x-3">
                    <div class="flex items-center justify-center w-10 h-10 text-white shadow-lg rounded-xl bg-brand-600">
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
            <div ref="scrollContainer" class="flex-1 p-6 space-y-6 overflow-y-auto bg-slate-50/30">
                <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full space-y-4 text-center">
                    <div class="flex items-center justify-center w-16 h-16 mb-2 bg-brand-50 rounded-2xl">
                        <el-icon class="text-2xl text-brand-600"><ChatLineRound /></el-icon>
                    </div>
                    <h3 class="text-lg font-bold text-gray-700">您好, {{ userStore.userInfo.username }}</h3>
                    <p class="max-w-sm text-sm text-gray-400">我可以为您处理复杂的业务流程，例如标签挖掘、自动化管理和数据分析。您可以尝试输入指令开始聊天。</p>
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
                                <!-- 思考过程展示：扁平三层树状结构 -->
                                <div v-if="msg.thoughts && msg.thoughts.length > 0" class="pb-2 mb-3 border-b border-gray-200 border-dashed">
                                    <!-- 折叠控制头 -->
                                    <div
                                        class="flex items-center text-xs text-gray-400 cursor-pointer hover:text-brand-500 select-none mb-1.5"
                                        @click="showThoughts[msg.id || idx] = !showThoughts[msg.id || idx]"
                                    >
                                        <el-icon class="mr-1 animate-spin" v-if="msg.status === 'running'"><Loading /></el-icon>
                                        <el-icon class="mr-1" v-else><Operation /></el-icon>
                                        <span>推理过程 ({{ getThoughtTree(msg.thoughts).length }} 个阶段)</span>
                                        <el-icon class="ml-1 transition-transform" :class="{ 'rotate-180': showThoughts[msg.id || idx] || msg.status === 'running' }"><ArrowDown /></el-icon>
                                    </div>

                                    <!-- 扁平树状内容 -->
                                    <div v-show="showThoughts[msg.id || idx] || msg.status === 'running'" class="thought-tree">
                                        <div v-for="node in getThoughtTree(msg.thoughts)" :key="node.id" class="thought-node-row">
                                            <!-- Node 标题行 -->
                                            <div class="thought-row-title">
                                                <div class="flex-shrink-0 node-dot" :class="node.status"></div>
                                                <span class="thought-node-label">{{ node.title }}</span>
                                                <span v-if="node.status === 'running'" class="thought-status-running">运行中</span>
                                                <!-- 展开/收起思考内容 -->
                                                <button
                                                    v-if="node.thinking && node.status !== 'running'"
                                                    class="thought-toggle"
                                                    @click.stop="expandedNodeThinking[node.id] = !expandedNodeThinking[node.id]"
                                                >{{ expandedNodeThinking[node.id] ? '收起' : '展开' }}</button>
                                            </div>

                                            <!-- 节点思考内容：浅色背景内嵌，流式显示，完成后折叠 -->
                                            <div
                                                v-if="node.thinking"
                                                :class="['thought-thinking-flat', { 'is-collapsed': node.status !== 'running' && !expandedNodeThinking[node.id] }]"
                                            >{{ node.thinking }}<span v-if="node.status === 'running'" class="thought-cursor">_</span></div>

                                            <!-- 第二层：Agent -->
                                            <div v-if="node.children && node.children.length > 0" class="thought-indent">
                                                <div v-for="agent in node.children" :key="agent.id">
                                                    <div v-if="agent.type === 'agent_start'">
                                                        <div class="thought-row-title">
                                                            <div class="flex-shrink-0 agent-dot" :class="agent.status"></div>
                                                            <span
                                                                class="cursor-pointer thought-agent-label hover:underline"
                                                                @click="handleAgentClick(agent.title, msg)"
                                                            >{{ agent.title }}</span>
                                                            <span v-if="agent.children && agent.children.length > 0" class="thought-tool-count">{{ agent.children.length }} 个工具</span>
                                                        </div>
                                                        <!-- 第三层：Tool -->
                                                        <div v-if="agent.children && agent.children.length > 0" class="thought-indent">
                                                            <div v-for="tool in agent.children" :key="tool.id" class="thought-row-title thought-tool-row">
                                                                <div class="flex-shrink-0 tool-dot" :class="tool.status"></div>
                                                                <span class="thought-tool-label">{{ tool.title }}</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <!-- Node 直属 Tool -->
                                                    <div v-else class="thought-row-title thought-tool-row">
                                                        <div class="flex-shrink-0 tool-dot" :class="agent.status"></div>
                                                        <span class="thought-tool-label">{{ agent.title }}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div
                                    v-if="msg.content"
                                    class="markdown-body leading-relaxed min-h-[1.5em]"
                                    v-html="renderMarkdown(msg.content)"
                                ></div>
                                <div v-else class="leading-relaxed min-h-[1.5em] text-slate-400">{{ msg.status === 'running' ? '...' : '' }}</div>
                                
                                <!-- 需要人工确认提示（对话式，无按钮） -->
                                <div v-if="msg.requireReview" class="pt-3 mt-3 border-t border-dashed border-amber-200">
                                    <p class="text-[11px] text-amber-600 flex items-center">
                                        <el-icon class="mr-1"><Warning /></el-icon>
                                        请在下方输入框直接回复您的决定
                                    </p>
                                </div>
                            </div>
                            <div :class="['text-[10px] text-gray-400 px-1', msg.role === 'user' ? 'text-right' : 'text-left']">
                                {{ formatTime(msg.createTime) }}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 加载 -->
                <div v-if="isLoading" class="flex items-center justify-start space-x-2">
                    <div class="px-4 py-3 bg-white border rounded-tl-none shadow-sm border-slate-100 rounded-2xl">
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
                <div class="relative flex items-end p-2 pr-3 space-x-3 transition-all border border-gray-200 bg-slate-50 rounded-2xl focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-50">
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
            <div v-if="agentPanelVisible" class="flex flex-col overflow-hidden agent-panel">
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
                                <div class="ap-tool-list-flat">
                                    <div v-for="(tool, tidx) in entry.tools" :key="tidx" class="ap-tool-card">
                                        <!-- 工具头部行：状态点 + 别名 + OK标记 + 展开按钮 -->
                                        <div class="ap-tool-card-head" @click="tool.expanded = !tool.expanded">
                                            <span :class="['ap-tool-status', tool.status === 'running' ? 'is-tool-running' : 'is-tool-done']"></span>
                                            <span class="ap-tool-label">{{ tool.alias }}</span>
                                            <span v-if="tool.status === 'running'" class="ap-tool-running-tag">执行中</span>
                                            <span v-else class="ap-tool-result-tag">OK</span>
                                            <span class="ap-tool-expand-btn">{{ tool.expanded ? '▲' : '▼' }}</span>
                                        </div>
                                        <!-- 工具详情：入参 + 出参（可折叠） -->
                                        <div v-if="tool.expanded" class="ap-tool-detail">
                                            <div v-if="tool.input && Object.keys(tool.input).length > 0" class="ap-tool-detail-section">
                                                <div class="ap-tool-detail-label">入参</div>
                                                <pre class="ap-tool-detail-code">{{ JSON.stringify(tool.input, null, 2) }}</pre>
                                            </div>
                                            <div v-if="tool.output" class="ap-tool-detail-section">
                                                <div class="ap-tool-detail-label">结果</div>
                                                <pre class="ap-tool-detail-code ap-tool-output">{{ tool.output }}</pre>
                                            </div>
                                            <div v-if="!tool.output && tool.status === 'running'" class="ap-tool-detail-section">
                                                <div class="ap-tool-detail-label">结果</div>
                                                <span class="ap-tool-waiting">等待返回...</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- 思考内容：弱化显示 & 完成后自动折叠 -->
                            <div v-if="entry.thinking" class="ap-section-flat has-thought">
                                <div class="flex items-center justify-between ap-section-head group">
                                    <span>逻辑 / THINKING</span>
                                    <button 
                                        v-if="entry.status !== 'running'"
                                        class="ap-toggle-btn"
                                        @click="expandedThinking[entry.id] = !expandedThinking[entry.id]"
                                    >
                                        {{ expandedThinking[entry.id] ? '收起更多记录' : '展开全文' }}
                                    </button>
                                </div>
                                <div :class="['ap-thought-text-flat', { 'is-collapsed': entry.status !== 'running' && !expandedThinking[entry.id] }]">
                                    <div class="markdown-body" v-html="renderMarkdown(entry.thinking)"></div>
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

/* 工具（白盒化卡片风格） */
.ap-tool-list-flat { display: flex; flex-direction: column; gap: 6px; }
.ap-tool-card { border: 1px solid #eef0f3; border-radius: 6px; overflow: hidden; font-size: 11px; }
.ap-tool-card-head {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: #f8f9fb;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s;
}
.ap-tool-card-head:hover { background: #f0f3f8; }
.ap-tool-status { width: 8px; height: 2px; background: #ddd; flex-shrink: 0; }
.is-tool-running { background: #f59e0b; width: 12px; }
.is-tool-done { background: #111; width: 12px; }
.ap-tool-label { color: #333; font-weight: 600; flex: 1; }
.ap-tool-running-tag { font-size: 9px; color: #f59e0b; font-weight: 700; }
.ap-tool-result-tag { font-size: 9px; color: #00c853; font-weight: 900; }
.ap-tool-expand-btn { font-size: 8px; color: #bbb; margin-left: auto; }
.ap-tool-detail { padding: 8px 10px; background: #fff; border-top: 1px solid #eef0f3; }
.ap-tool-detail-section { margin-bottom: 8px; }
.ap-tool-detail-section:last-child { margin-bottom: 0; }
.ap-tool-detail-label { font-size: 9px; font-weight: 700; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.ap-tool-detail-code {
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 10px;
    color: #475569;
    background: #f8f9fb;
    border: 1px solid #eef0f3;
    border-radius: 4px;
    padding: 6px 8px;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 120px;
    overflow-y: auto;
    line-height: 1.5;
    margin: 0;
}
.ap-tool-output { color: #1e40af; background: #eff6ff; border-color: #bfdbfe; }
.ap-tool-waiting { font-size: 10px; color: #94a3b8; font-style: italic; }

/* 思考流（弱化显示 & 折叠） */
.ap-section-flat.has-thought {
    border-left: 2px solid #e2e8f0;
    padding-left: 12px;
    margin-left: -1px;
}
.ap-thought-text-flat {
    font-size: 11px;
    color: #94a3b8; /* 字体颜色弱化 */
    line-height: 1.45;
    transition: max-height 0.4s ease-out;
}
.ap-thought-text-flat :deep(.markdown-body) {
    font-size: 11px;
    line-height: 1.45;
    color: #94a3b8;
}
.ap-thought-text-flat :deep(.markdown-body p) { margin: 0 0 0.3em; }
.ap-thought-text-flat :deep(.markdown-body p:last-child) { margin-bottom: 0; }
.ap-thought-text-flat :deep(.markdown-body h1),
.ap-thought-text-flat :deep(.markdown-body h2),
.ap-thought-text-flat :deep(.markdown-body h3),
.ap-thought-text-flat :deep(.markdown-body h4) { font-size: 11px; font-weight: 700; margin: 0.4em 0 0.2em; }
.ap-thought-text-flat :deep(.markdown-body ul),
.ap-thought-text-flat :deep(.markdown-body ol) { padding-left: 1.2em; margin: 0.2em 0 0.3em; }
.ap-thought-text-flat :deep(.markdown-body li) { margin: 0.1em 0; }
.ap-thought-text-flat :deep(.markdown-body code) { font-size: 10px; padding: 0 3px; }
.ap-thought-text-flat :deep(.markdown-body pre) { padding: 5px 8px; margin: 0.3em 0; }
.ap-thought-text-flat :deep(.markdown-body pre code) { font-size: 10px; }
.ap-thought-text-flat.is-collapsed {
    max-height: 4.8em !important; /* 约三行高度 */
    overflow: hidden !important;
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
/* ===== 思考过程：扁平树状布局 ===== */
.thought-tree {
    font-size: 11px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

/* Node 行 */
.thought-node-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

/* 通用标题行：状态点 + 文字 + 操作 */
.thought-row-title {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 18px;
}

/* Node 标签 */
.thought-node-label {
    font-weight: 700;
    color: #475569;
    font-size: 11px;
    letter-spacing: 0.3px;
    text-transform: uppercase;
    flex: 1;
}

.thought-status-running {
    font-size: 9px;
    color: #3b82f6;
    font-weight: 600;
    flex-shrink: 0;
}

/* 展开/收起按钮 */
.thought-toggle {
    font-size: 9px;
    color: #94a3b8;
    background: transparent;
    border: none;
    padding: 0 4px;
    cursor: pointer;
    flex-shrink: 0;
    line-height: 1;
}
.thought-toggle:hover { color: #3b82f6; }

/* 思考内容：浅色背景内嵌，流式显示，完成后折叠 */
.thought-thinking-flat {
    margin-left: 14px;
    padding: 6px 10px;
    background: #f8fafc;
    border-left: 2px solid #e2e8f0;
    border-radius: 0 4px 4px 0;
    font-size: 11px;
    color: #94a3b8;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    transition: max-height 0.35s ease-out;
}
.thought-thinking-flat.is-collapsed {
    max-height: 4.5em;
    overflow: hidden;
    mask-image: linear-gradient(to bottom, black 50%, transparent 100%);
    -webkit-mask-image: linear-gradient(to bottom, black 50%, transparent 100%);
}

/* 缩进层（Agent / Tool 层） */
.thought-indent {
    margin-left: 14px;
    padding-left: 10px;
    border-left: 1px solid #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 3px;
}

/* Agent 标签 */
.thought-agent-label {
    color: #6366f1;
    font-weight: 600;
    font-size: 11px;
    flex: 1;
}

.thought-tool-count {
    color: #cbd5e1;
    font-size: 10px;
    flex-shrink: 0;
}

/* Tool 行 */
.thought-tool-row { opacity: 0.8; }
.thought-tool-label {
    color: #94a3b8;
    font-size: 10px;
    font-style: italic;
    flex: 1;
}

/* 光标 */
.thought-cursor {
    color: #94a3b8;
    font-weight: 900;
    animation: blink2 0.8s infinite;
}
@keyframes blink2 { 50% { opacity: 0; } }

/* ===== 思考过程状态点（Node / Agent / Tool） ===== */
.node-dot, .agent-dot, .tool-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.node-dot.running, .agent-dot.running, .tool-dot.running { background: #3b82f6; animation: pulse 1.5s infinite; }
.node-dot { background: #a855f7; }
.agent-dot { background: #6366f1; }
.tool-dot { background: #f59e0b; }
.node-dot.success, .agent-dot.success, .tool-dot.success { background: #10b981; }

.delay-150 { animation-delay: 0.15s; }
.delay-300 { animation-delay: 0.3s; }

/* ===== Markdown 渲染样式 ===== */
.markdown-body { font-size: 14px; line-height: 1.7; color: inherit; }
.markdown-body :deep(p) { margin: 0 0 0.6em; }
.markdown-body :deep(p:last-child) { margin-bottom: 0; }
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) { font-weight: 700; margin: 0.8em 0 0.4em; line-height: 1.3; }
.markdown-body :deep(h1) { font-size: 1.3em; }
.markdown-body :deep(h2) { font-size: 1.15em; }
.markdown-body :deep(h3) { font-size: 1.05em; }
.markdown-body :deep(ul),
.markdown-body :deep(ol) { padding-left: 1.4em; margin: 0.4em 0 0.6em; }
.markdown-body :deep(li) { margin: 0.2em 0; }
.markdown-body :deep(code) {
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 12px;
    background: rgba(100, 116, 139, 0.12);
    padding: 1px 5px;
    border-radius: 4px;
}
.markdown-body :deep(pre) {
    background: #1e293b;
    border-radius: 6px;
    padding: 10px 14px;
    overflow-x: auto;
    margin: 0.6em 0;
}
.markdown-body :deep(pre code) {
    background: transparent;
    padding: 0;
    font-size: 12px;
    color: #e2e8f0;
}
.markdown-body :deep(blockquote) {
    border-left: 3px solid #cbd5e1;
    padding-left: 10px;
    color: #94a3b8;
    margin: 0.5em 0;
}
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; margin: 0.6em 0; font-size: 13px; }
.markdown-body :deep(th),
.markdown-body :deep(td) { border: 1px solid #e2e8f0; padding: 5px 10px; text-align: left; }
.markdown-body :deep(th) { background: #f8fafc; font-weight: 600; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid #e2e8f0; margin: 0.8em 0; }
.markdown-body :deep(a) { color: #3b82f6; text-decoration: underline; }
/* 用户气泡（深色背景）内的代码块 */
.bg-brand-600 .markdown-body :deep(code) { background: rgba(255,255,255,0.15); }
.bg-brand-600 .markdown-body :deep(a) { color: #bfdbfe; }
</style>
