<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../../utils/request'
import { Plus, Edit, Delete, List, Refresh, FolderOpened } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// --- 数据定义 ---
const tableData = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('')
const deptTreeOptions = ref<any[]>([]) // 用于选择父部门

const form = reactive<any>({
    deptId: null,
    parentId: 0,
    deptName: ''
})

const ruleFormRef = ref<FormInstance>()
const rules = reactive<FormRules>({
    deptName: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
    parentId: [{ required: true, message: '请选择上级部门', trigger: 'change' }]
})

// --- 接口调用 ---
const fetchData = async () => {
    loading.value = true
    try {
        // 使用树状接口获取数据
        const res: any = await request.get('/dept/tree')
        tableData.value = res
        
        // 构建扁平化的部门列表用于下拉选择
        const flatRes: any = await request.get('/dept/list')
        deptTreeOptions.value = [{ deptId: 0, deptName: '无（顶级部门）' }, ...flatRes]
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

// --- 交互逻辑 ---
const handleAdd = (parent?: any) => {
    dialogTitle.value = '创建新部门'
    resetForm()
    if (parent) {
        form.parentId = parent.deptId
    }
    dialogVisible.value = true
}

const handleEdit = (row: any) => {
    dialogTitle.value = '编辑部门信息'
    Object.assign(form, row)
    dialogVisible.value = true
}

const handleDelete = (row: any) => {
    ElMessageBox.confirm(
        `确定要删除部门 "${row.deptName}" 吗？如果含有子部门将无法删除或会联级删除（需后端支持）。`,
        '警告',
        {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning',
            confirmButtonClass: 'el-button--danger'
        }
    ).then(async () => {
        await request.delete(`/dept/remove/${row.deptId}`)
        ElMessage.success('删除成功')
        fetchData()
    })
}

const submitForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            try {
                await request.post('/dept/save', form)
                ElMessage.success(`${dialogTitle.value}成功`)
                dialogVisible.value = false
                fetchData()
            } catch (e) {
                console.error(e)
            }
        }
    })
}

const resetForm = () => {
    Object.assign(form, {
        deptId: null,
        parentId: 0,
        deptName: ''
    })
    ruleFormRef.value?.resetFields()
}

onMounted(() => {
    fetchData()
})
</script>

<template>
  <div class="space-y-4">
    <!-- 顶部操作 -->
    <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex justify-between items-center bg-gradient-to-r from-white to-slate-50">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 bg-brand-50 rounded-xl flex items-center justify-center text-brand-600">
                <el-icon :size="20"><List /></el-icon>
            </div>
            <div>
                <h3 class="text-lg font-bold text-gray-800">部门管理</h3>
                <p class="text-xs text-gray-400">组织架构维护与层级管理</p>
            </div>
        </div>
        <div class="flex space-x-2">
            <el-button :icon="Refresh" circle @click="fetchData" />
            <el-button type="primary" :icon="Plus" round size="large" @click="handleAdd()" class="shadow-md shadow-brand-100">创建新部门</el-button>
        </div>
    </div>

    <!-- 表格区域 -->
    <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
        <el-table v-loading="loading" :data="tableData" style="width: 100%" row-key="deptId" default-expand-all class="custom-table" :tree-props="{ children: 'children', hasChildren: 'hasChildren' }">
          <el-table-column prop="deptName" label="部门/机构名称" min-width="280">
              <template #default="scope">
                  <div class="flex items-center">
                      <el-icon class="mr-2 text-brand-400"><FolderOpened /></el-icon>
                      <span class="font-medium text-gray-700">{{ scope.row.deptName }}</span>
                  </div>
              </template>
          </el-table-column>
          <el-table-column prop="deptId" label="组织编码" width="120" />
          <el-table-column label="管理操作" width="220" fixed="right">
            <template #default="scope">
                <el-button link type="primary" :icon="Plus" @click="handleAdd(scope.row)">添加子项</el-button>
                <el-button link type="primary" :icon="Edit" @click="handleEdit(scope.row)">编辑</el-button>
                <el-button link type="danger" :icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
    </div>

    <!-- 对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
        <el-form ref="ruleFormRef" :model="form" :rules="rules" label-width="100px" class="mt-4">
            <el-form-item label="上级部门" prop="parentId">
                <el-select v-model="form.parentId" placeholder="请选择上级部门" class="w-full">
                    <el-option v-for="item in deptTreeOptions" :key="item.deptId" :label="item.deptName" :value="item.deptId" />
                </el-select>
            </el-form-item>
            <el-form-item label="部门名称" prop="deptName">
                <el-input v-model="form.deptName" placeholder="如：研发中心" />
            </el-form-item>

        </el-form>
        <template #footer>
            <span class="dialog-footer">
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" @click="submitForm(ruleFormRef)">确认保存</el-button>
            </span>
        </template>
    </el-dialog>
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
