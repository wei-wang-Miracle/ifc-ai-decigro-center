<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import request from '../../utils/request'
import { Plus, Edit, Delete, Search, Refresh, Check, Close } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// ============================================
// 第一部分：数据定义
// ============================================

// --- 接口类型定义 ---
interface ToolParameter {
    param_name: string
    param_type: string
    param_description: string
    param_required: boolean
    param_example: string
}

interface ToolCard {
    toolName: string
    toolDescription: string
    toolTags: string[]
    toolVersion: string
    toolPrivileges: string
    toolProtocol: string
    urlPath: string
    referenceTarget: string
    toolParameters: ToolParameter[]  // 入参定义
    outputSchema: ToolParameter[]    // 出参定义（结构与入参相同）
    inputExamples: string            // 输入示例（TEXT）
    outputExamples: string           // 输出示例（TEXT）
    isOnline: boolean
    createTime: string
    updateTime: string
    managerBy: string
}

// --- 列表相关 ---
const cardList = ref<ToolCard[]>([])  // 卡片列表数据
const loading = ref(false)
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(12)
const searchKeyword = ref('')
const searchTag = ref('')

// --- 表单相关 ---
const dialogVisible = ref(false)
const dialogTitle = ref('')
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<ToolCard>({
    toolName: '',
    toolDescription: '',
    toolTags: [],
    toolVersion: '1.0.0',
    toolPrivileges: 'public',
    toolProtocol: 'http',
    urlPath: '',
    referenceTarget: '',
    toolParameters: [],
    outputSchema: [],
    inputExamples: '',
    outputExamples: '',
    isOnline: false,
    createTime: '',
    updateTime: '',
    managerBy: ''
})

const formRules = reactive<FormRules>({
    toolName: [
        { required: true, message: '请输入工具名称', trigger: 'blur' },
        { pattern: /^[a-z0-9_]+$/, message: '仅支持小写字母、数字、下划线', trigger: 'blur' }
    ],
    toolDescription: [{ required: true, message: '请输入工具描述', trigger: 'blur' }],
    toolProtocol: [{ required: true, message: '请选择协议', trigger: 'change' }]
})

// --- 详情预览抽屉 ---
const previewVisible = ref(false)
const previewData = ref<ToolCard | null>(null)

// --- 标签输入 ---
const newTag = ref('')

// --- 协议类型选项 ---
const protocolOptions = [
    { label: 'HTTP 接口', value: 'http' },
    { label: '内部引用', value: 'reference' }
]

// --- 权限选项 ---
const privilegesOptions = [
    { label: '公开', value: 'public' },
    { label: '受保护', value: 'protected' }
]

// --- 参数类型选项 ---
const paramTypeOptions = ['string', 'number', 'boolean', 'array', 'object']

// ============================================
// 第二部分：计算属性
// ============================================

// 转换为 OpenAI Function Schema 格式预览
const schemaPreview = computed(() => {
    const properties: any = {}
    const required: string[] = []
    
    form.toolParameters.forEach(param => {
        properties[param.param_name] = {
            type: param.param_type,
            description: param.param_description
        }
        if (param.param_required) {
            required.push(param.param_name)
        }
    })
    
    return {
        name: form.toolName,
        description: form.toolDescription,
        parameters: {
            type: 'object',
            properties,
            required
        }
    }
})

// 转换为 Output Schema 格式预览
const outputSchemaPreview = computed(() => {
    const properties: any = {}
    
    form.outputSchema.forEach(param => {
        properties[param.param_name] = {
            type: param.param_type,
            description: param.param_description
        }
    })
    
    return {
        type: 'object',
        properties
    }
})


// ============================================
// 第三部分：接口调用
// ============================================

// --- 获取工具列表 ---
const fetchList = async () => {
    loading.value = true
    try {
        const params: any = {
            page: pageNum.value,
            size: pageSize.value
        }
        if (searchKeyword.value) {
            params.keyword = searchKeyword.value
        }
        if (searchTag.value) {
            params.tag = searchTag.value
        }
        const res: any = await request.get('/tool/page', { params })
        cardList.value = res.records || []
        total.value = res.totalRow || 0
    } catch (e) {
        console.error('获取工具列表失败', e)
    } finally {
        loading.value = false
    }
}

// ============================================
// 第四部分：交互方法
// ============================================

// --- 搜索 ---
const handleSearch = () => {
    pageNum.value = 1
    fetchList()
}

// --- 新增工具 ---
const handleAdd = () => {
    isEdit.value = false
    dialogTitle.value = '注册工具'
    resetForm()
    dialogVisible.value = true
}

// --- 编辑工具 ---
const handleEdit = (card: ToolCard) => {
    isEdit.value = true
    dialogTitle.value = '编辑工具'
    Object.assign(form, JSON.parse(JSON.stringify(card)))
    // 确保字段存在
    if (!form.toolParameters) form.toolParameters = []
    if (!form.outputSchema) form.outputSchema = []
    if (!form.toolTags) form.toolTags = []
    if (!form.inputExamples) form.inputExamples = ''
    if (!form.outputExamples) form.outputExamples = ''
    dialogVisible.value = true
}

// --- 删除工具 ---
const handleDelete = (card: ToolCard) => {
    ElMessageBox.confirm(
        `确定要删除工具 "${card.toolName}" 吗？`,
        '警告',
        {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
        }
    ).then(async () => {
        try {
            await request.delete(`/tool/remove/${card.toolName}`)
            ElMessage.success('删除成功')
            fetchList()
        } catch (e) {
            console.error('删除失败', e)
        }
    })
}

// --- 查看详情 ---
const handleView = (card: ToolCard) => {
    previewData.value = card
    previewVisible.value = true
}

// --- 上线/下线 ---
const handleToggleOnline = async (card: ToolCard) => {
    try {
        const action = card.isOnline ? 'offline' : 'online'
        await request.put(`/tool/${action}/${card.toolName}`)
        ElMessage.success(card.isOnline ? '已下线' : '已上线')
        fetchList()
    } catch (e) {
        console.error('状态切换失败', e)
    }
}

// --- 保存工具 ---
const submitForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            try {
                await request.post('/tool/save', form)
                ElMessage.success(`${dialogTitle.value}成功`)
                dialogVisible.value = false
                fetchList()
            } catch (e: any) {
                ElMessage.error(e.message || '保存失败')
            }
        }
    })
}

const resetForm = () => {
    Object.assign(form, {
        toolName: '',
        toolDescription: '',
        toolTags: [],
        toolVersion: '1.0.0',
        toolPrivileges: 'public',
        toolProtocol: 'http',
        urlPath: '',
        referenceTarget: '',
        toolParameters: [],
        outputSchema: [],
        inputExamples: '',
        outputExamples: '',
        isOnline: false,
        createTime: '',
        updateTime: '',
        managerBy: ''
    })
    formRef.value?.resetFields()
}

// --- 参数管理 ---
const handleAddParam = () => {
    form.toolParameters.push({
        param_name: '',
        param_type: 'string',
        param_description: '',
        param_required: false,
        param_example: ''
    })
}

const handleRemoveParam = (index: number) => {
    form.toolParameters.splice(index, 1)
}

// --- 出参管理（outputSchema） ---
const handleAddOutput = () => {
    form.outputSchema.push({
        param_name: '',
        param_type: 'string',
        param_description: '',
        param_required: false,
        param_example: ''
    })
}

const handleRemoveOutput = (index: number) => {
    form.outputSchema.splice(index, 1)
}

// --- 标签管理 ---
const handleAddTag = () => {
    if (newTag.value && !form.toolTags.includes(newTag.value)) {
        form.toolTags.push(newTag.value)
        newTag.value = ''
    }
}

const handleRemoveTag = (tag: string) => {
    const index = form.toolTags.indexOf(tag)
    if (index > -1) {
        form.toolTags.splice(index, 1)
    }
}

// --- 分页 ---
const handlePageChange = (page: number) => {
    pageNum.value = page
    fetchList()
}

// ============================================
// 第五部分：生命周期
// ============================================

onMounted(() => {
    fetchList()
})
</script>

<template>
  <div class="tool-registry">
    <!-- 顶部操作栏 -->
    <div class="header-bar">
        <!-- 左侧：标题与新增 -->
        <div class="header-left">
            <div class="header-icon">
                <span class="pixel-icon">▣</span>
            </div>
            <div class="header-info">
                <h3 class="header-title">MAS 工具注册中心</h3>
                <p class="header-subtitle">共 {{ total }} 个工具</p>
            </div>
            <el-button type="primary" :icon="Plus" @click="handleAdd" class="add-btn">
                注册工具
            </el-button>
        </div>
        
        <!-- 右侧：搜索 -->
        <div class="header-right">
            <el-input
                v-model="searchKeyword"
                placeholder="名称/描述"
                :prefix-icon="Search"
                clearable
                style="width: 140px"
                @keyup.enter="handleSearch"
                @clear="handleSearch"
                class="search-input" />
            <el-input
                v-model="searchTag"
                placeholder="标签"
                clearable
                style="width: 100px"
                @keyup.enter="handleSearch"
                @clear="handleSearch"
                class="search-input" />
            <el-button :icon="Search" @click="handleSearch" class="action-btn" />
            <el-button :icon="Refresh" @click="fetchList" class="action-btn" />
        </div>
    </div>

    <!-- 卡片网格 -->
    <div class="card-grid" v-loading="loading">
        <div 
            v-for="(card, index) in cardList" 
            :key="card.toolName ?? `temp-${index}`" 
            class="tool-card"
            :class="{ 'is-online': card.isOnline }"
            @click="handleView(card)">
            
            <!-- 像素状态灯 -->
            <div class="status-indicator" :class="card.isOnline ? 'online' : 'offline'">
                <span class="pixel"></span>
                <span class="pixel"></span>
                <span class="pixel"></span>
                <span class="pixel"></span>
                <span class="pixel center"></span>
                <span class="pixel"></span>
                <span class="pixel"></span>
                <span class="pixel"></span>
                <span class="pixel"></span>
            </div>
            
            <!-- 协议标签 -->
            <div class="protocol-badge">
                {{ card.toolProtocol === 'http' ? 'HTTP' : 'REF' }}
            </div>
            
            <!-- 卡片内容 -->
            <div class="card-content">
                <h4 class="card-title">{{ card.toolName }}</h4>
                <p class="card-desc">{{ card.toolDescription }}</p>
                
                <!-- 标签 -->
                <div class="card-tags" v-if="card.toolTags && card.toolTags.length">
                    <span v-for="tag in card.toolTags.slice(0, 3)" :key="tag" class="pixel-tag">
                        {{ tag }}
                    </span>
                    <span v-if="card.toolTags.length > 3" class="pixel-tag more">
                        +{{ card.toolTags.length - 3 }}
                    </span>
                </div>
                
                <!-- 版本 -->
                <div class="card-version">
                    VER {{ card.toolVersion }}
                </div>
            </div>
            
            <!-- 操作区 -->
            <div class="card-actions" @click.stop>
                <el-button 
                    :icon="card.isOnline ? Close : Check" 
                    size="small" 
                    :type="card.isOnline ? 'danger' : 'success'"
                    circle
                    @click="handleToggleOnline(card)" />
                <el-button :icon="Edit" size="small" circle @click="handleEdit(card)" />
                <el-button :icon="Delete" size="small" type="danger" circle @click="handleDelete(card)" />
            </div>
        </div>
        
        <!-- 空状态 -->
        <div v-if="!loading && cardList.length === 0" class="empty-state">
            <div class="pixel-icon large">□</div>
            <p>暂无工具，点击"注册工具"开始添加</p>
        </div>
    </div>

    <!-- 分页 -->
    <div class="pagination-bar" v-if="total > pageSize">
        <el-pagination
            background
            layout="prev, pager, next"
            :total="total"
            :page-size="pageSize"
            :current-page="pageNum"
            @current-change="handlePageChange" />
    </div>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="720px" class="tool-dialog">
        <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px" class="tool-form">
            <!-- 基本信息 -->
            <div class="form-section">
                <div class="section-title">▸ 基本信息</div>
                <el-row :gutter="16">
                    <el-col :span="12">
                        <el-form-item label="工具名称" prop="toolName">
                            <el-input 
                                v-model="form.toolName" 
                                placeholder="snake_case 格式"
                                :disabled="isEdit"
                                class="mono-input" />
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="版本号">
                            <el-input v-model="form.toolVersion" placeholder="1.0.0" class="mono-input" />
                        </el-form-item>
                    </el-col>
                </el-row>
                <el-form-item label="工具描述" prop="toolDescription">
                    <el-input 
                        v-model="form.toolDescription" 
                        type="textarea" 
                        :rows="3" 
                        placeholder="包含 Trigger(何时用) / Action(做什么) / Constraint(限制)" />
                </el-form-item>
                <el-row :gutter="16">
                    <el-col :span="12">
                        <el-form-item label="权限级别">
                            <el-select v-model="form.toolPrivileges" class="w-full">
                                <el-option 
                                    v-for="opt in privilegesOptions" 
                                    :key="opt.value" 
                                    :label="opt.label" 
                                    :value="opt.value" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="12">
                        <el-form-item label="标签">
                            <div class="tag-input-group">
                                <el-input v-model="newTag" placeholder="添加标签" size="small" @keyup.enter="handleAddTag" />
                                <el-button size="small" @click="handleAddTag">+</el-button>
                            </div>
                            <div class="tag-list">
                                <el-tag 
                                    v-for="tag in form.toolTags" 
                                    :key="tag" 
                                    closable 
                                    size="small"
                                    @close="handleRemoveTag(tag)">
                                    {{ tag }}
                                </el-tag>
                            </div>
                        </el-form-item>
                    </el-col>
                </el-row>
            </div>
            
            <!-- 协议配置 -->
            <div class="form-section">
                <div class="section-title">▸ 协议配置</div>
                <el-row :gutter="16">
                    <el-col :span="8">
                        <el-form-item label="协议类型" prop="toolProtocol">
                            <el-select v-model="form.toolProtocol" class="w-full">
                                <el-option 
                                    v-for="opt in protocolOptions" 
                                    :key="opt.value" 
                                    :label="opt.label" 
                                    :value="opt.value" />
                            </el-select>
                        </el-form-item>
                    </el-col>
                    <el-col :span="16">
                        <el-form-item v-if="form.toolProtocol === 'http'" label="URL Path">
                            <el-input v-model="form.urlPath" placeholder="/api/v1/xxx" class="mono-input" />
                        </el-form-item>
                        <el-form-item v-else label="引用目标">
                            <el-input v-model="form.referenceTarget" placeholder="目标服务/表名" class="mono-input" />
                        </el-form-item>
                    </el-col>
                </el-row>
            </div>
            
            <!-- 参数配置 -->
            <div class="form-section">
                <div class="section-title">
                    ▸ 参数配置
                    <el-button size="small" :icon="Plus" @click="handleAddParam">添加参数</el-button>
                </div>
                <el-table :data="form.toolParameters" border size="small" class="param-table">
                    <el-table-column label="参数名" width="130">
                        <template #default="scope">
                            <el-input v-model="scope.row.param_name" size="small" class="mono-input" />
                        </template>
                    </el-table-column>
                    <el-table-column label="类型" width="100">
                        <template #default="scope">
                            <el-select v-model="scope.row.param_type" size="small">
                                <el-option v-for="t in paramTypeOptions" :key="t" :label="t" :value="t" />
                            </el-select>
                        </template>
                    </el-table-column>
                    <el-table-column label="描述">
                        <template #default="scope">
                            <el-input v-model="scope.row.param_description" size="small" />
                        </template>
                    </el-table-column>
                    <el-table-column label="必填" width="60" align="center">
                        <template #default="scope">
                            <el-checkbox v-model="scope.row.param_required" />
                        </template>
                    </el-table-column>
                    <el-table-column label="示例" width="120">
                        <template #default="scope">
                            <el-input v-model="scope.row.param_example" size="small" class="mono-input" />
                        </template>
                    </el-table-column>
                    <el-table-column label="" width="50">
                        <template #default="scope">
                            <el-button link type="danger" :icon="Delete" @click="handleRemoveParam(scope.$index)" />
                        </template>
                    </el-table-column>
                </el-table>
            </div>
            
            <!-- 出参配置（Output Schema） -->
            <div class="form-section">
                <div class="section-title">
                    ▸ 出参配置（返回值结构）
                    <el-button size="small" :icon="Plus" @click="handleAddOutput">添加出参</el-button>
                </div>
                <el-table :data="form.outputSchema" border size="small" class="param-table">
                    <el-table-column label="字段名" width="130">
                        <template #default="scope">
                            <el-input v-model="scope.row.param_name" size="small" class="mono-input" />
                        </template>
                    </el-table-column>
                    <el-table-column label="类型" width="100">
                        <template #default="scope">
                            <el-select v-model="scope.row.param_type" size="small">
                                <el-option v-for="t in paramTypeOptions" :key="t" :label="t" :value="t" />
                            </el-select>
                        </template>
                    </el-table-column>
                    <el-table-column label="描述">
                        <template #default="scope">
                            <el-input v-model="scope.row.param_description" size="small" />
                        </template>
                    </el-table-column>
                    <el-table-column label="示例" width="120">
                        <template #default="scope">
                            <el-input v-model="scope.row.param_example" size="small" class="mono-input" />
                        </template>
                    </el-table-column>
                    <el-table-column label="" width="50">
                        <template #default="scope">
                            <el-button link type="danger" :icon="Delete" @click="handleRemoveOutput(scope.$index)" />
                        </template>
                    </el-table-column>
                </el-table>
            </div>
            
            <!-- Few-Shot 样本（可选） -->
            <el-collapse class="fewshot-collapse">
                <el-collapse-item>
                    <template #title>
                        <span class="collapse-title">▸ Few-Shot 样本（可选增量）</span>
                    </template>
                    <div class="fewshot-section">
                        <el-row :gutter="16">
                            <el-col :span="12">
                                <div class="fewshot-label">输入示例 (Input Examples)</div>
                                <el-input
                                    v-model="form.inputExamples"
                                    type="textarea"
                                    :rows="5"
                                    placeholder="可填入任意文本或 JSON，用于描述用户可能的提问方式"
                                    class="mono-textarea" />
                                <div class="fewshot-hint">可填入任意文本含 JSON，用于信息补充</div>
                            </el-col>
                            <el-col :span="12">
                                <div class="fewshot-label">输出示例 (Output Examples)</div>
                                <el-input
                                    v-model="form.outputExamples"
                                    type="textarea"
                                    :rows="5"
                                    placeholder="可填入任意文本或 JSON，用于描述工具返回数据结构"
                                    class="mono-textarea" />
                                <div class="fewshot-hint">可填入任意文本含 JSON，用于信息补充</div>
                            </el-col>
                        </el-row>
                    </div>
                </el-collapse-item>
            </el-collapse>
            
            <!-- Schema 预览 -->
            <div class="form-section">
                <el-tabs type="border-card" class="schema-tabs">
                    <el-tab-pane label="OpenAI Function Schema (Input)">
                        <pre class="schema-preview">{{ JSON.stringify(schemaPreview, null, 2) }}</pre>
                    </el-tab-pane>
                    <el-tab-pane label="Output Schema (Return)">
                        <pre class="schema-preview">{{ JSON.stringify(outputSchemaPreview, null, 2) }}</pre>
                    </el-tab-pane>
                </el-tabs>
            </div>
        </el-form>
        <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitForm(formRef)">保存</el-button>
        </template>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer v-model="previewVisible" title="工具详情" size="640px" class="detail-drawer">
        <template v-if="previewData">
            <div class="preview-header-box">
                <div class="preview-title-row">
                    <span class="preview-name">{{ previewData.toolName }}</span>
                    <el-tag :type="previewData.isOnline ? 'success' : 'info'" effect="dark" size="small" class="mono-tag">
                        {{ previewData.isOnline ? 'ONLINE' : 'DRAFT' }}
                    </el-tag>
                    <span class="preview-version">v{{ previewData.toolVersion }}</span>
                </div>
                <div class="preview-desc-row">{{ previewData.toolDescription }}</div>
                <div class="preview-tags-row" v-if="previewData.toolTags && previewData.toolTags.length">
                    <el-tag v-for="tag in previewData.toolTags" :key="tag" type="info" size="small" class="tag-item">{{ tag }}</el-tag>
                </div>
            </div>
            
            <div class="preview-content">
                <div class="info-grid">
                    <div class="info-item">
                        <div class="label">协议类型</div>
                        <div class="value mono">{{ previewData.toolProtocol.toUpperCase() }}</div>
                    </div>
                    <div class="info-item">
                        <div class="label">权限级别</div>
                        <div class="value">{{ previewData.toolPrivileges === 'public' ? '公开' : '受保护' }}</div>
                    </div>
                    <div class="info-item full">
                        <div class="label">{{ previewData.toolProtocol === 'http' ? 'URL Path' : '引用目标' }}</div>
                        <div class="value mono">{{ previewData.toolProtocol === 'http' ? previewData.urlPath : previewData.referenceTarget }}</div>
                    </div>
                </div>

                <!-- 这是一个分割线 -->
                <div class="divider"></div>

                <!-- 入参定义 -->
                <div class="section-block">
                    <div class="block-title">▸ 参数定义 (Parameters)</div>
                    <el-table 
                        v-if="previewData.toolParameters?.length"
                        :data="previewData.toolParameters" 
                        border 
                        size="small" 
                        class="preview-table">
                        <el-table-column prop="param_name" label="参数名" width="140" />
                        <el-table-column prop="param_type" label="类型" width="80" />
                        <el-table-column prop="param_required" label="必填" width="60" align="center">
                            <template #default="{ row }">
                                <span v-if="row.param_required" style="color:#f56c6c">•</span>
                            </template>
                        </el-table-column>
                        <el-table-column prop="param_description" label="描述" />
                    </el-table>
                    <div v-else class="empty-text">无入参定义</div>
                </div>

                <!-- 出参定义 -->
                <div class="section-block">
                    <div class="block-title">▸ 出参定义 (Output Schema)</div>
                    <el-table 
                        v-if="previewData.outputSchema?.length"
                        :data="previewData.outputSchema" 
                        border 
                        size="small" 
                        class="preview-table">
                        <el-table-column prop="param_name" label="字段名" width="140" />
                        <el-table-column prop="param_type" label="类型" width="80" />
                        <el-table-column prop="param_description" label="描述" />
                    </el-table>
                    <div v-else class="empty-text">无出参定义</div>
                </div>

                <!-- 示例 -->
                <div class="section-block" v-if="previewData.inputExamples || previewData.outputExamples">
                    <el-tabs type="card" class="example-tabs">
                        <el-tab-pane label="输入示例" v-if="previewData.inputExamples">
                            <pre class="code-block">{{ previewData.inputExamples }}</pre>
                        </el-tab-pane>
                        <el-tab-pane label="输出示例" v-if="previewData.outputExamples">
                            <pre class="code-block">{{ previewData.outputExamples }}</pre>
                        </el-tab-pane>
                    </el-tabs>
                </div>
            </div>
        </template>
    </el-drawer>
  </div>
</template>

<style scoped>
/* ============================================
   极简复古像素风格 - MAS Tool Registry
   ============================================ */

/* --- 基础布局 --- */
.tool-registry {
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* --- 顶部操作栏 --- */
.header-bar {
    background: #fff;
    border: 1px solid #1a1a1a;
    border-radius: 2px;
    padding: 16px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: 2px 2px 0 rgba(0,0,0,0.1);
}

.header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.header-icon {
    width: 40px;
    height: 40px;
    background: #1a1a1a;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 2px;
}

.pixel-icon {
    color: #4ade80;
    font-size: 20px;
    font-family: 'Courier New', monospace;
    font-weight: bold;
}

.pixel-icon.large {
    font-size: 48px;
    color: #9ca3af;
}

.header-info {
    min-width: 0;
}

.header-title {
    font-size: 16px;
    font-weight: 700;
    color: #1a1a1a;
    margin: 0;
    font-family: 'Inter', sans-serif;
    letter-spacing: -0.02em;
}

.header-subtitle {
    font-size: 11px;
    color: #6b7280;
    margin: 2px 0 0;
    font-family: 'JetBrains Mono', monospace;
}

.add-btn {
    border-radius: 2px !important;
    font-weight: 600;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

.search-input :deep(.el-input__wrapper) {
    border-radius: 2px;
    border: 1px solid #d1d5db;
}

.action-btn {
    border-radius: 2px !important;
    border: 1px solid #d1d5db !important;
}

/* --- 卡片网格 --- */
.card-grid {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    align-content: start;
    gap: 16px;
    overflow-y: auto;
    padding: 4px;
}

/* --- 工具卡片 --- */
.tool-card {
    background: #fff;
    border: 1px solid #1a1a1a;
    border-radius: 2px;
    padding: 16px;
    position: relative;
    cursor: pointer;
    transition: all 0.15s ease;
    box-shadow: 2px 2px 0 rgba(0,0,0,0.08);
}

.tool-card:hover {
    border-width: 2px;
    padding: 15px;
    box-shadow: 3px 3px 0 rgba(0,0,0,0.12);
}

/* 扫描线效果 */
.tool-card:hover::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 100%;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(0,0,0,0.03) 2px,
        rgba(0,0,0,0.03) 4px
    );
    pointer-events: none;
    animation: scanline 0.5s ease-out;
}

@keyframes scanline {
    from { opacity: 1; }
    to { opacity: 0; }
}

.tool-card.is-online {
    border-color: #16a34a;
}

/* --- 像素状态灯 (3x3 矩阵) --- */
.status-indicator {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 18px;
    height: 18px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1px;
}

.status-indicator .pixel {
    width: 5px;
    height: 5px;
    background: #d1d5db;
    border-radius: 0;
}

.status-indicator.online .pixel {
    background: #4ade80;
}

.status-indicator.online .pixel.center {
    background: #22c55e;
    box-shadow: 0 0 4px #22c55e;
}

.status-indicator.offline .pixel.center {
    background: #9ca3af;
}

/* --- 协议标签 --- */
.protocol-badge {
    position: absolute;
    top: 12px;
    left: 12px;
    font-size: 10px;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-weight: 700;
    color: #6b7280;
    background: #f3f4f6;
    padding: 2px 6px;
    border: 1px solid #d1d5db;
    border-radius: 0;
    letter-spacing: 0.5px;
}

/* --- 卡片内容 --- */
.card-content {
    margin-top: 28px;
}

.card-title {
    font-size: 14px;
    font-weight: 700;
    color: #1a1a1a;
    margin: 0 0 8px;
    font-family: 'JetBrains Mono', monospace;
    word-break: break-all;
}

.card-desc {
    font-size: 12px;
    color: #6b7280;
    margin: 0 0 12px;
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

/* --- 像素标签 --- */
.card-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 12px;
}

.pixel-tag {
    font-size: 10px;
    font-family: 'JetBrains Mono', monospace;
    color: #374151;
    background: #e5e7eb;
    padding: 2px 6px;
    border: 1px solid #d1d5db;
    border-radius: 0;
}

.pixel-tag.more {
    background: #f9fafb;
    color: #9ca3af;
}

/* --- 版本号 --- */
.card-version {
    font-size: 10px;
    font-family: 'JetBrains Mono', monospace;
    color: #9ca3af;
    letter-spacing: 1px;
}

/* --- 卡片操作区 --- */
.card-actions {
    position: absolute;
    bottom: 12px;
    right: 12px;
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.15s;
}

.tool-card:hover .card-actions {
    opacity: 1;
}

/* --- 空状态 --- */
.empty-state {
    grid-column: 1 / -1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px;
    color: #9ca3af;
}

.empty-state p {
    margin-top: 16px;
    font-size: 14px;
}

/* --- 分页 --- */
.pagination-bar {
    display: flex;
    justify-content: center;
    padding: 12px 0;
}

/* --- 表单样式 --- */
.tool-form {
    max-height: 60vh;
    overflow-y: auto;
    padding-right: 12px;
}

.form-section {
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px dashed #e5e7eb;
}

.form-section:last-child {
    border-bottom: none;
}

.section-title {
    font-size: 13px;
    font-weight: 700;
    color: #374151;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.mono-input :deep(.el-input__inner) {
    font-family: 'JetBrains Mono', monospace;
}

.tag-input-group {
    display: flex;
    gap: 4px;
    margin-bottom: 8px;
}

.tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}

.param-table {
    border-radius: 0 !important;
}

.param-table :deep(.el-table__header th) {
    background: #f3f4f6 !important;
    font-weight: 600;
    font-size: 12px;
}

/* --- Schema 预览 --- */
.schema-preview {
    background: #1a1a1a;
    color: #4ade80;
    padding: 12px;
    border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    line-height: 1.6;
    overflow-x: auto;
    max-height: 200px;
}

/* --- 详情抽屉 --- */
.detail-drawer :deep(.el-drawer__body) {
    padding: 0;
    display: flex;
    flex-direction: column;
}

.preview-header-box {
    padding: 24px;
    background: #fafafa;
    border-bottom: 1px solid #e5e7eb;
}

.preview-title-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}

.preview-name {
    font-size: 20px;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
    color: #1a1a1a;
}

.preview-version {
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
    color: #9ca3af;
}

.mono-tag {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    border-radius: 2px;
}

.preview-desc-row {
    font-size: 14px;
    color: #4b5563;
    line-height: 1.6;
    margin-bottom: 12px;
}

.preview-tags-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.tag-item {
    border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
    color: #4b5563;
}

.preview-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
}

.info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
}

.info-item .label {
    font-size: 11px;
    font-weight: 600;
    color: #9ca3af;
    text-transform: uppercase;
    margin-bottom: 4px;
}

.info-item .value {
    font-size: 13px;
    color: #1a1a1a;
    font-weight: 500;
}

.info-item .value.mono {
    font-family: 'JetBrains Mono', monospace;
    background: #f3f4f6;
    padding: 2px 6px;
    border-radius: 2px;
    display: inline-block;
}

.info-item.full {
    grid-column: 1 / -1;
}

.divider {
    height: 1px;
    background: repeating-linear-gradient(to right, #e5e7eb 0, #e5e7eb 4px, transparent 4px, transparent 8px);
    margin: 0 0 24px;
}

.section-block {
    margin-bottom: 32px;
}

.block-title {
    font-size: 13px;
    font-weight: 700;
    color: #374151;
    margin-bottom: 12px;
    font-family: 'Inter', sans-serif;
}

.preview-table {
    width: 100%;
    margin-bottom: 8px;
}

.preview-table :deep(th) {
    background-color: #f9fafb !important;
    font-size: 12px;
    color: #6b7280;
    font-weight: 600;
}

.empty-text {
    font-size: 12px;
    color: #9ca3af;
    font-style: italic;
    background: #f9fafb;
    padding: 12px;
    text-align: center;
    border-radius: 2px;
}

.code-block {
    background: #1a1a1a;
    color: #e5e7eb;
    padding: 16px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    line-height: 1.5;
    margin: 0;
    overflow-x: auto;
    white-space: pre-wrap;
}

.schema-tabs {
    margin-top: 8px;
}

.schema-tabs :deep(.el-tabs__content) {
    padding: 0;
    background: #1a1a1a;
}


/* --- 弹窗样式覆盖 --- */
.tool-dialog :deep(.el-dialog) {
    border-radius: 2px !important;
}

.tool-dialog :deep(.el-dialog__header) {
    border-bottom: 1px solid #e5e7eb;
    padding: 16px 20px;
}

.tool-dialog :deep(.el-dialog__title) {
    font-weight: 700;
}

/* --- Few-Shot 折叠面板 --- */
.fewshot-collapse {
    margin-bottom: 20px;
    border: 1px dashed #e5e7eb;
    border-radius: 2px;
}

.fewshot-collapse :deep(.el-collapse-item__header) {
    background: #fafafa;
    padding: 0 16px;
    height: 40px;
    border-bottom: none;
}

.collapse-title {
    font-size: 13px;
    font-weight: 600;
    color: #6b7280;
}

.fewshot-section {
    padding: 16px;
}

.fewshot-label {
    font-size: 12px;
    font-weight: 600;
    color: #374151;
    margin-bottom: 8px;
}

.fewshot-hint {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 4px;
}

.mono-textarea :deep(.el-textarea__inner) {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    border-radius: 2px;
}

.w-full {
    width: 100%;
}
</style>
