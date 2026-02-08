<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '../../../utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, Refresh, Delete, Warning } from '@element-plus/icons-vue'

interface OnlineUser {
  tokenSign: string
  username: string
  ipAddress: string
  loginTime: string
  tenantCode: string
}

const tableData = ref<OnlineUser[]>([])
const loading = ref(false)

/**
 * 功能: 获取在线用户列表
 */
const fetchData = async () => {
    loading.value = true
    try {
        const res: any = await request.get('/user/online/list')
        tableData.value = res
    } catch (e: any) {
        ElMessage.error('获取在线用户失败: ' + (e.message || '未知错误'))
    } finally {
        loading.value = false
    }
}

/**
 * 功能: 踢出用户
 */
const handleKickout = (row: OnlineUser) => {
    ElMessageBox.confirm(
        `确定要将用户 [${row.username}] 强制踢下线吗？该操作将立即使其令牌失效。`,
        '安全警告',
        {
            confirmButtonText: '确定强退',
            cancelButtonText: '取消操作',
            type: 'warning',
            icon: Warning,
            roundButton: true
        }
    ).then(async () => {
        try {
            await request.post(`/user/online/kickout/${row.tokenSign}`)
            ElMessage.success('已强行清理该会话')
            fetchData()
        } catch (e: any) {
            ElMessage.error('操作失败: ' + (e.message || '未知错误'))
        }
    })
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
                <el-icon :size="20"><Monitor /></el-icon>
            </div>
            <div>
                <h3 class="text-lg font-bold text-gray-800">在线用户</h3>
                <p class="text-xs text-gray-400">实时监控并管理当前正在访问系统的活跃会话</p>
            </div>
        </div>
        <el-button type="default" :icon="Refresh" round size="large" @click="fetchData" :loading="loading">手动刷新</el-button>
    </div>

    <!-- 表格区域 -->
    <div class="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
        <el-table 
            v-loading="loading"
            :data="tableData" 
            style="width: 100%"
            class="custom-table"
        >
          <el-table-column label="位置" type="index" width="80" align="center" />
          <el-table-column prop="username" label="活跃账号" width="160">
              <template #default="scope">
                  <div class="flex items-center space-x-2">
                      <div class="w-7 h-7 bg-brand-500 rounded-full flex items-center justify-center text-[10px] text-white font-bold">
                          {{ scope.row.username?.[0]?.toUpperCase() }}
                      </div>
                      <span class="font-medium text-gray-700">{{ scope.row.username }}</span>
                  </div>
              </template>
          </el-table-column>
          <el-table-column prop="ipAddress" label="终端 IP 地址" width="150" align="center">
              <template #default="scope">
                  <code class="text-xs text-gray-400">{{ scope.row.ipAddress }}</code>
              </template>
          </el-table-column>
          <el-table-column prop="tenantCode" label="所属租户" width="120" align="center">
              <template #default="scope">
                  <el-tag size="small" effect="plain">{{ scope.row.tenantCode }}</el-tag>
              </template>
          </el-table-column>
          <el-table-column prop="loginTime" label="最后交互时间" min-width="180">
              <template #default="scope">
                  <span class="text-gray-400 text-sm">{{ scope.row.loginTime?.replace('T', ' ') }}</span>
              </template>
          </el-table-column>
          <el-table-column label="高级控制" width="120" fixed="right" align="center">
            <template #default="scope">
                <el-button 
                    link 
                    type="danger" 
                    :icon="Delete"
                    @click="handleKickout(scope.row)"
                    class="hover:bg-red-50 px-2 py-1 rounded"
                >
                    强退
                </el-button>
            </template>
          </el-table-column>
        </el-table>
    </div>
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
