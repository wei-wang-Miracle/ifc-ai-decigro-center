<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../../../utils/request'
import { User, Message, Iphone, UserFilled } from '@element-plus/icons-vue'

const loading = ref(false)
const form = ref({
    username: '',
    nickName: '',
    gender: 1,
    email: '',
    phone: '',
    avatarPath: ''
})

const fetchProfile = async () => {
    loading.value = true
    try {
        const res = await request.get('/user/profile')
        form.value = res as any
    } catch (error) {
        console.error(error)
    } finally {
        loading.value = false
    }
}

const handleSubmit = async () => {
    loading.value = true
    try {
        await request.put('/user/profile', form.value)
        ElMessage.success('保存成功')
    } catch (error) {
        ElMessage.error('保存失败')
    } finally {
        loading.value = false
    }
}

onMounted(fetchProfile)
</script>

<template>
  <div class="profile-container max-w-4xl mx-auto">
    <div class="mb-6">
        <h2 class="text-2xl font-bold text-gray-900">个人信息详情</h2>
        <p class="text-gray-500 mt-1 text-sm">管理您的个人基本资料和联系方式</p>
    </div>

    <!-- 采用 Bento Grid 卡片风格 -->
    <div class="bg-white rounded-xl shadow-bento p-8 border border-gray-100 hover:shadow-bento-hover transition-all duration-300">
        <el-form 
            :model="form" 
            label-width="100px" 
            v-loading="loading"
            class="max-w-lg"
        >
            <el-form-item label="用户名">
                <el-input v-model="form.username" disabled class="font-mono">
                    <template #prefix><el-icon><User /></el-icon></template>
                </el-input>
                <p class="text-xs text-gray-400 mt-1">登录标识，不可修改</p>
            </el-form-item>
            
            <el-form-item label="昵称">
                <el-input v-model="form.nickName" placeholder="建议使用真实姓名">
                    <template #prefix><el-icon><UserFilled /></el-icon></template>
                </el-input>
            </el-form-item>

            <el-form-item label="性别">
                <el-radio-group v-model="form.gender">
                    <el-radio :label="1">男</el-radio>
                    <el-radio :label="0">女</el-radio>
                </el-radio-group>
            </el-form-item>

            <el-form-item label="邮箱">
                <el-input v-model="form.email" placeholder="abc@example.com">
                    <template #prefix><el-icon><Message /></el-icon></template>
                </el-input>
            </el-form-item>

            <el-form-item label="手机号">
                <el-input v-model="form.phone" placeholder="建议绑定手机以接收通知">
                    <template #prefix><el-icon><Iphone /></el-icon></template>
                </el-input>
            </el-form-item>

            <el-form-item class="mt-8">
                <el-button 
                    type="primary" 
                    @click="handleSubmit" 
                    class="px-8 bg-brand-500 border-none hover:bg-brand-600 shadow-md"
                >
                    保存修改
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
