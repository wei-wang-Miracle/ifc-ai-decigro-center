<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../../utils/request'
import { Plus, Edit, Delete, Stamp, Refresh, Lock, Unlock } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// --- 数据定义 ---
const tableData = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('')

const toolOptions = [
    { label: '搜索工具', value: 'search' },
    { label: '代码解释器', value: 'interpreter' },
    { label: '智能分析', value: 'analysis' },
    { label: '文档生成', value: 'doc_gen' },
    { label: '外部插件', value: 'plugin' }
]

const form = reactive<any>({
    roleId: null,
    roleName: '',
    roleDesc: '',
    toolList: [],
    isEnabled: true
})

const ruleFormRef = ref<FormInstance>()
const rules = reactive<FormRules>({
    roleName: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
    roleDesc: [{ required: true, message: '请输入角色描述', trigger: 'blur' }]
})

// --- 接口调用 ---
const fetchData = async () => {
    loading.value = true
    try {
        const res: any = await request.get('/role/list')
        tableData.value = res
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

// --- 交互逻辑 ---
const handleAdd = () => {
    dialogTitle.value = '新增系统角色'
    resetForm()
    dialogVisible.value = true
}

const handleEdit = (row: any) => {
    dialogTitle.value = '修改系统角色'
    Object.assign(form, row)
    // 确保 toolList 是数组
    if (!form.toolList) form.toolList = []
    dialogVisible.value = true
}

const handleDelete = (row: any) => {
    ElMessageBox.confirm(
        `确定要删除角色 "${row.roleName}" 吗？`,
        '警告',
        {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning',
            confirmButtonClass: 'el-button--danger'
        }
    ).then(async () => {
        await request.delete(`/role/remove/${row.roleId}`)
        ElMessage.success('删除成功')
        fetchData()
    })
}

const handleToggleStatus = async (row: any) => {
    const statusText = row.isEnabled ? '禁用' : '启用'
    try {
        await request.post('/role/save', {
            ...row,
            isEnabled: !row.isEnabled
        })
        ElMessage.success(`角色已${statusText}`)
        fetchData()
    } catch (e) {
        console.error(e)
    }
}

const submitForm = async (formEl: FormInstance | undefined) => {
    if (!formEl) return
    await formEl.validate(async (valid) => {
        if (valid) {
            try {
                await request.post('/role/save', form)
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
        roleId: null,
        roleName: '',
        roleDesc: '',
        toolList: [],
        isEnabled: true
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
                <el-icon :size="20"><Stamp /></el-icon>
            </div>
            <div>
                <h3 class="text-lg font-bold text-gray-800">角色管理</h3>
                <p class="text-xs text-gray-400">定义系统操作权限组及其关联工具集</p>
            </div>
        </div>
        <div class="flex space-x-2">
            <el-button :icon="Refresh" circle @click="fetchData" />
            <el-button type="primary" :icon="Plus" round size="large" @click="handleAdd" class="shadow-md shadow-brand-100">新增系统角色</el-button>
        </div>
    </div>

    <!-- 表格区域 -->
    <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
        <el-table v-loading="loading" :data="tableData" style="width: 100%" class="custom-table">
          <el-table-column prop="roleId" label="角色ID" width="100" />
          <el-table-column prop="roleName" label="角色名称" width="180">
              <template #default="scope">
                  <div class="font-medium text-gray-700">{{ scope.row.roleName }}</div>
              </template>
          </el-table-column>
          <el-table-column prop="roleDesc" label="权限描述信息" min-width="250" show-overflow-tooltip />
          <el-table-column label="分配工具" min-width="200">
              <template #default="scope">
                  <div class="flex flex-wrap gap-1">
                      <el-tag v-for="tool in scope.row.toolList" :key="tool" size="small" effect="plain" round>
                          {{ toolOptions.find(o => o.value === tool)?.label || tool }}
                      </el-tag>
                      <span v-if="!scope.row.toolList?.length" class="text-gray-400 text-xs">未分配</span>
                  </div>
              </template>
          </el-table-column>
          <el-table-column prop="isEnabled" label="状态" width="100">
              <template #default="scope">
                  <el-tag :type="scope.row.isEnabled ? 'success' : 'danger'" effect="light" round class="border-none">
                      {{ scope.row.isEnabled ? '正常' : '禁用' }}
                  </el-tag>
              </template>
          </el-table-column>
          <el-table-column label="管理操作" width="220" fixed="right">
            <template #default="scope">
                <el-button link type="primary" :icon="Edit" @click="handleEdit(scope.row)">修改</el-button>
                <el-button link :type="scope.row.isEnabled ? 'warning' : 'success'" :icon="scope.row.isEnabled ? Lock : Unlock" @click="handleToggleStatus(scope.row)">
                    {{ scope.row.isEnabled ? '置为无效' : '启用' }}
                </el-button>
                <el-button link type="danger" :icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
    </div>

    <!-- 对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
        <el-form ref="ruleFormRef" :model="form" :rules="rules" label-width="100px" class="mt-4">
            <el-form-item label="角色名称" prop="roleName">
                <el-input v-model="form.roleName" placeholder="如：系统管理员" />
            </el-form-item>
            <el-form-item label="角色描述" prop="roleDesc">
                <el-input v-model="form.roleDesc" type="textarea" placeholder="描述角色的职权访问范围" />
            </el-form-item>
            <el-form-item label="分配工具" prop="toolList">
                <el-select v-model="form.toolList" multiple placeholder="请选择可选工具" class="w-full">
                    <el-option v-for="item in toolOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
            </el-form-item>
            <el-form-item label="是否启用">
                <el-switch v-model="form.isEnabled" />
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
