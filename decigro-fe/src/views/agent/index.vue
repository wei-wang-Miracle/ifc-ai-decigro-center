<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../utils/request'
import { Plus, Edit, Search, Refresh, Check, Close, Cpu } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// ============================================
// 第一部分：数据定义
// ============================================

interface AgentCard {
    agentName: string
    agentAlias: string
    agentDescription: string
    agentTags: string[]
    systemPrompt: string
    negativePrompt: string
    boundTools: string[] | null
    reasoningFramework: string
    agentVersion: string
    isOnline: boolean
    managerBy: string
    createTime: string
    updateTime: string
}

// --- 列表相关 ---
const cardList = ref<AgentCard[]>([])
const loading = ref(false)
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(12)
const searchKeyword = ref('')
const searchTag = ref('')

// --- 卡片翻转状态 (使用 agentName 作为 Key) ---
const flippedCards = ref<Set<string>>(new Set())

// --- 表单相关 ---
const dialogVisible = ref(false)
const dialogTitle = ref('')
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<AgentCard>({
    agentName: '',
    agentAlias: '',
    agentDescription: '',
    agentTags: [],
    systemPrompt: '',
    negativePrompt: '',
    boundTools: null,
    reasoningFramework: 'ReAct',
    agentVersion: '1.0.0',
    isOnline: true,
    managerBy: '',
    createTime: '',
    updateTime: ''
})

const formRules = reactive<FormRules>({
    agentName: [
        { required: true, message: '请输入唯一标识', trigger: 'blur' },
        { pattern: /^[a-z0-9_]+$/, message: '仅支持小写字母、数字、下划线', trigger: 'blur' }
    ],
    agentAlias: [{ required: true, message: '请输入智能体名称', trigger: 'blur' }],
    agentDescription: [{ required: true, message: '请输入描述', trigger: 'blur' }],
    systemPrompt: [{ required: true, message: '请输入系统提示词', trigger: 'blur' }]
})

// --- 可用工具列表 ---
const availableTools = ref<string[]>([])
const newTag = ref('')

// --- 推理框架选项 ---
const frameworkOptions = [
    { label: 'ReAct (推理+行动)', value: 'ReAct' },
    { label: 'PlanSolve', value: 'PlanSolve' },
    { label: 'COT (思维链)', value: 'COT' },
    { label: 'Direct (直接执行)', value: 'Direct' }
]

// ============================================
// 第二部分：交互实现
// ============================================

const fetchList = async () => {
    loading.value = true
    try {
        const params: any = { page: pageNum.value, size: pageSize.value }
        if (searchKeyword.value) params.keyword = searchKeyword.value
        if (searchTag.value) params.tag = searchTag.value
        const res: any = await request.get('/agent-cards', { params })
        cardList.value = res.records || []
        total.value = res.totalRow || 0
    } catch (e) {
        console.error('获取列表失败', e)
    } finally {
        loading.value = false
    }
}

const handleSearch = () => {
    pageNum.value = 1
    fetchList()
}

const fetchAvailableTools = async () => {
    try {
        const res: any = await request.get('/agent-cards/available-tools')
        availableTools.value = res || []
    } catch (e) { console.error(e) }
}

const handleAdd = () => {
    dialogTitle.value = '入职新智能体'
    isEdit.value = false
    resetForm()
    fetchAvailableTools()
    dialogVisible.value = true
}

const handleEdit = (card: AgentCard) => {
    dialogTitle.value = '修改智能体档案'
    isEdit.value = true
    Object.assign(form, JSON.parse(JSON.stringify(card)))
    if (!form.agentTags) form.agentTags = []
    fetchAvailableTools()
    dialogVisible.value = true
}

const handleFlip = (name: string) => {
    if (flippedCards.value.has(name)) flippedCards.value.delete(name)
    else flippedCards.value.add(name)
}

const handleToggleOnline = async (card: AgentCard) => {
    const action = card.isOnline ? 'offline' : 'online'
    await request.put(`/agent-cards/${card.agentName}/${action}`)
    ElMessage.success(card.isOnline ? '已离线' : '已就绪')
    fetchList()
}

const submitForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            await request.post('/agent-cards', form)
            ElMessage.success('保存成功')
            dialogVisible.value = false
            fetchList()
        }
    })
}

const resetForm = () => {
    Object.assign(form, {
        agentName: '',
        agentAlias: '',
        agentDescription: '',
        agentTags: [],
        systemPrompt: '',
        negativePrompt: '',
        boundTools: null,
        reasoningFramework: 'ReAct',
        agentVersion: '1.0.0',
        isOnline: true,
        managerBy: '',
        createTime: '',
        updateTime: ''
    })
}

const handleAddTag = () => {
    if (newTag.value && !form.agentTags.includes(newTag.value)) {
        form.agentTags.push(newTag.value)
        newTag.value = ''
    }
}
const handleRemoveTag = (tag: string) => {
    form.agentTags = form.agentTags.filter(t => t !== tag)
}

onMounted(() => fetchList())
</script>

<template>
  <div class="agent-registry">
    <!-- 顶部操作栏 -->
    <div class="header-bar">
        <div class="header-left">
            <div class="header-icon"><el-icon class="text-white"><Cpu /></el-icon></div>
            <div class="header-info">
                <h3 class="header-title">MAS 智能体管理中心</h3>
                <p class="header-subtitle">{{ total }} 名就职员工</p>
            </div>
            <el-button type="primary" :icon="Plus" @click="handleAdd" class="add-btn">
                创建智能体
            </el-button>
        </div>
        <div class="header-right">
            <el-input v-model="searchKeyword" placeholder="关键词检索" clearable class="w-40" @keyup.enter="handleSearch" />
            <el-button :icon="Search" @click="handleSearch" />
            <el-button :icon="Refresh" @click="fetchList" />
        </div>
    </div>

    <!-- 工牌网格 -->
    <div class="badge-wall" v-loading="loading">
        <div 
            v-for="(card, index) in cardList" 
            :key="card.agentName" 
            class="badge-container entrance-swing"
            :class="{ 'is-flipped': flippedCards.has(card.agentName) }"
            :style="{ animationDelay: `${index * 0.1}s` }">
            
            <div class="lanyard"><div class="lanyard-clip"></div><div class="lanyard-string"></div></div>
            
            <div class="badge-flipper">
                <!-- 正面: 参考图片样式优化 -->
                <div class="badge-front">
                    <!-- 右上角配置按钮 -->
                    <button class="config-btn-top" @click.stop="handleFlip(card.agentName)" title="查看配置详情">
                        <el-icon><Edit /></el-icon>
                    </button>
                    
                    <div class="status-bar" :class="card.isOnline ? 'online' : 'offline'">
                        <span class="status-dot"></span>
                        {{ card.isOnline ? 'READY' : 'OFF' }}
                    </div>
                    
                    <div class="id-band">
                        <span class="id-text">{{ card.agentName }}</span>
                    </div>
                    
                    <div class="card-main">
                        <div class="avatar-box">
                            <img 
                                :src="`https://api.dicebear.com/9.x/notionists/svg?seed=${card.agentName}`" 
                                :alt="card.agentAlias"
                                class="pixel-avatar-img"
                            />
                        </div>
                        
                        <div class="info-content">
                            <h4 class="info-alias">{{ card.agentAlias }}</h4>
                            <p class="info-desc">{{ card.agentDescription }}</p>
                        </div>
                    </div>
                    
                    <div class="card-divider"></div>
                    
                    <div class="card-footer-new">
                        <div class="footer-brand">MAS.CORE</div>
                        <div class="footer-tags-area">
                            <span v-for="tag in card.agentTags.slice(0, 2)" :key="tag" class="footer-tag">{{ tag }}</span>
                        </div>
                    </div>
                </div>
                
                <!-- 背面: 核心配置 -->
                <div class="badge-back">
                    <div class="back-header">
                        <span>内核设定</span>
                        <button class="close-btn" @click="handleFlip(card.agentName)">✕</button>
                    </div>
                    <div class="back-content">
                        <div class="info-section">
                            <div class="info-label">系统指令 (Prompt)</div>
                            <div class="info-value prompt-box">{{ card.systemPrompt }}</div>
                        </div>
                        <div class="info-section">
                            <div class="info-label">工具权限</div>
                            <div class="tool-list">
                                <template v-if="card.boundTools === null">
                                    <span class="tool-badge all">全量启用 (All Tools)</span>
                                </template>
                                <template v-else-if="card.boundTools.length === 0">
                                    <span class="tool-badge none">纯文本模式 (Chat Only)</span>
                                </template>
                                <template v-else>
                                    <span v-for="t in card.boundTools" :key="t" class="tool-badge">{{ t }}</span>
                                </template>
                            </div>
                        </div>
                    </div>
                    <div class="back-actions">
                        <el-button circle :icon="card.isOnline ? Close : Check" :type="card.isOnline ? 'info' : 'success'" @click="handleToggleOnline(card)" />
                        <el-button circle :icon="Edit" @click="handleEdit(card)" />
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 表单弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="800px">
        <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px" class="p-4">
            <el-row :gutter="20">
                <el-col :span="12">
                    <el-form-item label="唯一标识" prop="agentName">
                        <el-input v-model="form.agentName" :disabled="isEdit" placeholder="snake_case" />
                    </el-form-item>
                </el-col>
                <el-col :span="12">
                    <el-form-item label="智能体名称" prop="agentAlias">
                        <el-input v-model="form.agentAlias" placeholder="展示名称" />
                    </el-form-item>
                </el-col>
            </el-row>
            <el-form-item label="职能描述" prop="agentDescription">
                <el-input v-model="form.agentDescription" type="textarea" :rows="2" placeholder="展示在工牌上的描述" />
            </el-form-item>
            <el-form-item label="系统提示词" prop="systemPrompt">
                <el-input v-model="form.systemPrompt" type="textarea" :rows="6" placeholder="System Message" />
            </el-form-item>
            <el-row :gutter="20">
                <el-col :span="12">
                    <el-form-item label="推理框架">
                        <el-select v-model="form.reasoningFramework" class="w-full">
                            <el-option v-for="o in frameworkOptions" :key="o.value" :label="o.label" :value="o.value" />
                        </el-select>
                    </el-form-item>
                </el-col>
                <el-col :span="12">
                    <el-form-item label="标签">
                        <el-input v-model="newTag" size="small" placeholder="Enter添加" @keyup.enter="handleAddTag" class="mb-2" />
                        <div class="flex flex-wrap gap-1">
                            <el-tag v-for="t in form.agentTags" :key="t" closable size="small" @close="handleRemoveTag(t)">{{ t }}</el-tag>
                        </div>
                    </el-form-item>
                </el-col>
            </el-row>
            <el-form-item label="工具绑定">
                <el-radio-group v-model="form.boundTools" class="mb-2">
                    <el-radio :label="null">默认全量 (All)</el-radio>
                    <el-radio :label="[]">无工具 (Chat Only)</el-radio>
                    <el-radio label="specific">白名单 (Allowlist)</el-radio>
                </el-radio-group>
                <el-select 
                    v-if="typeof form.boundTools === 'string' || (form.boundTools && form.boundTools.length > 0)"
                    v-model="form.boundTools" 
                    multiple 
                    placeholder="选择工具"
                    class="w-full">
                    <el-option v-for="t in availableTools" :key="t" :label="t" :value="t" />
                </el-select>
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitForm(formRef)">下发执行</el-button>
        </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.agent-registry { height: 100%; display: flex; flex-direction: column; gap: 16px; font-family: 'Inter', sans-serif; }
.header-bar { background: #fff; border: 2px solid #000; padding: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 4px 4px 0 #000; }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-icon { width: 40px; height: 40px; background: #000; display: flex; align-items: center; justify-content: center; border-radius: 4px; }
.header-title { font-weight: 800; font-size: 18px; margin: 0; }
.header-subtitle { font-size: 12px; color: #666; margin: 0; font-family: monospace; }
.badge-wall { flex: 1; display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 60px 24px; padding: 40px 20px 20px; overflow-y: auto; background: #f8faff; }
.badge-container { display: flex; flex-direction: column; align-items: center; perspective: 1000px; transform-origin: top center; }

/* 入场摆动动画 */
.entrance-swing {
    animation: swing-in 1.2s cubic-bezier(0.36, 0, 0.66, -0.56) backwards;
}

@keyframes swing-in {
    0% { transform: rotateX(-30deg) rotateY(-10deg) translateY(-20px); opacity: 0; }
    20% { transform: rotateX(15deg) rotateY(5deg); opacity: 1; }
    40% { transform: rotateX(-10deg) rotateY(-3deg); }
    60% { transform: rotateX(5deg) rotateY(2deg); }
    80% { transform: rotateX(-2deg) rotateY(-1deg); }
    100% { transform: rotateX(0) rotateY(0); }
}

.lanyard { display: flex; flex-direction: column; align-items: center; z-index: 10; cursor: pointer; transition: transform 0.3s ease; }
.badge-container:hover .lanyard { transform: translateY(2px); }
.lanyard-clip { width: 30px; height: 12px; background: #333; border-radius: 4px; }
.lanyard-string { width: 4px; height: 15px; background: #4285f4; }
.badge-flipper { width: 220px; height: 320px; position: relative; transform-style: preserve-3d; transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1); }
.badge-container.is-flipped .badge-flipper { transform: rotateY(180deg); }
.badge-front, .badge-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; background: #fafafa; border: 1px solid #dcdfe6; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); overflow: hidden; display: flex; flex-direction: column; transition: all 0.3s ease; }
.badge-front:hover { border-color: #4285f4; }
.badge-back { transform: rotateY(180deg); background: #ffffff; border: 2px solid #000; }

/* 右上角按钮 */
.config-btn-top { position: absolute; top: 12px; right: 12px; width: 28px; height: 28px; background: #fff; border: 1px solid #eee; border-radius: 6px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: #666; transition: all 0.2s; z-index: 20; }
.config-btn-top:hover { background: #000; color: #fff; border-color: #000; transform: scale(1.1); }

.status-bar { position: absolute; top: 15px; left: 15px; font-size: 8px; font-weight: 900; color: #999; display: flex; align-items: center; gap: 4px; letter-spacing: 0.5px; }
.status-dot { width: 5px; height: 5px; border-radius: 50%; background: #ccc; }
.online .status-dot { background: #4ade80; box-shadow: 0 0 5px #4ade80; }
.online.status-bar { color: #555; }

.id-band { margin: 45px 15px 15px; background: #1a1a1a; border-radius: 8px; padding: 6px 12px; }
.id-text { color: #fff; font-size: 13px; font-weight: 700; letter-spacing: 0.5px; font-family: 'JetBrains Mono', monospace; }

.card-main { flex: 1; display: flex; flex-direction: column; align-items: flex-start; padding: 0 20px; }
.avatar-box { width: 90px; height: 90px; background: #fff; border: 1px solid #edf2f7; border-radius: 12px; padding: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); display: flex; align-items: center; justify-content: center; overflow: hidden; }
.pixel-avatar-img { width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }

.info-content { text-align: left; width: 100%; }
.info-alias { font-size: 20px; font-weight: 800; color: #1a202c; margin: 0 0 8px 0; letter-spacing: -0.5px; }
.info-desc { font-size: 13px; color: #718096; line-height: 1.5; margin: 0; display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }

.card-divider { height: 1px; background: radial-gradient(circle, #e2e8f0 0%, transparent 100%); margin: 15px 20px; }

.card-footer-new { padding: 0 20px 20px; display: flex; justify-content: space-between; align-items: center; }
.footer-brand { font-size: 16px; font-weight: 900; color: #1a1a1a; letter-spacing: -1px; }
.footer-tags-area { display: flex; gap: 4px; }
.footer-tag { font-size: 9px; font-weight: 700; background: #f1f5f9; color: #64748b; padding: 2px 6px; border-radius: 4px; border: 1px solid #e2e8f0; }
.back-header { background: #000; color: #fff; padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 900; }
.close-btn { background: none; border: none; color: #fff; cursor: pointer; font-size: 14px; }
.back-content { flex: 1; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.info-label { font-size: 9px; font-weight: 900; color: #999; text-transform: uppercase; margin-bottom: 4px; }
.prompt-box { font-size: 10px; background: #eee; padding: 8px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; line-height: 1.4; border: 1px solid #ddd; }
.tool-list { display: flex; flex-wrap: wrap; gap: 4px; }
.tool-badge { font-size: 9px; padding: 2px 6px; background: #e0f2fe; color: #0369a1; border-radius: 4px; font-weight: 700; }
.tool-badge.all { background: #dcfce7; color: #166534; }
.tool-badge.none { background: #fee2e2; color: #991b1b; }
.back-actions { padding: 12px; display: flex; justify-content: center; gap: 12px; }
.w-full { width: 100%; }
</style>
