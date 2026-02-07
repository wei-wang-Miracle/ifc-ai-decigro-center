<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import request from '../../utils/request'
import { 
    Plus, Edit, Delete, Search, Refresh, Setting, 
    FolderOpened, Collection, PriceTag, Switch 
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// ============================================
// 第一部分：数据定义
// ============================================

// --- 分类树相关 ---
const categoryTree = ref<any[]>([])  // 左侧分类树数据
const categoryLoading = ref(false)
const selectedCategory = ref<number | null>(null)  // 当前选中的分类ID
const categoryDialogVisible = ref(false)
const categoryDialogTitle = ref('')
const categoryForm = reactive<any>({
    id: null,
    name: '',
    parentId: 0,
    sortIndex: 1
})
const categoryFormRef = ref<FormInstance>()
const categoryRules = reactive<FormRules>({
    name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }]
})

// --- 迁移相关 ---
const migrateDialogVisible = ref(false)
const migrateForm = reactive({
    sourceId: null as number | null,
    sourceName: '',
    targetId: null as number | null
})
const migrateFormRef = ref<FormInstance>()
const migrateRules = reactive<FormRules>({
    targetId: [{ required: true, message: '请选择目标分类', trigger: 'change' }]
})

// --- 标签列表相关 ---
const tagTableData = ref<any[]>([])  // 右侧标签表格数据
const tagLoading = ref(false)
const tagTotal = ref(0)
const tagPageNum = ref(1)
const tagPageSize = ref(10)
const searchKeyword = ref('')

const tagDialogVisible = ref(false)
const tagDialogTitle = ref('')
const tagForm = reactive<any>({
    tagField: '',
    tagTable: '',
    tagName: '',
    tagDesc: '',
    valueType: 'string',
    categoryId: null,
    remark: '',
    sortIndex: 0
})
const tagFormRef = ref<FormInstance>()
const tagRules = reactive<FormRules>({
    tagField: [{ required: true, message: '请输入标签字段名', trigger: 'blur' }],
    tagName: [{ required: true, message: '请输入标签名称', trigger: 'blur' }],
    tagTable: [{ required: true, message: '请输入来源表名', trigger: 'blur' }],
    categoryId: [{ required: true, message: '请选择所属分类', trigger: 'change' }],
    valueType: [{ required: true, message: '请选择值类型', trigger: 'change' }]
})
const isEditTag = ref(false)  // 编辑模式下tagField不可修改

// --- 枚举值配置相关 ---
const enumDrawerVisible = ref(false)
const enumCurrentTagField = ref('')
const enumCurrentTagName = ref('')
const enumList = ref<any[]>([])

// --- 值类型选项 ---
const valueTypeOptions = [
    { label: '字符串', value: 'string' },
    { label: '数值', value: 'number' },
    { label: '枚举', value: 'enum' },
    { label: '日期', value: 'date' },
    { label: '数组', value: 'array' }
]

// --- 所有分类的扁平列表（用于下拉选择）---
const flatCategoryList = ref<any[]>([])

// ============================================
// 第二部分：计算属性
// ============================================

const selectedCategoryName = computed(() => {
    if (!selectedCategory.value) return '全部标签'
    const find = flatCategoryList.value.find(c => c.id === selectedCategory.value)
    return find ? find.name : '全部标签'
})

// ============================================
// 第三部分：接口调用
// ============================================

// --- 获取分类树 ---
const fetchCategoryTree = async () => {
    categoryLoading.value = true
    try {
        const res: any = await request.get('/tag-categories/tree')
        categoryTree.value = res

        // 同时获取扁平列表用于下拉选择
        const flatRes: any = await request.get('/tag-categories')
        flatCategoryList.value = flatRes
    } catch (e) {
        console.error('获取分类树失败', e)
    } finally {
        categoryLoading.value = false
    }
}

// --- 获取标签列表 ---
const fetchTagList = async () => {
    tagLoading.value = true
    try {
        const params: any = {
            page: tagPageNum.value,
            size: tagPageSize.value
        }
        if (selectedCategory.value) {
            params.categoryId = selectedCategory.value
        }
        if (searchKeyword.value) {
            params.keyword = searchKeyword.value
        }
        const res: any = await request.get('/tags', { params })
        tagTableData.value = res.records || []
        tagTotal.value = res.totalRow || 0
    } catch (e) {
        console.error('获取标签列表失败', e)
    } finally {
        tagLoading.value = false
    }
}

// --- 获取枚举值列表 ---
const fetchEnumList = async (tagField: string) => {
    try {
        const res: any = await request.get(`/tag-enums/${tagField}`)
        enumList.value = res || []
    } catch (e) {
        console.error('获取枚举值失败', e)
    }
}

// ============================================
// 第四部分：交互方法 - 分类管理
// ============================================

// --- 点击分类节点 ---
const handleCategoryClick = (data: any) => {
    selectedCategory.value = data.id
    tagPageNum.value = 1
    fetchTagList()
}

// --- 显示全部 ---
const handleShowAll = () => {
    selectedCategory.value = null
    tagPageNum.value = 1
    fetchTagList()
}

// --- 新增分类 ---
const handleAddCategory = (parentId: number = 0) => {
    categoryDialogTitle.value = '新增分类'
    resetCategoryForm()
    categoryForm.parentId = parentId
    categoryDialogVisible.value = true
}

// --- 编辑分类 ---
const handleEditCategory = (data: any) => {
    categoryDialogTitle.value = '编辑分类'
    Object.assign(categoryForm, {
        id: data.id,
        name: data.name,
        parentId: data.parentId,
        sortIndex: data.sortIndex || 1
    })
    categoryDialogVisible.value = true
}

// --- 删除分类 ---
const handleDeleteCategory = (data: any) => {
    ElMessageBox.confirm(
        `确定要删除分类 "${data.name}" 吗？`,
        '警告',
        {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
        }
    ).then(async () => {
        try {
            const res: any = await request.delete(`/tag-categories/${data.id}`)
            if (res === null || res === undefined) {
                ElMessage.success('删除成功')
                fetchCategoryTree()
            }
        } catch (e: any) {
            ElMessage.error(e.message || '删除失败')
        }
    })
}

// --- 保存分类 ---
const submitCategoryForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            try {
                await request.post('/tag-categories', categoryForm)
                ElMessage.success(`${categoryDialogTitle.value}成功`)
                categoryDialogVisible.value = false
                fetchCategoryTree()
            } catch (e) {
                console.error('保存分类失败', e)
            }
        }
    })
}


// --- 迁移分类下的标签 ---
const handleMigrate = (data: any) => {
    migrateForm.sourceId = data.id
    migrateForm.sourceName = data.name
    migrateForm.targetId = null
    migrateDialogVisible.value = true
}

const submitMigrateForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            if (migrateForm.sourceId === migrateForm.targetId) {
                ElMessage.warning('目标分类不能与源分类相同')
                return
            }
            try {
                await request.post('/tags/migrate', null, {
                    params: {
                        sourceId: migrateForm.sourceId,
                        targetId: migrateForm.targetId
                    }
                })
                ElMessage.success('标签迁移成功')
                migrateDialogVisible.value = false
                fetchTagList() // 刷新当前列表
            } catch (e) {
                console.error('迁移标签失败', e)
            }
        }
    })
}

const resetCategoryForm = () => {
    Object.assign(categoryForm, {
        id: null,
        name: '',
        parentId: 0,
        sortIndex: 1
    })
    categoryFormRef.value?.resetFields()
}

// ============================================
// 第五部分：交互方法 - 标签管理
// ============================================

// --- 搜索 ---
const handleSearch = () => {
    tagPageNum.value = 1
    fetchTagList()
}

// --- 新增标签 ---
const handleAddTag = () => {
    tagDialogTitle.value = '新增标签'
    isEditTag.value = false
    resetTagForm()
    // 默认选中当前分类
    if (selectedCategory.value) {
        tagForm.categoryId = selectedCategory.value
    }
    tagDialogVisible.value = true
}

// --- 编辑标签 ---
const handleEditTag = (row: any) => {
    tagDialogTitle.value = '编辑标签'
    isEditTag.value = true
    Object.assign(tagForm, row)
    tagDialogVisible.value = true
}

// --- 删除标签 ---
const handleDeleteTag = (row: any) => {
    ElMessageBox.confirm(
        `确定要删除标签 "${row.tagName}" 吗？关联的枚举值也会被删除。`,
        '警告',
        {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
        }
    ).then(async () => {
        try {
            await request.delete(`/tags/${row.tagField}`)
            ElMessage.success('删除成功')
            fetchTagList()
        } catch (e) {
            console.error('删除标签失败', e)
        }
    })
}

// --- 保存标签 ---
const submitTagForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            try {
                await request.post('/tags', tagForm)
                ElMessage.success(`${tagDialogTitle.value}成功`)
                tagDialogVisible.value = false
                fetchTagList()
            } catch (e) {
                console.error('保存标签失败', e)
            }
        }
    })
}

const resetTagForm = () => {
    Object.assign(tagForm, {
        tagField: '',
        tagTable: '',
        tagName: '',
        tagDesc: '',
        valueType: 'string',
        categoryId: null,
        remark: '',
        sortIndex: 0
    })
    tagFormRef.value?.resetFields()
}

// --- 分页 ---
const handlePageChange = (page: number) => {
    tagPageNum.value = page
    fetchTagList()
}

// ============================================
// 第六部分：交互方法 - 枚举值配置
// ============================================

const handleConfigEnum = async (row: any) => {
    enumCurrentTagField.value = row.tagField
    enumCurrentTagName.value = row.tagName
    await fetchEnumList(row.tagField)
    enumDrawerVisible.value = true
}

const handleAddEnumRow = () => {
    enumList.value.push({
        id: null,
        tagField: enumCurrentTagField.value,
        enumCode: '',
        enumName: ''
    })
}

const handleRemoveEnumRow = (index: number) => {
    enumList.value.splice(index, 1)
}

const handleSaveEnums = async () => {
    try {
        await request.post(`/tag-enums/batch/${enumCurrentTagField.value}`, enumList.value)
        ElMessage.success('枚举值保存成功')
        enumDrawerVisible.value = false
    } catch (e) {
        console.error('保存枚举值失败', e)
    }
}

// ============================================
// 第七部分：生命周期
// ============================================

onMounted(() => {
    fetchCategoryTree()
    fetchTagList()
})
</script>

<template>
  <div class="flex h-full gap-4 overflow-hidden">
    <!-- 左侧分类树 (20%) -->
    <div class="w-1/5 min-w-[240px] bg-white rounded-2xl shadow-sm border border-gray-100 flex flex-col">
        <!-- 树顶部 -->
        <div class="p-4 border-b border-gray-100 flex justify-between items-center">
            <div class="flex items-center space-x-2">
                <el-icon class="text-brand-500"><Collection /></el-icon>
                <span class="font-bold text-gray-700">标签分类</span>
            </div>
            <el-button :icon="Plus" size="small" circle @click="handleAddCategory(0)" />
        </div>
        
        <!-- 全部标签按钮 -->
        <div class="px-3 pt-3">
            <div 
                class="px-3 py-2 rounded-lg cursor-pointer flex items-center space-x-2 transition-colors"
                :class="selectedCategory === null ? 'bg-brand-50 text-brand-600' : 'hover:bg-gray-50 text-gray-600'"
                @click="handleShowAll">
                <el-icon><FolderOpened /></el-icon>
                <span>全部标签</span>
            </div>
        </div>

        <!-- 分类树 -->
        <div class="flex-1 overflow-auto p-3" v-loading="categoryLoading">
            <el-tree
                :data="categoryTree"
                node-key="id"
                :expand-on-click-node="false"
                @node-click="handleCategoryClick"
                :props="{ label: 'name', children: 'children' }">
                <template #default="{ node, data }">
                    <div class="flex-1 flex justify-between items-center group pr-2">
                        <span class="truncate">{{ node.label }}</span>
                        <div class="hidden group-hover:flex space-x-1">
                            <el-button :icon="Plus" size="small" link @click.stop="handleAddCategory(data.id)" />
                            <el-button :icon="Switch" size="small" link title="迁移标签" @click.stop="handleMigrate(data)" />
                            <el-button :icon="Edit" size="small" link @click.stop="handleEditCategory(data)" />
                            <el-button :icon="Delete" size="small" link type="danger" @click.stop="handleDeleteCategory(data)" />
                        </div>
                    </div>
                </template>
            </el-tree>
        </div>
    </div>

    <!-- 右侧标签列表 (80%) -->
    <div class="flex-1 min-w-0 flex flex-col space-y-4 overflow-hidden">
        <!-- 顶部操作栏 -->
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex flex-wrap gap-4 justify-between items-center bg-gradient-to-r from-white to-slate-50">
            <!-- 左侧：标题与新增 -->
            <div class="flex items-center space-x-3">
                <div class="w-9 h-9 bg-brand-50 rounded-lg flex items-center justify-center text-brand-600 flex-shrink-0">
                    <el-icon :size="18"><PriceTag /></el-icon>
                </div>
                <div class="min-w-0 mr-2">
                    <h3 class="text-base font-bold text-gray-800 truncate">{{ selectedCategoryName }}</h3>
                    <p class="text-[10px] text-gray-400">共 {{ tagTotal }} 个</p>
                </div>
                <el-button type="primary" :icon="Plus" @click="handleAddTag" class="flex-shrink-0">
                    新增
                </el-button>
            </div>
            
            <!-- 右侧：搜索于工具 -->
            <div class="flex items-center space-x-2 flex-shrink-0">
                <el-input
                    v-model="searchKeyword"
                    placeholder="关键字"
                    :prefix-icon="Search"
                    clearable
                    style="width: 120px"
                    @keyup.enter="handleSearch"
                    @clear="handleSearch" />
                <el-button :icon="Search" circle @click="handleSearch" />
                <el-button :icon="Refresh" circle @click="fetchTagList" />
            </div>
        </div>

        <!-- 表格区域 -->
        <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 flex-1 flex flex-col overflow-hidden">
            <el-table v-loading="tagLoading" :data="tagTableData" style="width: 100%" height="100%" class="custom-table flex-1">
                <el-table-column prop="tagField" label="字段名" width="150">
                    <template #default="scope">
                        <span class="font-mono text-sm text-gray-600">{{ scope.row.tagField }}</span>
                    </template>
                </el-table-column>
                <el-table-column prop="tagName" label="标签名称" width="160">
                    <template #default="scope">
                        <span class="font-medium text-gray-700">{{ scope.row.tagName }}</span>
                    </template>
                </el-table-column>
                <el-table-column prop="tagTable" label="来源表" width="120" />
                <el-table-column prop="valueType" label="值类型" width="100">
                    <template #default="scope">
                        <el-tag size="small" :type="scope.row.valueType === 'enum' ? 'warning' : 'info'" effect="light" round>
                            {{ valueTypeOptions.find(v => v.value === scope.row.valueType)?.label || scope.row.valueType }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="categoryName" label="所属分类" width="120" />
                <el-table-column prop="tagDesc" label="描述" min-width="180" show-overflow-tooltip />
                <el-table-column label="操作" width="200" fixed="right">
                    <template #default="scope">
                        <el-button link type="primary" :icon="Edit" @click="handleEditTag(scope.row)">编辑</el-button>
                        <el-button 
                            v-if="scope.row.valueType === 'enum'" 
                            link type="warning" :icon="Setting" 
                            @click="handleConfigEnum(scope.row)">枚举</el-button>
                        <el-button link type="danger" :icon="Delete" @click="handleDeleteTag(scope.row)">删除</el-button>
                    </template>
                </el-table-column>
            </el-table>

            <!-- 分页 -->
            <div class="mt-4 flex justify-end">
                <el-pagination
                    background
                    layout="prev, pager, next"
                    :total="tagTotal"
                    :page-size="tagPageSize"
                    :current-page="tagPageNum"
                    @current-change="handlePageChange" />
            </div>
        </div>
    </div>

    <!-- 分类弹窗 -->
    <el-dialog v-model="categoryDialogVisible" :title="categoryDialogTitle" width="420px">
        <el-form ref="categoryFormRef" :model="categoryForm" :rules="categoryRules" label-width="80px" class="mt-4">
            <el-form-item label="上级分类">
                <el-select v-model="categoryForm.parentId" placeholder="请选择" class="w-full">
                    <el-option :label="'( 顶级分类 )'" :value="0" />
                    <el-option v-for="item in flatCategoryList" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
            </el-form-item>
            <el-form-item label="分类名称" prop="name">
                <el-input v-model="categoryForm.name" placeholder="如：基础属性" />
            </el-form-item>
            <el-form-item label="排序序号">
                <el-input-number v-model="categoryForm.sortIndex" :min="1" />
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="categoryDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitCategoryForm(categoryFormRef)">确认</el-button>
        </template>
    </el-dialog>

    <!-- 标签弹窗 -->
    <el-dialog v-model="tagDialogVisible" :title="tagDialogTitle" width="560px">
        <el-form ref="tagFormRef" :model="tagForm" :rules="tagRules" label-width="90px" class="mt-4">
            <el-form-item label="标签字段" prop="tagField">
                <el-input 
                    v-model="tagForm.tagField" 
                    placeholder="如：customer_age" 
                    :disabled="isEditTag" />
                <div v-if="isEditTag" class="text-xs text-gray-400 mt-1">主键字段，创建后不可修改</div>
            </el-form-item>
            <el-form-item label="标签名称" prop="tagName">
                <el-input v-model="tagForm.tagName" placeholder="如：客户年龄" />
            </el-form-item>
            <el-form-item label="来源表名" prop="tagTable">
                <el-input v-model="tagForm.tagTable" placeholder="如：customer_info" />
            </el-form-item>
            <el-form-item label="所属分类" prop="categoryId">
                <el-select v-model="tagForm.categoryId" placeholder="请选择分类" class="w-full">
                    <el-option v-for="item in flatCategoryList" :key="item.id" :label="item.name" :value="item.id" />
                </el-select>
            </el-form-item>
            <el-form-item label="值类型" prop="valueType">
                <el-select v-model="tagForm.valueType" class="w-full">
                    <el-option v-for="opt in valueTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
                <div v-if="tagForm.valueType === 'enum'" class="text-xs text-orange-500 mt-1">
                    保存后请点击"枚举"按钮配置可选值
                </div>
            </el-form-item>
            <el-form-item label="描述">
                <el-input v-model="tagForm.tagDesc" type="textarea" :rows="3" placeholder="标签含义、计算逻辑等" />
            </el-form-item>
            <el-form-item label="排序序号">
                <el-input-number v-model="tagForm.sortIndex" :min="0" />
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="tagDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitTagForm(tagFormRef)">确认</el-button>
        </template>
    </el-dialog>

    <!-- 迁移标签弹窗 -->
    <el-dialog v-model="migrateDialogVisible" title="迁移标签" width="420px">
        <div class="mb-4 text-sm text-gray-500">
            将分类 <span class="font-bold text-brand-600">"{{ migrateForm.sourceName }}"</span> 下的所有标签迁移至：
        </div>
        <el-form ref="migrateFormRef" :model="migrateForm" :rules="migrateRules" label-width="80px">
            <el-form-item label="目标分类" prop="targetId">
                <el-select v-model="migrateForm.targetId" placeholder="请选择目标分类" class="w-full">
                    <el-option 
                        v-for="item in flatCategoryList" 
                        :key="item.id" 
                        :label="item.name" 
                        :value="item.id"
                        :disabled="item.id === migrateForm.sourceId" />
                </el-select>
            </el-form-item>
        </el-form>
        <template #footer>
            <el-button @click="migrateDialogVisible = false">取消</el-button>
            <el-button type="primary" @click="submitMigrateForm(migrateFormRef)">确定迁移</el-button>
        </template>
    </el-dialog>

    <!-- 枚举值配置抽屉 -->
    <el-drawer v-model="enumDrawerVisible" :title="`配置枚举值 - ${enumCurrentTagName}`" size="500px">
        <div class="space-y-4">
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-500">
                    字段: <code class="bg-gray-100 px-1 rounded">{{ enumCurrentTagField }}</code>
                </span>
                <el-button :icon="Plus" size="small" @click="handleAddEnumRow">添加枚举</el-button>
            </div>
            
            <el-table :data="enumList" border size="small">
                <el-table-column prop="enumCode" label="枚举代码" width="150">
                    <template #default="scope">
                        <el-input v-model="scope.row.enumCode" size="small" placeholder="存库值" />
                    </template>
                </el-table-column>
                <el-table-column prop="enumName" label="展示名称">
                    <template #default="scope">
                        <el-input v-model="scope.row.enumName" size="small" placeholder="显示名称" />
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="70">
                    <template #default="scope">
                        <el-button link type="danger" :icon="Delete" @click="handleRemoveEnumRow(scope.$index)" />
                    </template>
                </el-table-column>
            </el-table>
        </div>
        <template #footer>
            <el-button @click="enumDrawerVisible = false">取消</el-button>
            <el-button type="primary" @click="handleSaveEnums">保存枚举值</el-button>
        </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.custom-table :deep(.el-table__header) {
    color: #9ca3af;
    font-weight: 500;
}
.custom-table :deep(.el-table__cell) {
    padding: 12px 0;
}
</style>
