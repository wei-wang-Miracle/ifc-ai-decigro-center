package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.AiChatTraceIndex;
import com.mybatisflex.core.paginate.Page;

import java.util.List;
import java.util.Map;

/**
 * AI 全链路审计 Service 接口
 * 功能: 提供 PG 分页查询 + ES 详情读写能力
 */
public interface AiChatTraceIndexService {

    /**
     * 分页查询审计列表 (数据源: PostgreSQL)
     *
     * 参数:
     * - traceId: Trace ID (精确匹配, 可选)
     * - userId: 用户 ID (精确匹配, 可选)
     * - agentName: Agent 名称 (精确匹配, 可选)
     * - status: 执行状态 (精确匹配, 可选)
     * - toolName: 包含的工具名 (JSONB 包含查询, 可选)
     * - userFeedback: 用户反馈 (精确匹配, 可选)
     * - startTime: 开始时间 (可选)
     * - endTime: 结束时间 (可选)
     * - page: 页码
     * - size: 每页条数
     *
     * 返回: 分页结果
     */
    Page<AiChatTraceIndex> pageQuery(
            String traceId,
            String taskId,
            String userId,
            String agentName,
            String status,
            String toolName,
            Short userFeedback,
            String startTime,
            String endTime,
            int page,
            int size);

    /**
     * 保存审计数据 (同时写入 PG + ES)
     *
     * 参数:
     * - traceIndex: PG 宽表数据
     * - esSnapshot: ES 完整快照数据 (JSON Map)
     */
    void saveTrace(AiChatTraceIndex traceIndex, Map<String, Object> esSnapshot);

    /**
     * 从 ES 获取完整的审计详情
     *
     * 参数: traceId - 链路追踪 ID
     * 返回: ES 文档内容 (JSON Map)，不存在则返回 null
     */
    Map<String, Object> getDetailFromEs(String traceId);

    /**
     * 按 task_id 查询同一任务下所有 trace 记录
     *
     * 参数: taskId - 任务 ID
     * 返回: 该 task_id 下所有 trace 列表，按创建时间正序
     */
    List<AiChatTraceIndex> listByTaskId(String taskId);
}
