<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import request from '../../utils/request'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import DetailDrawer from './DetailDrawer.vue'

// ============================================
// 第一部分：数据定义
// ============================================

// --- 接口类型定义 ---
interface TraceRecord {
  traceId: string
  sessionId: string
  taskId: string
  userId: string
  deptId: string
  tenantCode: string
  agentName: string
  agentVersion: string
  modelProvider: string
  userFeedback: number
  userIntent: string
  userTraceQuery: string
  aiTraceResponse: string
  executionPath: string[]
  toolsUsed: string[]
  status: string
  failureReason: string
  traceLatencyMs: number
  traceTotalTokens: number
  traceInputTokens: number
  traceOutputTokens: number
  createTime: string
  updateTime: string
}

// --- 列表数据 ---
const tableData = ref<TraceRecord[]>([])
const loading = ref(false)
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)

// --- 筛选条件 ---
const filters = reactive({
  traceId: '',
  userId: '',
  agentName: '',
  status: '',
  toolName: '',
  userFeedback: undefined as number | undefined,
  dateRange: [] as string[],
})

// --- 详情抽屉 ---
const drawerVisible = ref(false)
const currentTraceId = ref('')

// --- 状态选项 ---
const statusOptions = [
  { label: '全部', value: '' },
  { label: 'SUCCESS', value: 'SUCCESS' },
  { label: 'FAILED', value: 'FAILED' },
  { label: 'RUNNING', value: 'RUNNING' },
  { label: 'INTERRUPTED', value: 'INTERRUPTED' },
]

// --- 反馈选项 ---
const feedbackOptions = [
  { label: '全部', value: undefined },
  { label: '好评 👍', value: 1 },
  { label: '无反馈', value: 0 },
  { label: '差评 👎', value: -1 },
]

// ============================================
// 第二部分：接口调用
// ============================================

const fetchList = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pageNum.value,
      size: pageSize.value,
    }
    // 条件拼装：仅传非空值
    if (filters.traceId) params.traceId = filters.traceId
    if (filters.userId) params.userId = filters.userId
    if (filters.agentName) params.agentName = filters.agentName
    if (filters.status) params.status = filters.status
    if (filters.toolName) params.toolName = filters.toolName
    if (filters.userFeedback !== undefined) params.userFeedback = filters.userFeedback
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.startTime = filters.dateRange[0]
      params.endTime = filters.dateRange[1]
    }

    const res: any = await request.get('/trace/page', { params })
    tableData.value = res.records || []
    total.value = res.totalRow || 0
  } catch (e) {
    console.error('获取审计数据失败', e)
  } finally {
    loading.value = false
  }
}

// ============================================
// 第三部分：交互方法
// ============================================

const handleSearch = () => {
  pageNum.value = 1
  fetchList()
}

const handleReset = () => {
  filters.traceId = ''
  filters.userId = ''
  filters.agentName = ''
  filters.status = ''
  filters.toolName = ''
  filters.userFeedback = undefined
  filters.dateRange = []
  handleSearch()
}

const handleViewDetail = (traceId: string) => {
  currentTraceId.value = traceId
  drawerVisible.value = true
}

const handlePageChange = (page: number) => {
  pageNum.value = page
  fetchList()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  pageNum.value = 1
  fetchList()
}

// --- 状态徽章颜色 ---
const getStatusType = (status: string) => {
  switch (status) {
    case 'SUCCESS': return 'success'
    case 'FAILED': return 'danger'
    case 'RUNNING': return 'warning'
    case 'INTERRUPTED': return 'info'
    default: return 'info'
  }
}

// --- 延迟颜色编码 ---
const getLatencyClass = (ms: number | null) => {
  if (!ms) return 'latency-unknown'
  if (ms < 1000) return 'latency-fast'
  if (ms < 3000) return 'latency-normal'
  return 'latency-slow'
}

// --- 反馈图标 ---
const getFeedbackIcon = (feedback: number) => {
  switch (feedback) {
    case 1: return '👍'
    case -1: return '👎'
    default: return '—'
  }
}

// ============================================
// 第四部分：生命周期
// ============================================

onMounted(() => {
  fetchList()
})
</script>

<template>
  <div class="audit-page">
    <!-- 筛选区 -->
    <div class="filter-bar">
      <div class="filter-row">
        <el-date-picker
          v-model="filters.dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DDTHH:mm:ss"
          style="width: 360px"
          size="default" />
        <el-input
          v-model="filters.traceId"
          placeholder="Trace ID"
          clearable
          style="width: 180px"
          @keyup.enter="handleSearch" />
        <el-input
          v-model="filters.userId"
          placeholder="用户 ID"
          clearable
          style="width: 140px"
          @keyup.enter="handleSearch" />
        <el-input
          v-model="filters.agentName"
          placeholder="Agent 名称"
          clearable
          style="width: 140px"
          @keyup.enter="handleSearch" />
        <el-select
          v-model="filters.status"
          placeholder="状态"
          clearable
          style="width: 130px">
          <el-option
            v-for="opt in statusOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value" />
        </el-select>
        <el-input
          v-model="filters.toolName"
          placeholder="工具名称"
          clearable
          style="width: 140px"
          @keyup.enter="handleSearch" />
        <el-select
          v-model="filters.userFeedback"
          placeholder="反馈"
          clearable
          style="width: 110px">
          <el-option
            v-for="opt in feedbackOptions"
            :key="String(opt.value)"
            :label="opt.label"
            :value="opt.value" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button :icon="Refresh" @click="handleReset">重置</el-button>
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="table-container" v-loading="loading">
      <el-table
        :data="tableData"
        border
        stripe
        size="default"
        class="audit-table"
        :header-cell-style="{ background: '#f5f7fa', color: '#303133', fontWeight: '600' }">
        <!-- 链路标识 -->
        <el-table-column label="Trace ID" prop="traceId" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono-text trace-link" @click="handleViewDetail(row.traceId)">
              {{ row.traceId }}
            </span>
          </template>
        </el-table-column>

        <!-- 用户ID -->
        <el-table-column label="用户" prop="userId" width="100" show-overflow-tooltip />

        <!-- 摘要透视 -->
        <el-table-column label="用户提问" prop="userTraceQuery" min-width="200" show-overflow-tooltip />
        <el-table-column label="AI 回复" prop="aiTraceResponse" min-width="200" show-overflow-tooltip />

        <!-- 技术画像 -->
        <el-table-column label="Agent" prop="agentName" width="120" show-overflow-tooltip />
        <el-table-column label="意图" prop="userIntent" width="110" show-overflow-tooltip />
        <el-table-column label="工具" width="160">
          <template #default="{ row }">
            <div class="tool-tags" v-if="row.toolsUsed && row.toolsUsed.length">
              <el-tag
                v-for="tool in row.toolsUsed.slice(0, 2)"
                :key="tool"
                size="small"
                type="info"
                class="tool-tag">
                {{ tool }}
              </el-tag>
              <el-tag v-if="row.toolsUsed.length > 2" size="small" type="info">
                +{{ row.toolsUsed.length - 2 }}
              </el-tag>
            </div>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>

        <!-- 效能指标 -->
        <el-table-column label="延迟" width="90" align="center">
          <template #default="{ row }">
            <span :class="['latency-badge', getLatencyClass(row.traceLatencyMs)]">
              {{ row.traceLatencyMs ? `${row.traceLatencyMs}ms` : '—' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="Tokens" prop="traceTotalTokens" width="80" align="center">
          <template #default="{ row }">
            {{ row.traceTotalTokens ?? '—' }}
          </template>
        </el-table-column>

        <!-- 状态 & 反馈 -->
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small" effect="dark">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="反馈" width="60" align="center">
          <template #default="{ row }">
            {{ getFeedbackIcon(row.userFeedback) }}
          </template>
        </el-table-column>

        <!-- 时间 -->
        <el-table-column label="创建时间" prop="createTime" width="170" show-overflow-tooltip />

        <!-- 操作 -->
        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              :icon="View"
              size="small"
              link
              type="primary"
              @click="handleViewDetail(row.traceId)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="pageNum"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handleSizeChange" />
    </div>

    <!-- 详情抽屉 -->
    <DetailDrawer
      v-model:visible="drawerVisible"
      :trace-id="currentTraceId" />
  </div>
</template>

<style scoped>
/* === 审计监控页面样式 === */

.audit-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* --- 筛选区 --- */
.filter-bar {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px 20px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

/* --- 表格区 --- */
.table-container {
  flex: 1;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  overflow: auto;
}

.mono-text {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
}

.trace-link {
  color: #409eff;
  cursor: pointer;
  text-decoration: none;
}
.trace-link:hover {
  text-decoration: underline;
}

.tool-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tool-tag {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.text-muted {
  color: #c0c4cc;
}

/* --- 延迟颜色编码 --- */
.latency-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.latency-fast {
  color: #67c23a;
  background: #f0f9eb;
}

.latency-normal {
  color: #e6a23c;
  background: #fdf6ec;
}

.latency-slow {
  color: #f56c6c;
  background: #fef0f0;
}

.latency-unknown {
  color: #909399;
}

/* --- 分页 --- */
.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 8px 0;
}
</style>
