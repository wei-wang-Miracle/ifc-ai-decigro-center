<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../utils/request'
import { Plus, Edit, Search, Refresh, Check, Close, Cpu } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// ============================================
// 第一部分：数据定义
// ============================================

interface UISwitches {
    visualDataEnable: boolean
    checkListEnable: boolean
    proposalsEnable: boolean
}

interface GenerationConstraints {
    predictiveForesightFocus: string[]
    executiveSummaryPerspectives: string[]
    visualDataPerspectives: string[]
    checkListDimensions: string[]
    proposalPerspectives: string[]
}

interface HumanReviewConfig {
    uiSwitches?: UISwitches
    generationConstraints?: GenerationConstraints
}

interface AgentCard {
    agentName: string
    agentAlias: string
    agentDescription: string
    agentTags: string[]
    agentType: string
    systemPrompt: string
    negativePrompt: string
    boundTools: string[] | null
    boundAgents: string[] | null
    reasoningFramework: string
    agentVersion: string
    isOnline: boolean
    requireReview: boolean
    humanReviewConfig: HumanReviewConfig | null
    managerBy: string
    createTime: string
    updateTime: string
}

// --- 列表相关 ---
const plannerList = ref<AgentCard[]>([])
const executorList = ref<AgentCard[]>([])
// 保存完整的 Executor 列表，用于在取消过滤时恢复
const fullExecutorList = ref<AgentCard[]>([])

const loading = ref(false)
const searchKeyword = ref('')
const searchTag = ref('')

// 当点击的 Planner 名称（用于高亮显示和过滤）
const activePlanner = ref<string>('')

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
    agentType: 'EXECUTOR',
    systemPrompt: '',
    negativePrompt: '',
    boundTools: null,
    boundAgents: [],
    reasoningFramework: 'ReAct',
    agentVersion: '1.0.0',
    isOnline: true,
    requireReview: false,
    humanReviewConfig: null,
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
const availableTools = ref<{ toolName: string; toolAlias: string | null }[]>([])
const availableExecutors = ref<string[]>([])
const newTag = ref('')

// --- 工具绑定模式: 'none'(不绑定) | 'specific'(白名单) ---
const boundToolsMode = ref<'none' | 'specific'>('none')

// --- 审核配置编辑状态 ---
const reviewConfigEnabled = ref(false)
// 约束维度输入框状态
const newConstraintItem = reactive<Record<string, string>>({
    predictiveForesightFocus: '',
    executiveSummaryPerspectives: '',
    visualDataPerspectives: '',
    checkListDimensions: '',
    proposalPerspectives: ''
})

// --- 智能体类型选项 ---
const agentTypeOptions = [
    { label: 'PLANNER (业务规划)', value: 'PLANNER' },
    { label: 'EXECUTOR (任务执行)', value: 'EXECUTOR' }
]

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
        const params: any = { page: 1, size: 999 } // Fetch all agents for front-end categorization
        if (searchKeyword.value) params.keyword = searchKeyword.value
        if (searchTag.value) params.tag = searchTag.value
        const res: any = await request.get('/agent/page', { params })
        const allCards: AgentCard[] = res.records || []
        
        plannerList.value = allCards.filter(c => c.agentType === 'PLANNER')
        fullExecutorList.value = allCards.filter(c => c.agentType === 'EXECUTOR')
        
        // 如果当前有激活的 Planner，且该 Planner 仍存在，则保留过滤状态
        // 否则显示所有 EXECUTOR
        if (activePlanner.value && plannerList.value.some(p => p.agentName === activePlanner.value)) {
           await loadBoundExecutors(activePlanner.value)
        } else {
           activePlanner.value = ''
           executorList.value = [...fullExecutorList.value]
        }

    } catch (e) {
        console.error('获取列表失败', e)
    } finally {
        loading.value = false
    }
}

const loadBoundExecutors = async (plannerName: string) => {
    try {
        loading.value = true
        activePlanner.value = plannerName
        const res: any = await request.get('/agent/executor-list', { params: { plannerName } })
        
        // 仅显示该 Planner 绑定的并且处于当前完整列表中的 executor（可能存在 keyword 搜索的交集处理）
        const boundNames = res.map((c: AgentCard) => c.agentName)
        executorList.value = fullExecutorList.value.filter(e => boundNames.includes(e.agentName))
    } catch (e) {
        console.error('获取绑定 executor 失败', e)
    } finally {
        loading.value = false
    }
}

const handlePlannerClick = async (plannerName: string) => {
    // 再次点击取消过滤
    if (activePlanner.value === plannerName) {
        activePlanner.value = ''
        executorList.value = [...fullExecutorList.value]
    } else {
        await loadBoundExecutors(plannerName)
    }
}

const handleSearch = () => {
    activePlanner.value = '' // Clear selection on search
    fetchList()
}

const fetchAvailableTools = async () => {
    try {
        const res: any = await request.get('/agent/available-tools')
        availableTools.value = res || []
    } catch (e) { console.error(e) }
}

const fetchAvailableExecutors = async () => {
    try {
        const res: any = await request.get('/agent/available-executors')
        availableExecutors.value = res || []
    } catch (e) { console.error(e) }
}

const handleAdd = () => {
    dialogTitle.value = '入职新智能体'
    isEdit.value = false
    resetForm()
    fetchAvailableTools()
    fetchAvailableExecutors()
    dialogVisible.value = true
}

const handleEdit = (card: AgentCard) => {
    dialogTitle.value = '修改智能体档案'
    isEdit.value = true
    Object.assign(form, JSON.parse(JSON.stringify(card)))
    if (!form.agentTags) form.agentTags = []
    if (!form.boundAgents) form.boundAgents = []
    // 回显工具绑定模式
    boundToolsMode.value = Array.isArray(form.boundTools) && form.boundTools.length > 0 ? 'specific' : 'none'
    if (boundToolsMode.value === 'none') form.boundTools = null
    // 回显审核配置
    reviewConfigEnabled.value = form.humanReviewConfig != null
    if (form.humanReviewConfig) {
        // 确保新版结构字段存在（兼容旧数据）
        if (!form.humanReviewConfig.uiSwitches) {
            form.humanReviewConfig.uiSwitches = { visualDataEnable: false, checkListEnable: false, proposalsEnable: false }
        }
        if (!form.humanReviewConfig.generationConstraints) {
            form.humanReviewConfig.generationConstraints = {
                predictiveForesightFocus: [],
                executiveSummaryPerspectives: [],
                visualDataPerspectives: [],
                checkListDimensions: [],
                proposalPerspectives: []
            }
        }
    }
    if (!form.humanReviewConfig) form.humanReviewConfig = null
    fetchAvailableTools()
    fetchAvailableExecutors()
    dialogVisible.value = true
}

const handleFlip = (name: string) => {
    if (flippedCards.value.has(name)) flippedCards.value.delete(name)
    else flippedCards.value.add(name)
}

const handleToggleOnline = async (card: AgentCard) => {
    const action = card.isOnline ? 'offline' : 'online'
    await request.put(`/agent/${action}/${card.agentName}`)
    ElMessage.success(card.isOnline ? '已离线' : '已就绪')
    fetchList()
}

const submitForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            // 不绑定模式时确保提交 null，而非残留的数组
            if (boundToolsMode.value === 'none') form.boundTools = null
            // 审核配置未开启时清空
            if (!reviewConfigEnabled.value) form.humanReviewConfig = null
            await request.post('/agent/save', form)
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
        agentType: 'EXECUTOR',
        systemPrompt: '',
        negativePrompt: '',
        boundTools: null,
        boundAgents: [],
        reasoningFramework: 'ReAct',
        agentVersion: '1.0.0',
        isOnline: true,
        requireReview: false,
        humanReviewConfig: null,
        managerBy: '',
        createTime: '',
        updateTime: ''
    })
    boundToolsMode.value = 'none'
    reviewConfigEnabled.value = false
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

const handleToggleReviewConfig = (enabled: boolean) => {
    if (enabled && !form.humanReviewConfig) {
        form.humanReviewConfig = {
            uiSwitches: { visualDataEnable: false, checkListEnable: false, proposalsEnable: false },
            generationConstraints: {
                predictiveForesightFocus: [],
                executiveSummaryPerspectives: [],
                visualDataPerspectives: [],
                checkListDimensions: [],
                proposalPerspectives: []
            }
        }
    }
}
const handleAddConstraintItem = (field: keyof GenerationConstraints) => {
    const val = newConstraintItem[field]?.trim()
    if (!val || !form.humanReviewConfig?.generationConstraints) return
    const list = form.humanReviewConfig.generationConstraints[field]
    if (!list.includes(val)) {
        list.push(val)
        newConstraintItem[field] = ''
    }
}
const handleRemoveConstraintItem = (field: keyof GenerationConstraints, item: string) => {
    if (!form.humanReviewConfig?.generationConstraints) return
    form.humanReviewConfig.generationConstraints[field] =
        form.humanReviewConfig.generationConstraints[field].filter(d => d !== item)
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
                <h3 class="header-title">MAS 智能体拓扑管理</h3>
                <p class="header-subtitle">PLANNER(规划者) / EXECUTOR(执行者) 联动编排</p>
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

    <!-- 主体区域：左侧 PLANNER (25%) / 右侧 EXECUTOR (75%) -->
    <div class="main-content" v-loading="loading">
        <!-- 左侧 Planner 列表 (1列) -->
        <div class="planner-column">
            <h4 class="column-title">规划者 (PLANNER)</h4>
            <div class="badge-wall planner-wall">
                <div 
                    v-for="(card, index) in plannerList" 
                    :key="card.agentName" 
                    class="badge-container entrance-swing"
                    :class="{ 
                        'is-flipped': flippedCards.has(card.agentName),
                        'is-active': activePlanner === card.agentName
                    }"
                    :style="{ animationDelay: `${index * 0.1}s` }"
                    @click="handlePlannerClick(card.agentName)">
                    <!-- 卡片内部复用 -->
            
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

                    <div v-if="card.requireReview" class="review-badge" title="需要人工审核">
                        <el-icon><Check /></el-icon> REVIEW
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
                        <button class="close-btn" @click.stop="handleFlip(card.agentName)">✕</button>
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
                        <div v-if="card.humanReviewConfig" class="info-section">
                            <div class="info-label">审核模块</div>
                            <div class="tool-list">
                                <template v-if="card.humanReviewConfig.uiSwitches">
                                    <span v-if="card.humanReviewConfig.uiSwitches.visualDataEnable" class="tool-badge review-dim">图表</span>
                                    <span v-if="card.humanReviewConfig.uiSwitches.checkListEnable" class="tool-badge review-dim">清单</span>
                                    <span v-if="card.humanReviewConfig.uiSwitches.proposalsEnable" class="tool-badge review-dim">方案</span>
                                    <span v-if="!card.humanReviewConfig.uiSwitches.visualDataEnable && !card.humanReviewConfig.uiSwitches.checkListEnable && !card.humanReviewConfig.uiSwitches.proposalsEnable" class="tool-badge none">纯文本模式</span>
                                </template>
                                <template v-else>
                                    <span class="tool-badge none">旧版配置</span>
                                </template>
                            </div>
                        </div>
                    </div>
                    <div class="back-actions">
                        <el-button circle :icon="card.isOnline ? Close : Check" :type="card.isOnline ? 'info' : 'success'" @click.stop="handleToggleOnline(card)" />
                        <el-button circle :icon="Edit" @click.stop="handleEdit(card)" />
                    </div>
                </div>
            </div>
        </div>
        </div>
        </div>

        <!-- 右侧 Executor 列表 (3列) -->
        <div class="executor-column">
            <h4 class="column-title">执行者 (EXECUTOR) <span v-if="activePlanner" class="filter-hint">- 当前筛选: {{ activePlanner }}</span></h4>
            <div class="badge-wall executor-wall">
                <div 
                    v-for="(card, index) in executorList" 
                    :key="card.agentName" 
                    class="badge-container entrance-swing"
                    :class="{ 'is-flipped': flippedCards.has(card.agentName) }"
                    :style="{ animationDelay: `${index * 0.05}s` }">
                    
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

                            <div v-if="card.requireReview" class="review-badge" title="需要人工审核">
                                <el-icon><Check /></el-icon> REVIEW
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
                                <button class="close-btn" @click.stop="handleFlip(card.agentName)">✕</button>
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
                                <div v-if="card.humanReviewConfig" class="info-section">
                                    <div class="info-label">审核模块</div>
                                    <div class="tool-list">
                                        <template v-if="card.humanReviewConfig.uiSwitches">
                                            <span v-if="card.humanReviewConfig.uiSwitches.visualDataEnable" class="tool-badge review-dim">图表</span>
                                            <span v-if="card.humanReviewConfig.uiSwitches.checkListEnable" class="tool-badge review-dim">清单</span>
                                            <span v-if="card.humanReviewConfig.uiSwitches.proposalsEnable" class="tool-badge review-dim">方案</span>
                                            <span v-if="!card.humanReviewConfig.uiSwitches.visualDataEnable && !card.humanReviewConfig.uiSwitches.checkListEnable && !card.humanReviewConfig.uiSwitches.proposalsEnable" class="tool-badge none">纯文本模式</span>
                                        </template>
                                        <template v-else>
                                            <span v-for="d in (card.humanReviewConfig.reviewDimensions || [])" :key="d" class="tool-badge review-dim">{{ d }}</span>
                                            <span v-if="!card.humanReviewConfig.reviewDimensions?.length" class="tool-badge none">旧版配置</span>
                                        </template>
                                    </div>
                                </div>
                            </div>
                            <div class="back-actions">
                                <el-button circle :icon="card.isOnline ? Close : Check" :type="card.isOnline ? 'info' : 'success'" @click.stop="handleToggleOnline(card)" />
                                <el-button circle :icon="Edit" @click.stop="handleEdit(card)" />
                            </div>
                        </div>
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
            <el-row :gutter="20">
                <el-col :span="12">
                    <el-form-item label="智能体类型" prop="agentType">
                        <el-select v-model="form.agentType" class="w-full">
                            <el-option v-for="o in agentTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
                        </el-select>
                    </el-form-item>
                </el-col>
            </el-row>
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
                    <el-form-item label="人工审核">
                        <el-switch v-model="form.requireReview" active-text="开启" inactive-text="关闭" />
                    </el-form-item>
                </el-col>
            </el-row>
            <!-- 审核配置（独立于 requireReview 开关） -->
            <el-form-item label="审核配置">
                <div class="review-config-wrap">
                    <el-switch v-model="reviewConfigEnabled" active-text="配置结构化审核" inactive-text="不配置" @change="handleToggleReviewConfig" />
                    <template v-if="reviewConfigEnabled && form.humanReviewConfig">
                        <!-- UI 模块开关 -->
                        <div class="review-config-section">
                            <div class="review-config-label">审核模块开关</div>
                            <div class="flex flex-wrap gap-4 mt-1">
                                <el-checkbox v-model="form.humanReviewConfig.uiSwitches!.visualDataEnable">数据可视化 (ECharts)</el-checkbox>
                                <el-checkbox v-model="form.humanReviewConfig.uiSwitches!.checkListEnable">审核清单 (CheckList)</el-checkbox>
                                <el-checkbox v-model="form.humanReviewConfig.uiSwitches!.proposalsEnable">建议方案 (Proposals)</el-checkbox>
                            </div>
                        </div>
                        <!-- 生成约束维度 -->
                        <div class="review-config-section">
                            <div class="review-config-label">深度洞察方向</div>
                            <el-input v-model="newConstraintItem.predictiveForesightFocus" size="small" placeholder="如：合规风险预期、潜在业务穿透影响，Enter 添加" @keyup.enter="handleAddConstraintItem('predictiveForesightFocus')" class="mb-2" />
                            <div class="flex flex-wrap gap-1">
                                <el-tag v-for="d in form.humanReviewConfig.generationConstraints!.predictiveForesightFocus" :key="d" closable size="small" type="danger" @close="handleRemoveConstraintItem('predictiveForesightFocus', d)">{{ d }}</el-tag>
                            </div>
                        </div>
                        <div class="review-config-section">
                            <div class="review-config-label">摘要约束视角</div>
                            <el-input v-model="newConstraintItem.executiveSummaryPerspectives" size="small" placeholder="如：风险、收益、合规，Enter 添加" @keyup.enter="handleAddConstraintItem('executiveSummaryPerspectives')" class="mb-2" />
                            <div class="flex flex-wrap gap-1">
                                <el-tag v-for="d in form.humanReviewConfig.generationConstraints!.executiveSummaryPerspectives" :key="d" closable size="small" type="warning" @close="handleRemoveConstraintItem('executiveSummaryPerspectives', d)">{{ d }}</el-tag>
                            </div>
                        </div>
                        <div v-if="form.humanReviewConfig.uiSwitches!.visualDataEnable" class="review-config-section">
                            <div class="review-config-label">图表约束视角</div>
                            <el-input v-model="newConstraintItem.visualDataPerspectives" size="small" placeholder="如：业绩走势、风险分布，Enter 添加" @keyup.enter="handleAddConstraintItem('visualDataPerspectives')" class="mb-2" />
                            <div class="flex flex-wrap gap-1">
                                <el-tag v-for="d in form.humanReviewConfig.generationConstraints!.visualDataPerspectives" :key="d" closable size="small" type="info" @close="handleRemoveConstraintItem('visualDataPerspectives', d)">{{ d }}</el-tag>
                            </div>
                        </div>
                        <div v-if="form.humanReviewConfig.uiSwitches!.checkListEnable" class="review-config-section">
                            <div class="review-config-label">审核清单维度</div>
                            <el-input v-model="newConstraintItem.checkListDimensions" size="small" placeholder="如：公告一致性、基金经理变更，Enter 添加" @keyup.enter="handleAddConstraintItem('checkListDimensions')" class="mb-2" />
                            <div class="flex flex-wrap gap-1">
                                <el-tag v-for="d in form.humanReviewConfig.generationConstraints!.checkListDimensions" :key="d" closable size="small" type="warning" @close="handleRemoveConstraintItem('checkListDimensions', d)">{{ d }}</el-tag>
                            </div>
                        </div>
                        <div v-if="form.humanReviewConfig.uiSwitches!.proposalsEnable" class="review-config-section">
                            <div class="review-config-label">建议方案视角</div>
                            <el-input v-model="newConstraintItem.proposalPerspectives" size="small" placeholder="如：合规、业务优化，Enter 添加" @keyup.enter="handleAddConstraintItem('proposalPerspectives')" class="mb-2" />
                            <div class="flex flex-wrap gap-1">
                                <el-tag v-for="d in form.humanReviewConfig.generationConstraints!.proposalPerspectives" :key="d" closable size="small" type="success" @close="handleRemoveConstraintItem('proposalPerspectives', d)">{{ d }}</el-tag>
                            </div>
                        </div>
                    </template>
                    <div v-if="!reviewConfigEnabled" class="no-tool-hint">未配置时，触发审核将使用系统默认的纯文本结论提取</div>
                </div>
            </el-form-item>
            <el-row :gutter="20">
                <el-col :span="12">
                    <el-form-item label="标签">
                        <el-input v-model="newTag" size="small" placeholder="Enter添加" @keyup.enter="handleAddTag" class="mb-2" />
                        <div class="flex flex-wrap gap-1">
                            <el-tag v-for="t in form.agentTags" :key="t" closable size="small" @close="handleRemoveTag(t)">{{ t }}</el-tag>
                        </div>
                    </el-form-item>
                </el-col>
            </el-row>
            <el-form-item label="执行器绑定" v-if="form.agentType === 'PLANNER'">
                <el-select 
                    v-model="form.boundAgents" 
                    multiple 
                    placeholder="选择可用的 Executor (子节点)"
                    class="w-full">
                    <el-option v-for="a in availableExecutors" :key="a" :label="a" :value="a" />
                </el-select>
            </el-form-item>

            <el-form-item label="工具绑定" v-if="form.agentType === 'EXECUTOR'">
                <div class="tool-bind-wrap">
                    <el-radio-group v-model="boundToolsMode" @change="() => { if (boundToolsMode === 'none') form.boundTools = null; else form.boundTools = [] }" class="tool-mode-radio">
                        <el-radio value="none">不绑定工具</el-radio>
                        <el-radio value="specific">指定工具白名单</el-radio>
                    </el-radio-group>
                    <template v-if="boundToolsMode === 'specific'">
                        <el-select
                            v-model="form.boundTools"
                            multiple
                            collapse-tags
                            collapse-tags-tooltip
                            placeholder="请选择绑定的工具（支持 protected 权限工具）"
                            class="w-full mt-2">
                            <el-option v-for="t in availableTools" :key="t.toolName" :label="t.toolAlias ? `${t.toolAlias} (${t.toolName})` : t.toolName" :value="t.toolName" />
                        </el-select>
                        <div v-if="form.boundTools && form.boundTools.length > 0" class="selected-tools-preview">
                            <span v-for="t in form.boundTools" :key="t" class="selected-tool-tag">{{ t }}</span>
                        </div>
                    </template>
                    <div v-else class="no-tool-hint">Agent 将不使用任何工具，仅进行纯文本推理</div>
                </div>
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
.agent-registry { height: 100%; display: flex; flex-direction: column; gap: 10px; font-family: 'Inter', sans-serif; }
.header-bar { background: #fff; border: 2px solid #000; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 4px 4px 0 #000; }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-icon { width: 40px; height: 40px; background: #000; display: flex; align-items: center; justify-content: center; border-radius: 4px; }
.header-title { font-weight: 800; font-size: 18px; margin: 0; }
.header-subtitle { font-size: 12px; color: #666; margin: 0; font-family: monospace; }
.badge-container { display: flex; flex-direction: column; align-items: center; perspective: 1000px; transform-origin: top center; cursor: pointer; transition: transform 0.2s; }

/* 布局调整 */
.main-content { flex: 1; display: flex; gap: 16px; padding: 12px; overflow-y: hidden; background: #f8faff; height: 0; min-height: 0;}
.planner-column { flex: 1; display: flex; flex-direction: column; background: #fff; border-radius: 12px; border: 2px solid #e2e8f0; overflow: hidden; }
.executor-column { flex: 3; display: flex; flex-direction: column; background: #fff; border-radius: 12px; border: 2px solid #e2e8f0; overflow: hidden; }

.column-title { margin: 0; padding: 10px 14px; font-size: 13px; font-weight: 800; border-bottom: 2px solid #e2e8f0; background: #f1f5f9; display: flex; align-items: center;}
.filter-hint { margin-left: auto; color: #f59e0b; font-size: 12px; background: #fef3c7; padding: 2px 8px; border-radius: 4px; border: 1px solid #fcd34d; font-weight: normal; }

.badge-wall { flex: 1; overflow-y: auto; padding: 28px 16px; }
/* 强制列数 */
.planner-wall { display: grid; grid-template-columns: repeat(1, 1fr); gap: 48px 12px; justify-items: center; }
/* >= 3列的弹性网格 */
.executor-wall { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 48px 20px; justify-items: center; }

/* 选中 Planner 高亮提示 */
.badge-container.is-active .badge-front { border-color: #f59e0b; box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.3); }

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

.review-badge { position: absolute; top: 15px; right: 45px; font-size: 8px; font-weight: 900; color: #ff9800; display: flex; align-items: center; gap: 2px; border: 1px solid #ff9800; padding: 1px 4px; border-radius: 4px; }

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
.tool-badge.review-dim { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.back-actions { padding: 12px; display: flex; justify-content: center; gap: 12px; }
.tool-bind-wrap { width: 100%; display: flex; flex-direction: column; gap: 8px; }
.tool-mode-radio { display: flex; gap: 24px; }
.no-tool-hint { font-size: 12px; color: #999; background: #f9f9f9; border: 1px dashed #ddd; border-radius: 6px; padding: 8px 12px; }
.selected-tools-preview { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.selected-tool-tag { font-size: 11px; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; border-radius: 4px; padding: 2px 8px; font-weight: 600; }
.review-config-wrap { width: 100%; display: flex; flex-direction: column; gap: 10px; }
.review-config-section { display: flex; flex-direction: column; gap: 4px; }
.review-config-label { font-size: 12px; font-weight: 600; color: #666; }
.w-full { width: 100%; }
</style>
