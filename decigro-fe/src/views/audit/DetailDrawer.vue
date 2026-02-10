<template>
  <!-- 审计详情抽屉（v3 增强信息呈现版本） -->
  <el-drawer
    v-model="visible"
    title="审计追踪详情"
    direction="rtl"
    size="55%"
    @close="handleClose"
  >
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-box">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载详情...</span>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="error-box">
      <el-icon><WarningFilled /></el-icon>
      <span>{{ error }}</span>
    </div>

    <!-- 详情内容 -->
    <div v-else-if="detail" class="detail-content">
      <!-- 顶部概要信息卡片 -->
      <div class="summary-card">
        <div class="summary-header">
          <span class="trace-id">Trace: {{ detail.trace_id }}</span>
          <el-tag v-if="detail.task_id" type="info" size="small" effect="plain">
            Task: {{ detail.task_id }}
          </el-tag>
        </div>
        <div class="summary-meta">
          <span><el-icon><User /></el-icon> {{ detail.user_id || '未知用户' }}</span>
          <span><el-icon><Clock /></el-icon> {{ formatTime(detail.start_time) }}</span>
          <span v-if="detail.session_id" class="session-tag">
            Session: {{ detail.session_id?.substring(0, 12) }}...
          </span>
        </div>
      </div>

      <!-- 对话摘要 -->
      <div v-if="detail.dialogue_summary" class="section dialogue-section">
        <h4 class="section-title">
          <el-icon><ChatDotRound /></el-icon> 对话摘要
        </h4>
        <div class="dialogue-box">
          <div class="msg user-msg">
            <div class="msg-label">用户输入</div>
            <div class="msg-content">{{ detail.dialogue_summary.user_query || '无' }}</div>
          </div>
          <div class="msg ai-msg">
            <div class="msg-label">AI 回复</div>
            <div class="msg-content">{{ detail.dialogue_summary.ai_response || '无' }}</div>
          </div>
        </div>
      </div>

      <!-- 图节点执行轨迹 -->
      <div class="section graph-section">
        <h4 class="section-title">
          <el-icon><Connection /></el-icon> 执行轨迹（{{ graphNodes.length }} 个节点）
        </h4>

        <div v-if="graphNodes.length === 0" class="empty-hint">
          暂无节点追踪数据
        </div>

        <!-- 时间轴 -->
        <el-timeline v-else>
          <el-timeline-item
            v-for="(node, idx) in graphNodes"
            :key="idx"
            :type="getNodeTagType(node.status)"
            :hollow="node.status === 'IN_PROGRESS'"
            :timestamp="formatNodeTime(node)"
            placement="top"
          >
            <div class="node-card">
              <!-- 节点头部：直接使用 node_name -->
              <div class="node-header">
                <span class="node-name">{{ node.node_name }}</span>
                <el-tag :type="getNodeTagType(node.status)" size="small" effect="plain">
                  {{ node.status || 'UNKNOWN' }}
                </el-tag>
                <span v-if="node.latency_ms != null" class="latency" :class="getLatencyClass(node.latency_ms)">
                  {{ node.latency_ms }}ms
                </span>
              </div>

              <!-- 节点输出结果 -->
              <div v-if="node.node_result" class="node-result">
                <el-collapse>
                  <el-collapse-item title="节点输出">
                    <pre class="result-pre">{{ node.node_result }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </div>

              <!-- Agent 快照列表 -->
              <div v-if="node.agent_snapshots && node.agent_snapshots.length > 0" class="agent-list">
                <div
                  v-for="(agent, aIdx) in node.agent_snapshots"
                  :key="aIdx"
                  class="agent-card"
                >
                  <div class="agent-header">
                    <el-icon><Avatar /></el-icon>
                    <span class="agent-name">{{ agent.agent_name || '默认 Agent' }}</span>
                    <el-tag
                      v-if="agent.model_config?.model_name"
                      size="small"
                      type="info"
                      effect="plain"
                    >
                      {{ agent.model_config.model_name }}
                    </el-tag>
                  </div>

                  <!-- Agent 系统提示词（可折叠） -->
                  <div v-if="agent.system_prompt" class="agent-detail-section">
                    <el-collapse>
                      <el-collapse-item title="System Prompt">
                        <pre class="result-pre prompt-pre">{{ agent.system_prompt }}</pre>
                      </el-collapse-item>
                    </el-collapse>
                  </div>

                  <!-- Agent 输出结果（可折叠） -->
                  <div v-if="agent.agent_result" class="agent-detail-section">
                    <el-collapse>
                      <el-collapse-item title="Agent 输出">
                        <pre class="result-pre">{{ agent.agent_result }}</pre>
                      </el-collapse-item>
                    </el-collapse>
                  </div>

                  <!-- 工具调用列表 -->
                  <div v-if="agent.tools_snapshot && agent.tools_snapshot.length > 0" class="tools-list">
                    <div class="tools-list-title">🔧 工具调用 ({{ agent.tools_snapshot.length }})</div>
                    <div
                      v-for="(tool, tIdx) in agent.tools_snapshot"
                      :key="tIdx"
                      class="tool-item"
                    >
                      <div class="tool-header">
                        <el-icon><SetUp /></el-icon>
                        <span class="tool-name">{{ tool.tool_name }}</span>
                        <el-tag
                          v-if="tool.tool_type"
                          size="small"
                          type="warning"
                          effect="plain"
                          class="tool-type-tag"
                        >
                          {{ tool.tool_type }}
                        </el-tag>
                        <el-tag :type="tool.status === 'SUCCESS' ? 'success' : 'danger'" size="small">
                          {{ tool.status }}
                        </el-tag>
                        <span v-if="tool.latency_ms != null" class="tool-latency">
                          {{ tool.latency_ms }}ms
                        </span>
                      </div>
                      <!-- 工具入参 -->
                      <div v-if="tool.input_args" class="tool-detail">
                        <span class="detail-label">入参:</span>
                        <pre class="json-pre">{{ formatJson(tool.input_args) }}</pre>
                      </div>
                      <!-- 工具出参 -->
                      <div v-if="tool.output_result" class="tool-detail">
                        <span class="detail-label">出参:</span>
                        <pre class="json-pre output-pre">{{ formatJson(tool.output_result) }}</pre>
                      </div>
                      <!-- 错误信息 -->
                      <div v-if="tool.error_message" class="tool-detail error-detail">
                        <span class="detail-label">错误:</span>
                        <span>{{ tool.error_message }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import request from '../../utils/request'
import {
  Loading, WarningFilled, User, Clock, ChatDotRound,
  Connection, Avatar, SetUp
} from '@element-plus/icons-vue'

// Props
const props = defineProps<{
  modelValue: boolean
  traceId: string
}>()

// Emits
const emit = defineEmits(['update:modelValue'])

// 状态
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const error = ref('')
const detail = ref<any>(null)

// 计算属性：提取 graph_nodes 数组
const graphNodes = computed(() => {
  return detail.value?.graph_nodes || []
})

// 监听 traceId 变化，自动加载详情
watch(() => props.traceId, (newId) => {
  if (newId && props.modelValue) {
    loadDetail(newId)
  }
})

watch(() => props.modelValue, (val) => {
  if (val && props.traceId) {
    loadDetail(props.traceId)
  }
})

// 加载详情数据
async function loadDetail(traceId: string) {
  loading.value = true
  error.value = ''
  detail.value = null

  try {
    const res = await request.get(`/trace/detail/${traceId}`)
    // request 拦截器已处理 Result 包装并返回了 .data
    if (res) {
      detail.value = res
    } else {
      error.value = '未找到该追踪记录详情'
    }
  } catch (e: any) {
    error.value = e.message || '网络请求失败'
  } finally {
    loading.value = false
  }
}

function handleClose() {
  detail.value = null
  error.value = ''
}

// 工具函数
function formatTime(t: string) {
  if (!t) return '—'
  try {
    return new Date(t).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return t
  }
}

function formatNodeTime(node: any) {
  const parts: string[] = []
  if (node.start_time) {
    parts.push(formatTime(node.start_time))
  }
  if (node.latency_ms != null) {
    parts.push(`耗时 ${node.latency_ms}ms`)
  }
  return parts.join(' · ') || '—'
}

function getNodeTagType(status: string) {
  switch (status) {
    case 'SUCCESS': return 'success'
    case 'FAILED': return 'danger'
    case 'IN_PROGRESS': return 'warning'
    case 'SKIPPED': return 'info'
    default: return 'info'
  }
}

function getLatencyClass(ms: number) {
  if (ms < 500) return 'latency-fast'
  if (ms < 2000) return 'latency-normal'
  return 'latency-slow'
}

function formatJson(obj: any) {
  if (!obj) return ''
  if (typeof obj === 'string') {
    try { return JSON.stringify(JSON.parse(obj), null, 2) } catch { return obj }
  }
  try { return JSON.stringify(obj, null, 2) } catch { return String(obj) }
}

</script>

<style scoped>
/* -- 加载和错误状态 -- */
.loading-box, .error-box {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}
.error-box { color: var(--el-color-danger); }

/* -- 概要卡片 -- */
.summary-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  padding: 16px 20px;
  color: #fff;
  margin-bottom: 20px;
}
.summary-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.trace-id {
  font-size: 13px;
  font-family: 'Menlo', 'Monaco', monospace;
  opacity: 0.9;
}
.summary-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  opacity: 0.85;
}
.summary-meta .el-icon { vertical-align: -2px; }
.session-tag { font-family: monospace; }

/* -- 通用 Section -- */
.section {
  margin-bottom: 24px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

/* -- 对话摘要 -- */
.dialogue-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.msg {
  border-radius: 10px;
  padding: 12px 16px;
}
.msg-label {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.user-msg {
  background: #e8f4fd;
  border-left: 3px solid #409eff;
}
.user-msg .msg-label { color: #409eff; }
.ai-msg {
  background: #f0f9eb;
  border-left: 3px solid #67c23a;
}
.ai-msg .msg-label { color: #67c23a; }
.msg-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  word-break: break-word;
}

/* -- 图节点时间轴 -- */
.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--el-text-color-secondary);
}

.node-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 12px 16px;
  transition: box-shadow 0.2s;
}
.node-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.latency {
  margin-left: auto;
  font-size: 12px;
  font-family: monospace;
  font-weight: 500;
}
.latency-fast { color: #67c23a; }
.latency-normal { color: #e6a23c; }
.latency-slow { color: #f56c6c; }

/* -- 节点输出结果 -- */
.node-result {
  margin-top: 4px;
  margin-bottom: 8px;
}

/* -- 通用 result-pre 样式 -- */
.result-pre {
  background: var(--el-fill-color);
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-family: 'Menlo', 'Monaco', monospace;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  line-height: 1.5;
}
.prompt-pre {
  max-height: 150px;
  color: var(--el-text-color-secondary);
}

/* -- Agent 卡片 -- */
.agent-list {
  margin-top: 8px;
}
.agent-card {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.agent-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--el-text-color-regular);
}
.agent-name { font-weight: 600; }

/* -- Agent 详情区域（system_prompt & agent_result） -- */
.agent-detail-section {
  margin-top: 6px;
}
.agent-detail-section :deep(.el-collapse) {
  border: none;
}
.agent-detail-section :deep(.el-collapse-item__header) {
  height: 28px;
  line-height: 28px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  background: transparent;
  border-bottom: none;
}
.agent-detail-section :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}
.agent-detail-section :deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}

/* -- 节点输出折叠样式 -- */
.node-result :deep(.el-collapse) {
  border: none;
}
.node-result :deep(.el-collapse-item__header) {
  height: 28px;
  line-height: 28px;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  background: transparent;
  border-bottom: none;
}
.node-result :deep(.el-collapse-item__wrap) {
  border-bottom: none;
  background: transparent;
}
.node-result :deep(.el-collapse-item__content) {
  padding-bottom: 4px;
}

/* -- 工具调用列表 -- */
.tools-list {
  margin-top: 8px;
  border-top: 1px dashed var(--el-border-color);
  padding-top: 8px;
}
.tools-list-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}
.tool-item {
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.tool-item:last-child { border-bottom: none; }

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.tool-name {
  font-weight: 600;
  font-family: monospace;
  color: var(--el-text-color-primary);
}
.tool-type-tag {
  font-size: 10px;
}
.tool-latency {
  margin-left: auto;
  font-size: 11px;
  font-family: monospace;
  color: var(--el-text-color-secondary);
}

.tool-detail {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.detail-label {
  font-weight: 600;
  margin-right: 4px;
  color: var(--el-text-color-regular);
}
.json-pre {
  background: var(--el-fill-color);
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-family: 'Menlo', 'Monaco', monospace;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin-top: 4px;
}
.output-pre {
  max-height: 80px;
}
.error-detail {
  color: var(--el-color-danger);
}
</style>
