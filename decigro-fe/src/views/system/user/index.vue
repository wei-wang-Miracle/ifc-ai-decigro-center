<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../../utils/request'
import { Plus, Edit, Delete, User, Refresh, Lock, Unlock, Memo, Avatar } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

// --- 数据定义 ---
const tableData = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const dialogTitle = ref('')
const roleOptions = ref<any[]>([])
const deptOptions = ref<any[]>([])

const form = reactive<any>({
    id: null,
    username: '',
    password: '',
    nickName: '',
    gender: 1,
    email: '',
    phone: '',
    deptId: null,
    roleId: null,
    isEnabled: true
})

const ruleFormRef = ref<FormInstance>()

const rules = reactive<FormRules>({
    username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
    password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
    nickName: [{ required: true, message: '请输入显示昵称', trigger: 'blur' }],
    roleId: [{ required: true, message: '请选择角色', trigger: 'change' }],
    deptId: [{ required: true, message: '请选择部门', trigger: 'change' }]
})

// --- 接口调用 ---
const fetchData = async () => {
    loading.value = true
    try {
        const res: any = await request.get('/sys/user')
        tableData.value = res
    } catch (e) {
        console.error(e)
    } finally {
        loading.value = false
    }
}

const fetchOptions = async () => {
    try {
        const roles: any = await request.get('/sys/role')
        roleOptions.value = roles
        const depts: any = await request.get('/sys/dept')
        deptOptions.value = depts
    } catch (e) {
        console.error(e)
    }
}

// --- 交互逻辑 ---
const handleAdd = () => {
    dialogTitle.value = '新增用户项目'
    resetForm()
    dialogVisible.value = true
}

const handleEdit = (row: any) => {
    dialogTitle.value = '修改用户信息'
    Object.assign(form, row)
    // 隐藏密码，修改时不强制输入
    form.password = '' 
    dialogVisible.value = true
}

const handleDelete = (row: any) => {
    ElMessageBox.confirm(
        `确定要删除用户 "${row.username}" 吗？`,
        '警告',
        {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning',
            confirmButtonClass: 'el-button--danger'
        }
    ).then(async () => {
        await request.delete(`/sys/user/${row.id}`)
        ElMessage.success('删除成功')
        fetchData()
    })
}

const handleToggleStatus = async (row: any) => {
    const statusText = row.isEnabled ? '禁用' : '启用'
    try {
        await request.post('/sys/user', {
            ...row,
            isEnabled: !row.isEnabled
        })
        ElMessage.success(`用户已${statusText}`)
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
                // 如果是修改且密码为空，保持原密码
                const data = { ...form }
                if (data.id && !data.password) {
                    data.password = undefined
                }
                await request.post('/sys/user', data)
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
        id: null,
        username: '',
        password: '',
        nickName: '',
        gender: 1,
        email: '',
        phone: '',
        deptId: null,
        roleId: null,
        isEnabled: true
    })
    ruleFormRef.value?.resetFields()
}

onMounted(() => {
    fetchData()
    fetchOptions()
})
</script>

<template>
  <div class="space-y-4">
    <!-- 顶部操作工具栏 -->
    <div class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex justify-between items-center bg-gradient-to-r from-white to-slate-50">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 bg-brand-50 rounded-xl flex items-center justify-center text-brand-600">
                <el-icon :size="20"><User /></el-icon>
            </div>
            <div>
                <h3 class="text-lg font-bold text-gray-800">用户管理</h3>
                <p class="text-xs text-gray-400">管理系统登录账号及其基本资料</p>
            </div>
        </div>
        <div class="flex space-x-2">
            <el-button :icon="Refresh" circle @click="fetchData" />
            <el-button type="primary" :icon="Plus" round size="large" @click="handleAdd" class="shadow-md shadow-brand-100">新增用户项目</el-button>
        </div>
    </div>

    <!-- 数据表格区域 -->
    <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
        <el-table v-loading="loading" :data="tableData" style="width: 100%" class="custom-table">
          <el-table-column prop="id" label="序号" width="80" />
          <el-table-column prop="username" label="登录账号" width="150">
              <template #default="scope">
                  <div class="font-medium text-gray-700">{{ scope.row.username }}</div>
              </template>
          </el-table-column>
          <el-table-column prop="nickName" label="显示昵称" width="150" />
          <el-table-column prop="email" label="电子邮箱" min-width="180" show-overflow-tooltip />
          <el-table-column label="组织/角色" width="200">
              <template #default="scope">
                  <div class="text-xs space-y-1">
                      <div class="flex items-center text-gray-500">
                          <el-icon class="mr-1"><Memo /></el-icon>
                          {{ scope.row.deptId }} (部门ID)
                      </div>
                      <div class="flex items-center text-brand-600">
                          <el-icon class="mr-1"><Avatar /></el-icon>
                          {{ scope.row.roleId }} (角色ID)
                      </div>
                  </div>
              </template>
          </el-table-column>
          <el-table-column prop="isEnabled" label="账号状态" width="120">
              <template #default="scope">
                  <el-tag :type="scope.row.isEnabled ? 'success' : 'danger'" effect="light" round class="border-none">
                      {{ scope.row.isEnabled ? '正常启用' : '已锁定' }}
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

    <!-- 新增/修改对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="550px">
        <el-form ref="ruleFormRef" :model="form" :rules="rules" label-width="100px" class="mt-4">
            <el-form-item label="登录账号" prop="username">
                <el-input v-model="form.username" placeholder="请输入用户名" :disabled="!!form.id" />
            </el-form-item>
            <el-form-item label="登录密码" prop="password" v-if="!form.id">
                <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
            </el-form-item>
            <el-form-item label="显示昵称" prop="nickName">
                <el-input v-model="form.nickName" placeholder="请输入昵称" />
            </el-form-item>
            <el-row :gutter="20">
                <el-col :span="12">
                    <el-form-item label="手机号码" prop="phone">
                        <el-input v-model="form.phone" placeholder="手机号" />
                    </el-form-item>
                </el-col>
                <el-col :span="12">
                    <el-form-item label="性别" prop="gender">
                        <el-select v-model="form.gender" placeholder="请选择">
                            <el-option label="男" :value="1" />
                            <el-option label="女" :value="2" />
                            <el-option label="未知" :value="0" />
                        </el-select>
                    </el-form-item>
                </el-col>
            </el-row>
            <el-form-item label="电子邮箱" prop="email">
                <el-input v-model="form.email" placeholder="example@domain.com" />
            </el-form-item>
            <el-form-item label="所属部门" prop="deptId">
                <el-select v-model="form.deptId" placeholder="选择部门" class="w-full">
                    <el-option v-for="item in deptOptions" :key="item.deptId" :label="item.deptName" :value="item.deptId" />
                </el-select>
            </el-form-item>
            <el-form-item label="分配角色" prop="roleId">
                <el-select v-model="form.roleId" placeholder="选择角色" class="w-full">
                    <el-option v-for="item in roleOptions" :key="item.roleId" :label="item.roleName" :value="item.roleId" />
                </el-select>
            </el-form-item>
            <el-form-item label="账号状态">
                <el-switch v-model="form.isEnabled" active-text="启用" inactive-text="禁用" />
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
