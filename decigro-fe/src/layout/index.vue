<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { RouterView, useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'
import { useAppStore } from '../stores/app'
import { ArrowRight, User, Lock, SwitchButton, Calendar, Stamp, List, OfficeBuilding, ArrowDown, Box, Cpu, Promotion, Fold, Expand } from '@element-plus/icons-vue'


const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

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
    <div 
        :class="[
            'bg-brand-900 text-white flex flex-col shadow-lg z-20 transition-all duration-300 ease-in-out overflow-hidden whitespace-nowrap',
            appStore.isSidebarCollapsed ? 'w-20' : 'w-64'
        ]"
    >
        <div class="h-16 flex items-center px-6 font-bold text-xl border-b border-brand-700/50 flex-shrink-0">
            <span v-if="!appStore.isSidebarCollapsed" class="tracking-wider">Deci<span class="text-brand-500">Gro</span></span>
            <span v-else class="text-brand-500 w-full text-center">DG</span>
        </div>
        
        <el-menu
            active-text-color="#ffffff"
            background-color="transparent"
            class="el-menu-vertical-demo flex-1 border-r-0 pt-4"
            :default-active="route.path"
            :collapse="appStore.isSidebarCollapsed"
            :collapse-transition="false"
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
                    <template #title>用户管理</template>
                </el-menu-item>
                <el-menu-item index="/system/role">
                    <el-icon><Stamp /></el-icon>
                    <template #title>角色管理</template>
                </el-menu-item>
                <el-menu-item index="/system/dept">
                    <el-icon><List /></el-icon>
                    <template #title>部门管理</template>
                </el-menu-item>
                <el-menu-item index="/system/tenant">
                    <el-icon><OfficeBuilding /></el-icon>
                    <template #title>租户管理</template>
                </el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/tool/list">
                <el-icon><Box /></el-icon>
                <template #title>工具管理</template>
            </el-menu-item>
            <el-menu-item index="/agent/list">
                <el-icon><Cpu /></el-icon>
                <template #title>智能体管理</template>
            </el-menu-item>
            <el-menu-item index="/chat/index">
                <el-icon><Promotion /></el-icon>
                <template #title>AI 智能对话</template>
            </el-menu-item>
        </el-menu>
        
        <!-- 用户简要信息 -->
        <div class="p-4 bg-brand-700/30 border-t border-brand-700/50 flex-shrink-0">
             <div class="flex items-center space-x-3 overflow-hidden">
                 <div class="w-8 h-8 flex-shrink-0 rounded-full bg-brand-500 shadow-sm flex items-center justify-center text-xs font-bold ring-2 ring-brand-50/20">
                     {{ userStore.userInfo.username?.[0]?.toUpperCase() || 'U' }}
                 </div>
                 <div v-if="!appStore.isSidebarCollapsed" class="flex flex-col min-w-0 transition-opacity duration-300">
                    <span class="text-sm font-medium truncate opacity-90">{{ userStore.userInfo.username }}</span>
                    <span class="text-[10px] opacity-50 uppercase tracking-tighter">Administrator</span>
                 </div>
             </div>
        </div>
    </div>

    <div class="flex-1 flex flex-col bg-slate-50 relative overflow-hidden">
        <!-- AI 助手挂件 -->

        
        <!-- 头部: 带实时时钟和用户中心 -->
        <header class="h-16 bg-white/80 backdrop-blur-md border-b border-gray-100 flex items-center justify-between px-6 z-10 flex-shrink-0">
            <!-- 左侧: 面包屑 + 切换按钮 -->
            <div class="flex items-center space-x-4">
                <div 
                    class="p-1 cursor-pointer text-gray-400 hover:text-brand-500 transition-colors"
                    @click="appStore.toggleSidebar"
                >
                    <el-icon size="20">
                        <Expand v-if="appStore.isSidebarCollapsed" />
                        <Fold v-else />
                    </el-icon>
                </div>
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
        <main
            :class="[
                'flex-1 overflow-auto transition-all duration-300',
                route.path === '/chat/index' ? 'p-0' : 'p-4'
            ]"
        >
             <div
                :class="[
                    'h-full transition-all duration-300',
                    route.path === '/chat/index' ? 'max-w-none' : 'max-w-none'
                ]"
             >
                <RouterView />
             </div>
        </main>
    </div>
  </div>
</template>

<style scoped>
/* 侧边栏整体样式 */
:deep(.el-menu) {
    border-right: none;
    transition: width 0.3s;
}

/* 菜单项基础样式 */
:deep(.el-menu-item),
:deep(.el-sub-menu__title) {
    height: 50px;
    line-height: 50px;
    margin: 4px 12px;
    border-radius: 8px;
    transition: all 0.3s ease;
}

/* 展开状态：选中高亮 */
:deep(.el-menu-item.is-active),
:deep(.el-sub-menu.is-active > .el-sub-menu__title) {
    background-color: var(--el-color-primary) !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(66, 133, 244, 0.3);
}

/* --------------------------------------------------
   收缩状态 (Collapse) 核心修复：对齐与尺寸
   -------------------------------------------------- */
:deep(.el-menu--collapse) .el-menu-item,
:deep(.el-menu--collapse) .el-sub-menu__title {
    margin: 4px 0 !important;
    padding: 0 !important;
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* 修复激活状态下的“小方块”背景 */
:deep(.el-menu--collapse) .el-menu-item.is-active,
:deep(.el-menu--collapse) .el-sub-menu.is-active > .el-sub-menu__title {
    position: relative;
    background-color: transparent !important; /* 容器背景透明 */
    box-shadow: none !important;
}

/* 使用伪元素制作固定比例的背景方块，确保图标始终在方块正中 */
:deep(.el-menu--collapse) .el-menu-item.is-active::after,
:deep(.el-menu--collapse) .el-sub-menu.is-active > .el-sub-menu__title::after {
    content: '';
    position: absolute;
    width: 42px;
    height: 42px;
    background-color: var(--el-color-primary);
    border-radius: 12px;
    z-index: 0;
}

:deep(.el-menu--collapse) .el-icon {
    position: relative;
    z-index: 1;
    margin: 0 !important;
    font-size: 20px;
    color: inherit;
}

:deep(.el-menu--collapse) .el-menu-item.is-active .el-icon,
:deep(.el-menu--collapse) .el-sub-menu.is-active > .el-sub-menu__title .el-icon {
    color: white !important;
}

/* 隐藏收缩后的弹出箭头 */
:deep(.el-menu--collapse) .el-sub-menu__icon-arrow {
    display: none !important;
}
</style>

<!-- 
    注意：子菜单弹出框 (Popper) 是挂载在 body 上的，
    Scoped 样式无法触及，必须使用非 Scoped 样式进行全局覆盖。
-->
<style>
.el-menu--popup {
    background-color: #1a202c !important; /* 使用更深的深灰色/深蓝色背景 */
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
}

.el-menu--popup .el-menu-item {
    color: rgba(255, 255, 255, 0.8) !important;
    font-size: 13px !important;
}

.el-menu--popup .el-menu-item:hover {
    background-color: #174EA6 !important;
    color: white !important;
}

.el-menu--popup .el-menu-item.is-active {
    background-color: #174EA6 !important;
    color: white !important;
    font-weight: bold;
}
</style>
