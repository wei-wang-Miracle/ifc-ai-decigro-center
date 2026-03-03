package com.ifc.decigro.buskernel.entity.vo;

import com.ifc.decigro.buskernel.common.handler.Fastjson2TypeHandler;
import com.mybatisflex.annotation.Column;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.List;

/**
 * 智能体卡片简要信息 VO
 * 用于 AI 引擎加载阶段获取智能体介绍
 * 符合渐进式加载思想
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class AgentCardSummaryVO implements Serializable {

    /**
     * Agent 唯一标识
     */
    private String agentName;

    /**
     * Agent 别名/名称
     */
    private String agentAlias;

    /**
     * Agent 描述
     */
    private String agentDescription;

    /**
     * Agent 标签列表
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> agentTags;

    /**
     * Agent 类型 (PLANNER / EXECUTOR)
     * AI 引擎加载阶段需要此字段区分规划层与执行层，用于路由决策
     */
    private String agentType;

    /**
     * PLANNER 绑定的 EXECUTOR 列表
     * AI 引擎加载阶段需要此字段，以便在 dispatcher 阶段快速判断 Planner 的可用 Executor 范围
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> boundAgents;

    /**
     * 是否需要人工审核
     */
    private Boolean requireReview;
}
