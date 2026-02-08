<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ChatLineRound, Close, Promotion, Warning, Check } from '@element-plus/icons-vue'
import aiRequest from '../utils/aiRequest'
import { useUserStore } from '../stores/user'
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
const isOpen = ref(false)
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
    
    // 添加用户消息
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

        // 添加 AI 响应
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

        // 更新最后一条消息状态
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

watch(isOpen, (newVal) => {
    if (newVal) {
        scrollToBottom()
    }
})
</script>

<template>
    <div class="ai-chat-widget">
        <!-- 悬浮按钮 -->
        <div 
            class="chat-trigger shadow-lg hover:scale-110 transition-all duration-300"
            @click="isOpen = !isOpen"
        >
            <el-icon v-if="!isOpen"><ChatLineRound /></el-icon>
            <el-icon v-else><Close /></el-icon>
            <div v-if="!isOpen" class="badge">AI</div>
        </div>

        <!-- 对话窗口 -->
        <Transition name="fade-slide">
            <div v-if="isOpen" class="chat-window shadow-2xl flex flex-col overflow-hidden">
                <!-- 头部 -->
                <div class="chat-header px-4 py-3 flex items-center justify-between border-b bg-brand-900 text-white">
                    <div class="flex items-center space-x-2">
                        <div class="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center shadow-inner">
                            <el-icon class="text-white"><Promotion /></el-icon>
                        </div>
                        <div>
                            <p class="text-sm font-bold leading-tight">DeciGro AI</p>
                            <p class="text-[10px] opacity-60">智能辅助引擎</p>
                        </div>
                    </div>
                </div>

                <!-- 消息列表 -->
                <div ref="scrollContainer" class="chat-body flex-1 p-4 overflow-y-auto bg-slate-50 space-y-4">
                    <div v-if="messages.length === 0" class="welcome-card p-6 text-center space-y-3">
                        <div class="w-12 h-12 bg-brand-50 rounded-2xl mx-auto flex items-center justify-center">
                            <el-icon class="text-brand-500 text-xl"><Promotion /></el-icon>
                        </div>
                        <p class="text-sm font-bold text-slate-700">您好! {{ userStore.userInfo.username }}</p>
                        <p class="text-xs text-slate-400">我是您的业务助理，可以帮您查询数据、管理标签或执行复杂操作。</p>
                        <div class="flex flex-wrap gap-2 justify-center mt-4">
                            <button @click="inputMessage = '帮我查询所有客户标签'; handleSend()" class="suggestion">查询标签</button>
                            <button @click="inputMessage = '有哪些可用的智能体？'; handleSend()" class="suggestion">查看 Agent</button>
                        </div>
                    </div>

                    <div v-for="(msg, idx) in messages" :key="idx" 
                        :class="['flex w-full', msg.role === 'user' ? 'justify-end' : 'justify-start']"
                    >
                        <div :class="['max-w-[85%] rounded-2xl px-4 py-2 text-sm shadow-sm transition-all', 
                            msg.role === 'user' 
                                ? 'bg-brand-600 text-white rounded-tr-none' 
                                : 'bg-white text-slate-700 border border-slate-100 rounded-tl-none']"
                        >
                            <div class="message-content whitespace-pre-wrap">{{ msg.content }}</div>
                            
                            <!-- 审核交互区 -->
                            <div v-if="msg.require_review" class="mt-3 pt-3 border-t border-slate-100 space-y-2">
                                <div class="flex items-center space-x-1 text-[10px] text-amber-500 font-bold uppercase tracking-wider">
                                    <el-icon><Warning /></el-icon>
                                    <span>需要人工确认</span>
                                </div>
                                <div class="flex space-x-2">
                                    <button 
                                        class="flex-1 py-1 px-3 bg-emerald-50 text-emerald-600 rounded-md text-xs hover:bg-emerald-100 transition-colors flex items-center justify-center space-x-1"
                                        @click="handleReview(msg.thread_id!, 'approve')"
                                    >
                                        <el-icon><Check /></el-icon>
                                        <span>批准执行</span>
                                    </button>
                                    <button 
                                        class="flex-1 py-1 px-3 bg-rose-50 text-rose-600 rounded-md text-xs hover:bg-rose-100 transition-colors flex items-center justify-center space-x-1"
                                        @click="handleReview(msg.thread_id!, 'reject')"
                                    >
                                        <el-icon><Close /></el-icon>
                                        <span>驳回操作</span>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="text-[9px] mt-1 opacity-40 text-right italic uppercase">
                                {{ msg.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) }}
                            </div>
                        </div>
                    </div>

                    <!-- 加载状态 -->
                    <div v-if="isLoading" class="flex justify-start">
                        <div class="bg-white border border-slate-100 rounded-2xl rounded-tl-none px-4 py-3 flex space-x-1 shadow-sm">
                            <span class="dot"></span>
                            <span class="dot"></span>
                            <span class="dot"></span>
                        </div>
                    </div>
                </div>

                <!-- 输入框 -->
                <div class="chat-footer p-3 bg-white border-t border-slate-100 flex items-end space-x-2">
                    <textarea 
                        v-model="inputMessage" 
                        rows="1"
                        placeholder="请输入指令..." 
                        class="flex-1 resize-none border-none bg-slate-100 rounded-xl px-4 py-2 text-sm focus:ring-2 focus:ring-brand-500/20 transition-all"
                        @keydown.enter.prevent="handleSend"
                    ></textarea>
                    <button 
                        @click="handleSend"
                        :disabled="!inputMessage.trim() || isLoading"
                        class="w-10 h-10 bg-brand-600 text-white rounded-xl flex items-center justify-center hover:bg-brand-700 disabled:bg-slate-200 transition-all flex-shrink-0"
                    >
                        <el-icon><Promotion /></el-icon>
                    </button>
                </div>
            </div>
        </Transition>
    </div>
</template>

<style scoped>
.ai-chat-widget {
    position: fixed;
    right: 32px;
    bottom: 32px;
    z-index: 2000;
}

.chat-trigger {
    width: 60px;
    height: 60px;
    background: #174EA6;
    border-radius: 50%;
    color: white;
    font-size: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    position: relative;
    border: 4px solid #fff;
}

.badge {
    position: absolute;
    top: -4px;
    right: -4px;
    background: #FF5252;
    color: white;
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 10px;
    border: 2px solid #fff;
}

.chat-window {
    position: absolute;
    right: 0;
    bottom: 80px;
    width: 380px;
    height: 580px;
    background: white;
    border-radius: 24px;
    transform-origin: bottom right;
}

.suggestion {
    padding: 4px 12px;
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    font-size: 11px;
    color: #64748B;
    transition: all 0.2s;
}

.suggestion:hover {
    border-color: #1a73e8;
    color: #1a73e8;
    background: #f8fbff;
}

/* 动画效果 */
.dot {
    width: 6px;
    height: 6px;
    background: #CBD5E1;
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
    0%, 80%, 100% { transform: scale(0); }
    40% { transform: scale(1.0); }
}

.fade-slide-enter-active, .fade-slide-leave-active {
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.fade-slide-enter-from, .fade-slide-leave-to {
    opacity: 0;
    transform: scale(0.9) translateY(20px);
}
</style>
