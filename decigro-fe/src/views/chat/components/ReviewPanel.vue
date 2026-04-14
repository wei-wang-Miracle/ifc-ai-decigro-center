<script setup lang="ts">
/**
 * ReviewPanel - 结构化审核面板组件
 *
 * 渲染 ProfessionalAuditResponse (Entity B) 为可交互 UI：
 * - 摘要区：summary_title + executive_summary + advanced_foresight
 * - 图表区：ECharts setOption 渲染
 * - 清单区：Checkbox 交互
 * - 方案区：Radio Card 选择
 * - 快捷操作栏 + 综合补充框
 *
 * emit submit 事件，payload 为 HumanDecisionPayload (Entity C)
 */
import { ref, reactive, computed, onMounted, nextTick, watch, onBeforeUnmount } from 'vue'
import { Check, Close, Warning, InfoFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type {
    StructuredAuditData,
    AuditCheckItemData,
    StrategicProposalData,
    HumanDecisionPayload
} from '../../../stores/chatStore'

const props = defineProps<{
    audit: StructuredAuditData
    sessionId: string
    /** 已提交后变为只读 */
    submitted?: boolean
    /** 提交时的决策标记，回显用 */
    decision?: 'approve_all_ai_recommendations' | 'reject_all' | 'custom'
}>()

const emit = defineEmits<{
    (e: 'submit', payload: HumanDecisionPayload): void
}>()

// ===== CheckList 交互状态 =====
const checkedItems = reactive<Record<string, boolean>>({})
// 初始化：全部默认勾选（AI 推荐）
onMounted(() => {
    props.audit.check_list.forEach(item => {
        checkedItems[item.item_id] = true
    })
})

// ===== Proposal 选择状态 =====
const selectedProposalId = ref<string | null>(null)
// 默认选中 AI 推荐的方案
onMounted(() => {
    const recommended = props.audit.proposals.find(p => p.is_recommond)
    if (recommended) {
        selectedProposalId.value = recommended.option_id
    }
})

// ===== 综合补充 =====
const supplementaryNotes = ref('')

// ===== ECharts 实例管理 =====
const chartRefs = ref<(HTMLElement | null)[]>([])
const chartInstances: echarts.ECharts[] = []

const initCharts = async () => {
    await nextTick()
    // 销毁旧实例
    chartInstances.forEach(c => c.dispose())
    chartInstances.length = 0

    props.audit.visual_data.forEach((chartConfig, idx) => {
        const dom = chartRefs.value[idx]
        if (!dom || chartConfig.chart_type === 'none') return
        try {
            const instance = echarts.init(dom)
            instance.setOption(chartConfig.option)
            chartInstances.push(instance)
        } catch (e) {
            console.warn(`[ReviewPanel] ECharts 渲染失败 (index=${idx}):`, e)
        }
    })
}

onMounted(initCharts)
watch(() => props.audit.visual_data, initCharts, { deep: true })

// 窗口 resize 时自适应
const handleResize = () => chartInstances.forEach(c => c.resize())
onMounted(() => window.addEventListener('resize', handleResize))
onBeforeUnmount(() => {
    window.removeEventListener('resize', handleResize)
    chartInstances.forEach(c => c.dispose())
})

// ===== 提交逻辑 =====
const buildPayload = (flag: HumanDecisionPayload['quick_decision_flag']): HumanDecisionPayload => {
    const accepted: HumanDecisionPayload['accepted'] = { check_list: [], proposals: [] }
    const rejected: HumanDecisionPayload['rejected'] = { check_list: [], proposals: [] }

    // 分拣 CheckList
    props.audit.check_list.forEach(item => {
        const target = checkedItems[item.item_id] ? accepted : rejected
        target.check_list.push({
            item_id: item.item_id,
            task_label: item.task_label,
            ai_observation: item.ai_observation
        })
    })

    // 分拣 Proposals
    props.audit.proposals.forEach(p => {
        const target = p.option_id === selectedProposalId.value ? accepted : rejected
        target.proposals.push({ option_id: p.option_id, title: p.title })
    })

    return {
        session_id: props.sessionId,
        quick_decision_flag: flag,
        accepted,
        rejected,
        comprehensive_supplementary_notes: supplementaryNotes.value
    }
}

const handleApproveAll = () => {
    emit('submit', buildPayload('approve_all_ai_recommendations'))
}

const handleRejectAll = () => {
    emit('submit', buildPayload('reject_all'))
}

const handleCustomSubmit = () => {
    emit('submit', buildPayload('custom'))
}

// 严重程度显示
const severityMap: Record<string, { label: string; type: string }> = {
    high: { label: '高', type: 'danger' },
    medium: { label: '中', type: 'warning' },
    low: { label: '低', type: 'info' }
}

// 成本显示
const effortMap: Record<string, string> = {
    high: '高成本',
    medium: '中成本',
    low: '低成本'
}

// 决策标记显示
const decisionLabelMap: Record<string, string> = {
    approve_all_ai_recommendations: '全部接受 AI 建议',
    reject_all: '全部驳回',
    custom: '自定义决策'
}
const decisionLabel = computed(() => decisionLabelMap[props.decision || ''] || props.decision || '')
</script>

<template>
    <div class="review-panel">
        <!-- 摘要区 -->
        <div class="rp-summary">
            <h3 class="rp-title">{{ audit.summary_title }}</h3>
            <p class="rp-executive">{{ audit.executive_summary }}</p>
            <div v-if="audit.advanced_foresight" class="rp-foresight">
                <el-icon class="rp-foresight-icon"><InfoFilled /></el-icon>
                <span>{{ audit.advanced_foresight }}</span>
            </div>
        </div>

        <!-- ECharts 图表区 -->
        <div v-if="audit.visual_data && audit.visual_data.length > 0" class="rp-charts">
            <div class="rp-section-label">数据洞察</div>
            <div v-for="(chart, idx) in audit.visual_data" :key="idx" class="rp-chart-item">
                <div
                    v-if="chart.chart_type !== 'none'"
                    :ref="(el: any) => { chartRefs[idx] = el }"
                    class="rp-chart-container"
                ></div>
                <p class="rp-chart-insight">{{ chart.insight_text }}</p>
            </div>
        </div>

        <!-- CheckList 审核清单 -->
        <div v-if="audit.check_list && audit.check_list.length > 0" class="rp-checklist">
            <div class="rp-section-label">审核清单</div>
            <div v-for="item in audit.check_list" :key="item.item_id" class="rp-check-item">
                <el-checkbox
                    v-model="checkedItems[item.item_id]"
                    class="rp-check-box"
                    :disabled="submitted"
                >
                    <div class="rp-check-content">
                        <div class="rp-check-header">
                            <span class="rp-check-label">{{ item.task_label }}</span>
                            <el-tag
                                :type="(severityMap[item.severity]?.type as any) || 'info'"
                                size="small"
                                effect="plain"
                            >
                                {{ severityMap[item.severity]?.label || item.severity }}
                            </el-tag>
                        </div>
                        <p class="rp-check-observation">{{ item.ai_observation }}</p>
                    </div>
                </el-checkbox>
            </div>
        </div>

        <!-- Proposal 建议方案 -->
        <div v-if="audit.proposals && audit.proposals.length > 0" class="rp-proposals">
            <div class="rp-section-label">建议方案</div>
            <div class="rp-proposal-grid">
                <div
                    v-for="proposal in audit.proposals"
                    :key="proposal.option_id"
                    :class="[
                        'rp-proposal-card',
                        { 'is-selected': selectedProposalId === proposal.option_id },
                        { 'is-recommended': proposal.is_recommond },
                        { 'is-disabled': submitted }
                    ]"
                    @click="!submitted && (selectedProposalId = proposal.option_id)"
                >
                    <div class="rp-proposal-header">
                        <span class="rp-proposal-title">{{ proposal.title }}</span>
                        <el-tag v-if="proposal.is_recommond" type="success" size="small" effect="dark">
                            推荐
                        </el-tag>
                    </div>
                    <p class="rp-proposal-reason">{{ proposal.recommond_reason }}</p>
                    <div class="rp-proposal-meta">
                        <span class="rp-proposal-effort">{{ effortMap[proposal.effort_estimation] || proposal.effort_estimation }}</span>
                        <span class="rp-proposal-divider">|</span>
                        <span class="rp-proposal-impact">{{ proposal.impact_analysis }}</span>
                    </div>
                    <div v-if="selectedProposalId === proposal.option_id" class="rp-proposal-check">
                        <el-icon><Check /></el-icon>
                    </div>
                </div>
            </div>
        </div>

        <!-- 综合补充 -->
        <div class="rp-notes">
            <div class="rp-section-label">补充说明 <span class="rp-optional">(选填)</span></div>
            <el-input
                v-model="supplementaryNotes"
                type="textarea"
                :rows="2"
                placeholder="如有补充意见，请在此填写..."
                resize="none"
                :disabled="submitted"
            />
        </div>

        <!-- 操作栏 -->
        <div class="rp-actions" v-if="!submitted">
            <el-button type="success" @click="handleApproveAll">
                <el-icon class="mr-1"><Check /></el-icon>
                全部接受
            </el-button>
            <el-button type="primary" @click="handleCustomSubmit">
                提交自定义决策
            </el-button>
            <el-button type="danger" plain @click="handleRejectAll">
                <el-icon class="mr-1"><Close /></el-icon>
                全部驳回
            </el-button>
        </div>
        <!-- 已提交回显 -->
        <div v-else class="rp-submitted-bar">
            <el-icon class="rp-submitted-icon"><Check /></el-icon>
            <span>已提交：{{ decisionLabel }}</span>
        </div>
    </div>
</template>

<style scoped>
.review-panel {
    padding: 16px 0;
    font-size: 13px;
    color: #334155;
}

/* 摘要区 */
.rp-summary { margin-bottom: 20px; }
.rp-title { font-size: 16px; font-weight: 700; color: #0f172a; margin: 0 0 8px; }
.rp-executive { color: #475569; line-height: 1.65; margin: 0 0 10px; }
.rp-foresight {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 10px 12px;
    background: #eff6ff;
    border-left: 3px solid #3b82f6;
    border-radius: 0 6px 6px 0;
    font-size: 12px;
    color: #1e40af;
    line-height: 1.5;
}
.rp-foresight-icon { flex-shrink: 0; margin-top: 2px; color: #3b82f6; }

/* Section 标签 */
.rp-section-label {
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 10px;
}
.rp-optional { font-weight: 400; color: #cbd5e1; }

/* ECharts 图表区 */
.rp-charts { margin-bottom: 20px; }
.rp-chart-item { margin-bottom: 14px; }
.rp-chart-container { width: 100%; height: 260px; }
.rp-chart-insight {
    font-size: 11px;
    color: #64748b;
    margin: 6px 0 0;
    padding-left: 4px;
    font-style: italic;
}

/* CheckList */
.rp-checklist { margin-bottom: 20px; }
.rp-check-item {
    padding: 10px 12px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-bottom: 8px;
    transition: border-color 0.2s;
}
.rp-check-item:hover { border-color: #94a3b8; }
.rp-check-box { align-items: flex-start; width: 100%; }
.rp-check-box :deep(.el-checkbox__label) { flex: 1; }
.rp-check-content { flex: 1; }
.rp-check-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.rp-check-label { font-weight: 600; color: #1e293b; flex: 1; }
.rp-check-observation { font-size: 12px; color: #64748b; margin: 0; line-height: 1.5; }

/* Proposals */
.rp-proposals { margin-bottom: 20px; }
.rp-proposal-grid { display: flex; flex-direction: column; gap: 10px; }
.rp-proposal-card {
    position: relative;
    padding: 14px 16px;
    border: 2px solid #e2e8f0;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
}
.rp-proposal-card:hover { border-color: #94a3b8; }
.rp-proposal-card.is-selected { border-color: #3b82f6; background: #f0f7ff; }
.rp-proposal-card.is-recommended { border-color: #86efac; }
.rp-proposal-card.is-selected.is-recommended { border-color: #22c55e; background: #f0fdf4; }
.rp-proposal-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.rp-proposal-title { font-weight: 700; color: #0f172a; font-size: 14px; }
.rp-proposal-reason { font-size: 12px; color: #475569; margin: 0 0 8px; line-height: 1.5; }
.rp-proposal-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: #94a3b8;
}
.rp-proposal-effort { font-weight: 600; }
.rp-proposal-divider { color: #e2e8f0; }
.rp-proposal-impact { flex: 1; }
.rp-proposal-check {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 22px;
    height: 22px;
    background: #3b82f6;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 12px;
}

/* 补充说明 */
.rp-notes { margin-bottom: 16px; }
.rp-notes :deep(.el-textarea__inner) {
    font-size: 13px;
    border-radius: 8px;
}

/* 操作栏 */
.rp-actions {
    display: flex;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px dashed #e2e8f0;
}
.rp-actions .el-button { flex: 1; }

/* 已提交回显条 */
.rp-submitted-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 14px;
    margin-top: 12px;
    border-top: 1px dashed #e2e8f0;
    background: #f0fdf4;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #15803d;
}
.rp-submitted-icon { color: #22c55e; font-size: 16px; }

/* Disabled proposal card */
.rp-proposal-card.is-disabled {
    cursor: default;
    opacity: 0.7;
    pointer-events: none;
}
</style>
