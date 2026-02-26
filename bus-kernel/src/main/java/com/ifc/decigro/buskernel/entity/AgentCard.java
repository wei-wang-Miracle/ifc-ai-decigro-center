package com.ifc.decigro.buskernel.entity;

import com.ifc.decigro.buskernel.common.handler.Fastjson2TypeHandler;
import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.OffsetDateTime;
import java.util.List;

/**
 * MAS 智能体卡片实体类 (V2)
 * 功能: 对应数据库 agent_cards 表，主键变更为 agentName (String)
 */
@Data
@Table("agent_cards")
public class AgentCard implements Serializable {

    // =========================================
    // 1. Identity (数字身份)
    // =========================================

    /**
     * Agent 唯一标识 (主键)
     * VARCHAR(100)
     */
    @Id(keyType = KeyType.None)
    private String agentName;

    /**
     * Agent 别名/名称
     */
    private String agentAlias;

    /**
     * Agent 描述 (PRD: 工牌展示 agent_alias + agent_description)
     */
    private String agentDescription;

    // =========================================
    // 2. Registry Info
    // =========================================

    /**
     * Agent 标签列表 (JSONB)
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> agentTags;

    /**
     * Agent 类型 (PLANNER, EXECUTOR)
     */
    private String agentType;

    // =========================================
    // 3. Core Config
    // =========================================

    /**
     * 系统提示词
     */
    private String systemPrompt;

    /**
     * 负向提示词
     */
    private String negativePrompt;

    /**
     * 绑定的工具列表 (JSONB)
     * NULL = 全量, [] = 无工具, [...] = 白名单
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> boundTools;

    /**
     * PLANNER 绑定的 EXECUTOR 列表 (JSONB)
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> boundAgents;

    /**
     * 推理框架
     * e.g. 'ReAct', 'PlanSolve'
     */
    private String reasoningFramework;

    // =========================================
    // 4. Meta Data
    // =========================================

    /**
     * 版本号
     */
    private String agentVersion;

    /**
     * 是否上线
     */
    private Boolean isOnline;

    /**
     * 是否需要人工审核
     * true = 需要人工审核任务计划
     * false = 自动执行
     */
    private Boolean requireReview;

    /**
     * 管理人
     */
    private String managerBy;

    /**
     * 创建时间 (TIMESTAMPTZ)
     */
    @Column(onInsertValue = "now()")
    private OffsetDateTime createTime;

    /**
     * 更新时间 (TIMESTAMPTZ)
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private OffsetDateTime updateTime;
}
