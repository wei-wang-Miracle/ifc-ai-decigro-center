package com.ifc.decigro.buskernel.dto;

import lombok.Data;

import java.util.List;

/**
 * AgentCard.humanReviewConfig 的结构化 DTO
 * 用于校验 HITL 配置的数据结构完整性
 *
 * 对应 PRD Entity A: Agent_HITL_Config
 * 支持两种模式：
 * - 旧版文本审核：仅使用 reviewDimensions / reviewInstruction / summaryPrompt
 * - 新版结构化审核：使用 uiSwitches + generationConstraints
 */
@Data
public class HumanReviewConfigDTO {

    /**
     * UI 模块开关，控制前端渲染哪些审核板块
     */
    private UISwitches uiSwitches;

    /**
     * LLM 生成约束，引导大模型按指定维度输出审核内容
     */
    private GenerationConstraints generationConstraints;

    // ===== 旧版兼容字段 =====

    /**
     * 审核维度列表（旧版配置）
     */
    private List<String> reviewDimensions;

    /**
     * 面向用户的审核引导语（旧版配置）
     */
    private String reviewInstruction;

    /**
     * 自定义审核摘要 prompt（旧版配置）
     */
    private String summaryPrompt;

    @Data
    public static class UISwitches {
        /**
         * 是否启用 ECharts 可视化图表
         */
        private Boolean visualDataEnable;

        /**
         * 是否启用结构化审核清单
         */
        private Boolean checkListEnable;

        /**
         * 是否启用多维建议方案
         */
        private Boolean proposalsEnable;
    }

    @Data
    public static class GenerationConstraints {
        /**
         * 深度洞察方向
         */
        private List<String> predictiveForesightFocus;

        /**
         * 摘要约束视角
         */
        private List<String> executiveSummaryPerspectives;

        /**
         * 图表约束视角
         */
        private List<String> visualDataPerspectives;

        /**
         * CheckList 审核维度
         */
        private List<String> checkListDimensions;

        /**
         * 建议方案约束视角
         */
        private List<String> proposalPerspectives;
    }
}
