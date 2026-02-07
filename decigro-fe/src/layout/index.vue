<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { RouterView, useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ArrowRight, User, Lock, SwitchButton, Calendar, Stamp, List, OfficeBuilding, Monitor, ArrowDown, PriceTag, Box } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 实时时间相关
const currentTime = ref('')
let timer: any = null

const updateTime = () => {
    const now = new Date()
    currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
    updateTime()
    timer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
    if (timer) clearInterval(timer)
})

// 登出处理
const handleLogout = () => {
    userStore.logout()
    router.push('/login')
}

// 路由跳转
const handleCommand = (command: string) => {
    switch (command) {
        case 'profile':
            router.push('/system/profile')
            break
        case 'password':
            router.push('/system/password')
            break
        case 'logout':
            handleLogout()
            break
    }
}

// 面包屑
const breadcrumbs = computed(() => {
    const matched = route.matched.filter(item => item.meta && item.meta.title)
    return matched
})
</script>

<template>
  <div class="common-layout h-full flex font-sans overflow-hidden">
    <!-- 侧边栏: DDS v3.0 品牌深色 #174EA6 -->
    <div class="w-64 bg-brand-900 text-white flex flex-col shadow-lg z-20">
        <div class="h-16 flex items-center px-6 font-bold text-xl border-b border-brand-700/50">
            <span class="tracking-wider">Deci<span class="text-brand-500">Gro</span></span>
        </div>
        
        <el-menu
            active-text-color="#ffffff"
            background-color="transparent"
            class="el-menu-vertical-demo flex-1 border-r-0 pt-4"
            :default-active="route.path"
            text-color="rgba(255, 255, 255, 0.7)"
            router
        >
            <el-sub-menu index="1">
                <template #title>
                    <el-icon><Setting /></el-icon>
                    <span>系统管理</span>
                </template>
                <el-menu-item index="/system/user">
                    <el-icon><User /></el-icon>
                    用户管理
                </el-menu-item>
                <el-menu-item index="/system/role">
                    <el-icon><Stamp /></el-icon>
                    角色管理
                </el-menu-item>
                <el-menu-item index="/system/dept">
                    <el-icon><List /></el-icon>
                    部门管理
                </el-menu-item>
                <el-menu-item index="/system/tenant">
                    <el-icon><OfficeBuilding /></el-icon>
                    租户管理
                </el-menu-item>
                <el-menu-item index="/system/online">
                    <el-icon><Monitor /></el-icon>
                    在线用户
                </el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/tag/list">
                <el-icon><PriceTag /></el-icon>
                标签管理
            </el-menu-item>
            <el-menu-item index="/tool/list">
                <el-icon><Box /></el-icon>
                工具管理
            </el-menu-item>
        </el-menu>
        
        <!-- 用户简要信息 -->
        <div class="p-4 bg-brand-700/30 border-t border-brand-700/50">
             <div class="flex items-center space-x-3">
                 <div class="w-8 h-8 rounded-full bg-brand-500 shadow-sm flex items-center justify-center text-xs font-bold ring-2 ring-brand-50/20">
                     {{ userStore.userInfo.username?.[0]?.toUpperCase() || 'U' }}
                 </div>
                 <div class="flex flex-col min-w-0">
                    <span class="text-sm font-medium truncate opacity-90">{{ userStore.userInfo.username }}</span>
                    <span class="text-[10px] opacity-50 uppercase tracking-tighter">Administrator</span>
                 </div>
             </div>
        </div>
    </div>

    <!-- 主体区 -->
    <div class="flex-1 flex flex-col bg-slate-50 relative overflow-hidden">
        <!-- 头部: 带实时时钟和用户中心 -->
        <header class="h-16 bg-white/80 backdrop-blur-md border-b border-gray-100 flex items-center justify-between px-6 z-10">
            <!-- 左侧: 面包屑 -->
            <div class="flex items-center">
                <el-breadcrumb :separator-icon="ArrowRight">
                    <el-breadcrumb-item :to="{ path: '/' }">系统首页</el-breadcrumb-item>
                    <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path">
                        {{ item.meta.title }}
                    </el-breadcrumb-item>
                </el-breadcrumb>
            </div>

            <!-- 右侧: 时钟 + 用户头像 -->
            <div class="flex items-center space-x-6">
                <!-- 实时时钟: JetBrains Mono -->
                <div class="flex items-center space-x-2 text-gray-400 bg-slate-50 px-3 py-1.5 rounded-full border border-gray-100 hover:text-brand-500 transition-colors">
                    <el-icon class="text-xs"><Calendar /></el-icon>
                    <span class="font-mono text-sm font-bold tracking-tighter">{{ currentTime }}</span>
                </div>

                <!-- 用户下拉菜单 -->
                <el-dropdown trigger="click" @command="handleCommand">
                    <div class="flex items-center cursor-pointer transition-all hover:opacity-80">
                        <el-avatar 
                            :size="32" 
                            class="bg-brand-500 ring-2 ring-brand-50 shadow-sm"
                        >
                            {{ userStore.userInfo.username?.[0]?.toUpperCase() || 'U' }}
                        </el-avatar>
                        <el-icon class="el-icon--right ml-1 text-gray-400"><ArrowDown /></el-icon>
                    </div>
                    <template #dropdown>
                        <el-dropdown-menu class="w-48 py-2 border-none shadow-xl">
                            <div class="px-4 py-3 border-b border-gray-50 mb-1">
                                <p class="text-[10px] text-gray-400 uppercase tracking-widest font-bold">当前登录账号</p>
                                <p class="text-sm font-bold text-gray-800 mt-1">{{ userStore.userInfo.username }}</p>
                            </div>
                            <el-dropdown-item command="profile">
                                <el-icon><User /></el-icon>个 人 资 料
                            </el-dropdown-item>
                            <el-dropdown-item command="password">
                                <el-icon><Lock /></el-icon>修 改 密 码
                            </el-dropdown-item>
                            <el-dropdown-item divided command="logout" class="text-red-500">
                                <el-icon><SwitchButton /></el-icon>安 全 登 出
                            </el-dropdown-item>
                        </el-dropdown-menu>
                    </template>
                </el-dropdown>
            </div>
        </header>

        <!-- 内容渲染区 -->
        <main class="flex-1 p-6 overflow-auto">
             <div class="max-w-7xl mx-auto h-full">
                <RouterView />
             </div>
        </main>
    </div>
  </div>
</template>

<style scoped>
:deep(.el-menu) {
    border-right: none;
}

:deep(.el-menu-item) {
    height: 50px;
    line-height: 50px;
    margin: 4px 12px;
    border-radius: 8px;
}

:deep(.el-menu-item.is-active) {
    background-color: var(--el-color-primary) !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(66, 133, 244, 0.3);
}

:deep(.el-sub-menu__title) {
    height: 50px;
    line-height: 50px;
    margin: 4px 12px;
    border-radius: 8px;
}

:deep(.el-sub-menu__title:hover) {
    background-color: rgba(255, 255, 255, 0.1) !important;
}
</style>
