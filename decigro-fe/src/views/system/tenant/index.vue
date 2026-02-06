<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../../utils/request'
import { Plus, Edit, Delete, OfficeBuilding, Refresh, Lock, Unlock } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// --- 数据定义 ---
const tableData = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('')

const form = reactive<any>({
    tenantCode: '',
    tenantName: '',
    isEnabled: true
})

const ruleFormRef = ref<FormInstance>()
const rules = reactive<FormRules>({
    tenantCode: [{ required: true, message: '请输入租户编码', trigger: 'blur' }],
    tenantName: [{ required: true, message: '请输入租户名称', trigger: 'blur' }]
})

// --- 接口调用 ---
const fetchData = async () => {
    loading.value = true
    try {
        const res: any = await request.get('/sys/tenant')
        tableData.value = res
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

// --- 交互逻辑 ---
const handleAdd = () => {
    dialogTitle.value = '入驻新租户'
    resetForm()
    dialogVisible.value = true
}

const handleEdit = (row: any) => {
    dialogTitle.value = '修改租户信息'
    Object.assign(form, row)
    dialogVisible.value = true
}

const handleDelete = (row: any) => {
    ElMessageBox.confirm(
        `确定要清退租户 "${row.tenantName}" (${row.tenantCode}) 吗？此操作将立即生效并可能影响该租户下的所有用户。`,
        '警告',
        {
            confirmButtonText: '确定清退',
            cancelButtonText: '取消',
            type: 'warning',
            confirmButtonClass: 'el-button--danger'
        }
    ).then(async () => {
        await request.delete(`/sys/tenant/${row.tenantCode}`)
        ElMessage.success('清退成功')
        fetchData()
    })
}

const handleToggleStatus = async (row: any) => {
    const statusText = row.isEnabled ? '禁用' : '启用'
    try {
        await request.post('/sys/tenant', {
            ...row,
            isEnabled: !row.isEnabled
        })
        ElMessage.success(`租户已${statusText}`)
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
                await request.post('/sys/tenant', form)
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
        tenantCode: '',
        tenantName: '',
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
                <el-icon :size="20"><OfficeBuilding /></el-icon>
            </div>
            <div>
                <h3 class="text-lg font-bold text-gray-800">租户管理</h3>
                <p class="text-xs text-gray-400">跨机构多租户资源隔离与配置中心</p>
            </div>
        </div>
        <div class="flex space-x-2">
            <el-button :icon="Refresh" circle @click="fetchData" />
            <el-button type="primary" :icon="Plus" round size="large" @click="handleAdd" class="shadow-md shadow-brand-100">入驻新租户</el-button>
        </div>
    </div>

    <!-- 表格区域 -->
    <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
        <el-table v-loading="loading" :data="tableData" style="width: 100%" class="custom-table">
          <el-table-column prop="tenantCode" label="租户识别码" width="180" />
          <el-table-column prop="tenantName" label="企业/租户名称" min-width="280">
              <template #default="scope">
                  <span class="font-medium text-gray-700">{{ scope.row.tenantName }}</span>
              </template>
          </el-table-column>
          <el-table-column prop="isEnabled" label="账号状态" width="120">
               <template #default="scope">
                  <el-tag :type="scope.row.isEnabled ? 'success' : 'danger'" effect="light" round class="border-none">
                      {{ scope.row.isEnabled ? '服务中' : '已停服' }}
                  </el-tag>
              </template>
          </el-table-column>
          <el-table-column label="管理操作" width="220" fixed="right">
            <template #default="scope">
                <el-button link type="primary" :icon="Edit" @click="handleEdit(scope.row)">详情</el-button>
                <el-button link :type="scope.row.isEnabled ? 'warning' : 'success'" :icon="scope.row.isEnabled ? Lock : Unlock" @click="handleToggleStatus(scope.row)">
                    {{ scope.row.isEnabled ? '置为无效' : '启用' }}
                </el-button>
                <el-button link type="danger" :icon="Delete" @click="handleDelete(scope.row)">清退</el-button>
            </template>
          </el-table-column>
        </el-table>
    </div>

    <!-- 对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
        <el-form ref="ruleFormRef" :model="form" :rules="rules" label-width="100px" class="mt-4">
            <el-form-item label="租户编码" prop="tenantCode">
                <el-input v-model="form.tenantCode" placeholder="如：ALIBABA" :disabled="dialogTitle.includes('修改')" />
            </el-form-item>
            <el-form-item label="租户名称" prop="tenantName">
                <el-input v-model="form.tenantName" placeholder="如：阿里巴巴网络技术有限公司" />
            </el-form-item>
            <el-form-item label="状态">
                <el-switch v-model="form.isEnabled" active-text="服务中" inactive-text="已停服" />
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
