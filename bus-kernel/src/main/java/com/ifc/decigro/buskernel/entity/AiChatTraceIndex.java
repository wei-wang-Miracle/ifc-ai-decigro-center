package com.ifc.decigro.buskernel.entity;

import com.ifc.decigro.buskernel.common.handler.Fastjson2TypeHandler;
import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.OffsetDateTime;
import java.util.List;

/**
 * AI 全链路审计宽表实体类
 * 功能: 对应数据库 ai_chat_trace_index 表
 * 核心价值: 利用 PG 索引承担 90% 的日常查询、筛选、统计需求
 */
@Data
@Table("ai_chat_trace_index")
public class AiChatTraceIndex implements Serializable {

    // === 1. 链路指纹 (Identity) ===

    /**
     * 全局唯一请求ID (与 ES _id 一一对应)
     */
    @Id
    private String traceId;

    /**
     * 会话ID
     */
    private String sessionId;

    /**
     * 异步任务ID (可空)
     */
    private String taskId;

    /**
     * 用户ID
     */
    private String userId;

    /**
     * 部门ID
     */
    private String deptId;

    /**
     * 多租户隔离字段
     */
    private String tenantCode;

    // === 2. 智能体画像 (Agent Profile) ===

    /**
     * 入口 Agent 名称
     */
    private String agentName;

    /**
     * Agent 版本号
     */
    private String agentVersion;

    /**
     * 模型底座 (e.g., "gpt-4-turbo")
     */
    private String modelProvider;

    /**
     * 用户反馈 (1=好评, 0=无, -1=差评)
     */
    private Short userFeedback;

    // === 3. 摘要与透视 (Summary & Insight) ===

    /**
     * 用户意图 (意图识别节点提供)
     */
    private String userIntent;

    /**
     * 用户本次请求的提问 (前500字符截断)
     */
    private String userTraceQuery;

    /**
     * AI 本次回复的内容 (前500字符截断)
     */
    private String aiTraceResponse;

    /**
     * 经过的节点 agent_name 列表 (JSONB)
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> executionPath;

    /**
     * 本次使用的工具 tool_name 列表 (JSONB)
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> toolsUsed;

    // === 4. 状态与合规 (Status & Compliance) ===

    /**
     * 执行状态: SUCCESS, FAILED, RUNNING, INTERRUPTED
     */
    private String status;

    /**
     * 简短的失败原因 (长堆栈存 ES)
     */
    private String failureReason;

    // === 5. 效能账本 (Metrics) ===

    /**
     * trace 总耗时 (毫秒)
     */
    private Integer traceLatencyMs;

    /**
     * trace 总 Token 消耗
     */
    private Integer traceTotalTokens;

    /**
     * trace 提示词 Token
     */
    private Integer traceInputTokens;

    /**
     * trace 输出 Token
     */
    private Integer traceOutputTokens;

    // === 6. 时序 (Timing) ===

    /**
     * 创建时间
     */
    @Column(onInsertValue = "now()")
    private OffsetDateTime createTime;

    /**
     * 更新时间
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private OffsetDateTime updateTime;
}
