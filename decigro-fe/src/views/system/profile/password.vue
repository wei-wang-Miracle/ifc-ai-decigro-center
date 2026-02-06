<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../../../utils/request'
import { useUserStore } from '../../../stores/user'
import { Lock, Key } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

const form = ref({
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
})

const handleSubmit = async () => {
    if (form.value.newPassword !== form.value.confirmPassword) {
        ElMessage.error('两次输入的密码不一致')
        return
    }

    loading.value = true
    try {
        await request.put('/sys/user/password', {
            oldPassword: form.value.oldPassword,
            newPassword: form.value.newPassword
        })
        ElMessage.success('密码修改成功，请重新登录')
        userStore.logout()
        router.push('/login')
    } catch (error: any) {
        ElMessage.error(error.message || '修改失败')
    } finally {
        loading.value = false
    }
}
</script>

<template>
  <div class="password-container max-w-4xl mx-auto">
    <div class="mb-6">
        <h2 class="text-2xl font-bold text-gray-900">修改登录密码</h2>
        <p class="text-gray-500 mt-1 text-sm">为了您的账户安全，建议定期更换高强度密码</p>
    </div>

    <div class="bg-white rounded-xl shadow-bento p-8 border border-gray-100 hover:shadow-bento-hover transition-all duration-300">
        <el-form 
            :model="form" 
            label-width="100px" 
            v-loading="loading"
            class="max-w-lg"
        >
            <el-form-item label="原密码">
                <el-input v-model="form.oldPassword" type="password" show-password placeholder="请输入当前使用的密码">
                    <template #prefix><el-icon><Key /></el-icon></template>
                </el-input>
            </el-form-item>
            
            <el-form-item label="新密码">
                <el-input v-model="form.newPassword" type="password" show-password placeholder="新密码建议包含字母和数字">
                    <template #prefix><el-icon><Lock /></el-icon></template>
                </el-input>
            </el-form-item>

            <el-form-item label="确认新密码">
                <el-input v-model="form.confirmPassword" type="password" show-password placeholder="请再次输入新密码">
                    <template #prefix><el-icon><Lock /></el-icon></template>
                </el-input>
            </el-form-item>

            <el-form-item class="mt-8">
                <el-button 
                    type="primary" 
                    @click="handleSubmit" 
                    class="px-8 bg-brand-500 border-none hover:bg-brand-600 shadow-md"
                >
                    确认重置密码
                </el-button>
            </el-form-item>
        </el-form>
    </div>
  </div>
</template>

<style scoped>
:deep(.el-input__wrapper) {
    box-shadow: 0 0 0 1px #e5e7eb inset;
    border-radius: 8px;
    padding: 2px 12px;
}

:deep(.el-input__wrapper.is-focus) {
    box-shadow: 0 0 0 1px #4285f4 inset !important;
}
</style>
