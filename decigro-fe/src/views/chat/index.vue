<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Promotion, Warning, ChatLineRound } from '@element-plus/icons-vue'
import aiRequest from '../../utils/aiRequest'
import { useUserStore } from '../../stores/user'
import { ElMessage } from 'element-plus'

interface Message {
    role: 'user' | 'ai'
    content: string
    timestamp: Date
    thread_id?: string
    status?: string
    require_review?: boolean
}

const userStore = useUserStore()
const inputMessage = ref('')
const isLoading = ref(false)
const messages = ref<Message[]>([])
const scrollContainer = ref<HTMLElement | null>(null)

// 自动滚动到底部
const scrollToBottom = async () => {
    await nextTick()
    if (scrollContainer.value) {
        scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
}

// 发送消息
const handleSend = async () => {
    if (!inputMessage.value.trim() || isLoading.value) return

    const userQuery = inputMessage.value
    inputMessage.value = ''
    
    messages.value.push({
        role: 'user',
        content: userQuery,
        timestamp: new Date()
    })
    
    isLoading.value = true
    scrollToBottom()

    try {
        const res = await aiRequest.post('/chat', {
            query: userQuery,
            user_id: userStore.userInfo.userId || 'guest',
            session_id: 'session_' + Date.now()
        }) as any

        messages.value.push({
            role: 'ai',
            content: res.message,
            timestamp: new Date(),
            thread_id: res.thread_id,
            status: res.status,
            require_review: res.require_review
        })
    } catch (error) {
        console.error('Chat error:', error)
    } finally {
        isLoading.value = false
        scrollToBottom()
    }
}

// 处理审核
const handleReview = async (thread_id: string, action: 'approve' | 'reject') => {
    try {
        const res = await aiRequest.post(`/review/${thread_id}`, {
            action,
            feedback: action === 'reject' ? '已被用户驳回' : '通过'
        }) as any

        const msg = messages.value.find(m => m.thread_id === thread_id)
        if (msg) {
            msg.content = res.message
            msg.status = res.status
            msg.require_review = res.require_review
        }
        
        ElMessage.success(`操作成功: ${action}`)
    } catch (error) {
        console.error('Review error:', error)
    }
}
</script>

<template>
    <div class="chat-container flex flex-col h-full bg-white rounded-xl shadow-sm overflow-hidden border border-gray-100">
        <!-- 头部 -->
        <div class="px-6 py-4 border-b bg-slate-50 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center text-white shadow-lg">
                    <el-icon size="20"><Promotion /></el-icon>
                </div>
                <div>
                    <h2 class="text-base font-bold text-gray-800">AI 智能助理</h2>
                    <p class="text-xs text-gray-400">基于 LangGraph 的多智能体协作平台</p>
                </div>
            </div>
            <div class="flex items-center space-x-2">
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
                        <el-icon v-if="msg.role === 'ai'"><Promotion /></el-icon>
                        <span v-else class="text-xs font-bold">{{ userStore.userInfo.username?.[0]?.toUpperCase() }}</span>
                    </div>

                    <!-- 气泡 -->
                    <div class="space-y-1">
                        <div :class="['px-4 py-3 rounded-2xl text-sm shadow-sm', 
                            msg.role === 'user' 
                                ? 'bg-brand-600 text-white rounded-tr-none' 
                                : 'bg-white text-slate-700 border border-slate-100 rounded-tl-none']"
                        >
                            <div class="whitespace-pre-wrap leading-relaxed">{{ msg.content }}</div>
                            
                            <!-- 审核区域 -->
                            <div v-if="msg.require_review" class="mt-4 pt-4 border-t border-dashed border-slate-100">
                                <p class="text-[11px] font-bold text-amber-600 mb-3 flex items-center uppercase tracking-wider">
                                    <el-icon class="mr-1"><Warning /></el-icon> 人工审核确认
                                </p>
                                <div class="flex space-x-3">
                                    <el-button type="success" size="small" @click="handleReview(msg.thread_id!, 'approve')" plain>批准执行</el-button>
                                    <el-button type="danger" size="small" @click="handleReview(msg.thread_id!, 'reject')" plain>驳回并中断</el-button>
                                </div>
                            </div>
                        </div>
                        <div :class="['text-[10px] text-gray-400 px-1', msg.role === 'user' ? 'text-right' : 'text-left']">
                            {{ msg.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}
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
</template>

<style scoped>
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
