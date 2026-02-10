<script setup lang="ts">
import { ref, watch } from 'vue'
import request from '../../utils/request'

// ============================================
// 组件 Props 定义
// ============================================

const props = defineProps<{
  traceId: string
}>()

const visible = defineModel<boolean>('visible', { default: false })

// ============================================
// 数据定义
// ============================================

const loading = ref(false)
const detail = ref<any>(null)

// ============================================
// 监听 traceId 变化，自动加载 ES 详情
// ============================================

watch(
  () => props.traceId,
  async (newId) => {
    if (newId && visible.value) {
      await fetchDetail(newId)
    }
  }
)

watch(visible, async (isVisible) => {
  if (isVisible && props.traceId) {
    await fetchDetail(props.traceId)
  }
})

// ============================================
// 接口调用
// ============================================

const fetchDetail = async (traceId: string) => {
  loading.value = true
  detail.value = null
  try {
    const res: any = await request.get(`/trace/detail/${traceId}`)
    detail.value = res
  } catch (e) {
    console.error('获取审计详情失败', e)
  } finally {
    loading.value = false
  }
}

// ============================================
// 辅助方法
// ============================================

// 工具执行状态颜色
const getToolStatusType = (status: string) => {
  return status === 'SUCCESS' ? 'success' : 'danger'
}

// 格式化 JSON 数据用于展示
const formatJson = (obj: any) => {
  if (!obj) return '—'
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}
</script>

<template>
  <el-drawer
    v-model="visible"
    title="审计详情"
    size="720px"
    class="audit-detail-drawer"
    direction="rtl"
    destroy-on-close>
    <div v-loading="loading" class="detail-content">
      <template v-if="detail">
        <!-- 环境快照 -->
        <div class="detail-section">
          <div class="section-header">
            <span class="section-icon">🔧</span>
            <span class="section-title">环境快照 (Environment)</span>
          </div>
          <div class="info-grid" v-if="detail.env_snapshot">
            <div class="info-item">
              <div class="label">Agent 名称</div>
              <div class="value mono">{{ detail.env_snapshot.agent_name || '—' }}</div>
            </div>
            <div class="info-item">
              <div class="label">Agent 版本</div>
              <div class="value mono">{{ detail.env_snapshot.agent_version || '—' }}</div>
            </div>
            <div class="info-item" v-if="detail.env_snapshot.model_config">
              <div class="label">模型提供商</div>
              <div class="value mono">{{ detail.env_snapshot.model_config.provider || '—' }}</div>
            </div>
            <div class="info-item" v-if="detail.env_snapshot.model_config">
              <div class="label">模型名称</div>
              <div class="value mono">{{ detail.env_snapshot.model_config.model_name || '—' }}</div>
            </div>
            <div class="info-item" v-if="detail.env_snapshot.model_config">
              <div class="label">Temperature</div>
              <div class="value mono">{{ detail.env_snapshot.model_config.temperature ?? '—' }}</div>
            </div>
            <div class="info-item" v-if="detail.env_snapshot.model_config">
              <div class="label">Max Tokens</div>
              <div class="value mono">{{ detail.env_snapshot.model_config.max_tokens ?? '—' }}</div>
            </div>
          </div>
          <!-- System Prompt -->
          <div v-if="detail.env_snapshot?.system_prompt" class="system-prompt-block">
            <div class="prompt-label">System Prompt</div>
            <pre class="prompt-content">{{ detail.env_snapshot.system_prompt }}</pre>
          </div>
        </div>

        <!-- 对话快照 -->
        <div class="detail-section">
          <div class="section-header">
            <span class="section-icon">💬</span>
            <span class="section-title">对话快照 (Dialogue)</span>
          </div>
          <div class="dialogue-block" v-if="detail.dialogue_snapshot">
            <!-- 用户提问 -->
            <div class="dialogue-item user">
              <div class="dialogue-role">用户提问</div>
              <div class="dialogue-content">{{ detail.dialogue_snapshot.user_query_full || '—' }}</div>
            </div>
            <!-- AI 回复 -->
            <div class="dialogue-item ai">
              <div class="dialogue-role">AI 回复</div>
              <div class="dialogue-content">{{ detail.dialogue_snapshot.ai_response_full || '—' }}</div>
            </div>
            <!-- 元信息 -->
            <div class="dialogue-meta">
              <span>完成原因: <strong>{{ detail.dialogue_snapshot.finish_reason || '—' }}</strong></span>
              <span>总 Tokens: <strong>{{ detail.dialogue_snapshot.total_tokens ?? '—' }}</strong></span>
            </div>

            <!-- 历史上下文窗口 -->
            <div v-if="detail.dialogue_snapshot.history_window?.length" class="history-section">
              <div class="history-label">历史上下文窗口 (最近 {{ detail.dialogue_snapshot.history_window.length }} 条)</div>
              <div
                v-for="(msg, idx) in detail.dialogue_snapshot.history_window"
                :key="idx"
                class="history-msg"
                :class="msg.role">
                <span class="msg-role">{{ msg.role }}</span>
                <span class="msg-content">{{ (msg.content || '').substring(0, 300) }}{{ (msg.content || '').length > 300 ? '...' : '' }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 工具执行时间轴 -->
        <div class="detail-section" v-if="detail.tool_snapshots?.length">
          <div class="section-header">
            <span class="section-icon">⚙️</span>
            <span class="section-title">工具执行时间轴 ({{ detail.tool_snapshots.length }} 次调用)</span>
          </div>
          <el-timeline class="tool-timeline">
            <el-timeline-item
              v-for="(tool, idx) in detail.tool_snapshots"
              :key="idx"
              :type="getToolStatusType(tool.status)"
              :timestamp="tool.start_time || ''"
              placement="top">
              <div class="tool-card">
                <div class="tool-header">
                  <span class="tool-name">{{ tool.tool_name }}</span>
                  <el-tag :type="getToolStatusType(tool.status)" size="small" effect="dark">
                    {{ tool.status }}
                  </el-tag>
                  <span class="tool-latency" v-if="tool.latency_ms">{{ tool.latency_ms }}ms</span>
                </div>
                <!-- 入参 -->
                <div class="tool-detail-row" v-if="tool.input_args">
                  <span class="tool-detail-label">入参:</span>
                  <pre class="tool-detail-value">{{ formatJson(tool.input_args) }}</pre>
                </div>
                <!-- 出参 -->
                <div class="tool-detail-row" v-if="tool.output_result">
                  <span class="tool-detail-label">出参:</span>
                  <pre class="tool-detail-value">{{ (tool.output_result || '').substring(0, 500) }}</pre>
                </div>
                <!-- 错误 -->
                <div class="tool-detail-row error" v-if="tool.error_message">
                  <span class="tool-detail-label">错误:</span>
                  <pre class="tool-detail-value">{{ tool.error_message }}</pre>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
        <div v-else class="detail-section">
          <div class="section-header">
            <span class="section-icon">⚙️</span>
            <span class="section-title">工具执行时间轴</span>
          </div>
          <div class="empty-tools">本次请求未调用任何工具</div>
        </div>
      </template>
      <div v-else-if="!loading" class="empty-state">
        暂无数据
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
/* === 审计详情抽屉样式 === */

.detail-content {
  padding: 0 4px;
}

.detail-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

.section-icon {
  font-size: 18px;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
}

/* --- 信息网格 --- */
.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.info-item .label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.info-item .value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

.mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

/* --- System Prompt --- */
.system-prompt-block {
  margin-top: 12px;
}

.prompt-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.prompt-content {
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

/* --- 对话快照 --- */
.dialogue-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dialogue-item {
  border-radius: 8px;
  padding: 12px 16px;
}

.dialogue-item.user {
  background: #ecf5ff;
  border-left: 4px solid #409eff;
}

.dialogue-item.ai {
  background: #f0f9eb;
  border-left: 4px solid #67c23a;
}

.dialogue-role {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 6px;
}

.dialogue-content {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.dialogue-meta {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #909399;
  padding: 4px 0;
}

/* --- 历史上下文 --- */
.history-section {
  margin-top: 12px;
}

.history-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
  font-weight: 600;
}

.history-msg {
  display: flex;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 13px;
}

.history-msg.human,
.history-msg.user {
  background: #fafafa;
}

.history-msg.ai,
.history-msg.assistant {
  background: #f5f7f5;
}

.msg-role {
  font-weight: 600;
  min-width: 55px;
  color: #606266;
  font-size: 11px;
  text-transform: uppercase;
}

.msg-content {
  color: #606266;
  word-break: break-word;
}

/* --- 工具时间轴 --- */
.tool-card {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.tool-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.tool-latency {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #909399;
}

.tool-detail-row {
  margin-top: 6px;
}

.tool-detail-label {
  font-size: 12px;
  color: #909399;
  font-weight: 600;
}

.tool-detail-value {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
  margin-top: 4px;
}

.tool-detail-row.error .tool-detail-value {
  border-color: #fde2e2;
  background: #fef0f0;
  color: #f56c6c;
}

.empty-tools {
  text-align: center;
  color: #c0c4cc;
  padding: 20px;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  color: #c0c4cc;
  padding: 60px 0;
  font-size: 16px;
}
</style>
