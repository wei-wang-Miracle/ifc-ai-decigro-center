import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 应用配置状态库
 * 功能: 管理侧边栏收起/展开、主题等应用级别状态
 */
export const useAppStore = defineStore('app', () => {
  // 侧边栏收起状态
  const isSidebarCollapsed = ref(false)

  /**
   * 切换侧边栏状态
   */
  function toggleSidebar() {
    isSidebarCollapsed.value = !isSidebarCollapsed.value
  }

  /**
   * 设置侧边栏固定状态
   */
  function setSidebarCollapsed(collapsed: boolean) {
    isSidebarCollapsed.value = collapsed
  }

  return { 
    isSidebarCollapsed, 
    toggleSidebar, 
    setSidebarCollapsed 
  }
})
