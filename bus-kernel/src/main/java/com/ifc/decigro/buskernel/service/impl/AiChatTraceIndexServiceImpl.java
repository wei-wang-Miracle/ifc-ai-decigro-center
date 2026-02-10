package com.ifc.decigro.buskernel.service.impl;

import co.elastic.clients.elasticsearch.ElasticsearchClient;
import co.elastic.clients.elasticsearch.core.GetResponse;
import co.elastic.clients.elasticsearch.core.IndexResponse;
import com.ifc.decigro.buskernel.entity.AiChatTraceIndex;
import com.ifc.decigro.buskernel.mapper.AiChatTraceIndexMapper;
import com.ifc.decigro.buskernel.service.AiChatTraceIndexService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;

import static com.ifc.decigro.buskernel.entity.table.AiChatTraceIndexTableDef.AI_CHAT_TRACE_INDEX;

/**
 * AI 全链路审计 Service 实现类
 * 功能: PG 分页查询 + ES 详情读写
 */
@Service
public class AiChatTraceIndexServiceImpl implements AiChatTraceIndexService {

    /**
     * ES 索引名称（与 init_es_mapping.sh 脚本中一致）
     */
    private static final String ES_INDEX = "ai_chat_trace_index_snapshot";

    @Autowired
    private AiChatTraceIndexMapper traceIndexMapper;

    @Autowired
    private ElasticsearchClient esClient;

    /**
     * 分页查询审计列表 (数据源: PostgreSQL)
     * 支持多维度筛选，利用 PG 索引加速
     */
    @Override
    public Page<AiChatTraceIndex> pageQuery(
            String traceId, String taskId, String userId, String agentName,
            String status, String toolName, Short userFeedback,
            String startTime, String endTime,
            int page, int size) {

        // 第一步：构建查询条件
        QueryWrapper queryWrapper = QueryWrapper.create();

        // Trace ID 精确匹配
        if (StringUtils.hasText(traceId)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.TRACE_ID.eq(traceId));
        }

        // Task ID 精确匹配
        if (StringUtils.hasText(taskId)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.TASK_ID.eq(taskId));
        }

        // 用户 ID 精确匹配
        if (StringUtils.hasText(userId)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.USER_ID.eq(userId));
        }

        // Agent 名称精确匹配
        if (StringUtils.hasText(agentName)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.AGENT_NAME.eq(agentName));
        }

        // 状态精确匹配
        if (StringUtils.hasText(status)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.STATUS.eq(status));
        }

        // 工具名包含查询，利用 JSONB GIN 索引
        if (StringUtils.hasText(toolName)) {
            queryWrapper.and("tools_used @> '[\"" + toolName + "\"]'::jsonb");
        }

        // 用户反馈精确匹配
        if (userFeedback != null) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.USER_FEEDBACK.eq(userFeedback));
        }

        // 时间范围查询
        if (StringUtils.hasText(startTime)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.CREATE_TIME.ge(startTime));
        }
        if (StringUtils.hasText(endTime)) {
            queryWrapper.and(AI_CHAT_TRACE_INDEX.CREATE_TIME.le(endTime));
        }

        // 第二步：按创建时间倒序
        queryWrapper.orderBy(AI_CHAT_TRACE_INDEX.CREATE_TIME.desc());

        // 第三步：执行分页查询
        return traceIndexMapper.paginate(Page.of(page, size), queryWrapper);
    }

    /**
     * 保存审计数据：同时写入 PG 宽表 + ES 快照
     */
    @Override
    public void saveTrace(AiChatTraceIndex traceIndex, Map<String, Object> esSnapshot) {
        // 第一步：写入 PG 宽表
        AiChatTraceIndex existing = traceIndexMapper.selectOneById(traceIndex.getTraceId());
        if (existing == null) {
            traceIndexMapper.insert(traceIndex);
        } else {
            // 同一个 trace_id 可能因为重试/更新而再次写入
            traceIndexMapper.update(traceIndex);
        }

        // 第二步：写入 ES 快照（以 trace_id 作为文档 _id，天然去重）
        if (esSnapshot != null && !esSnapshot.isEmpty()) {
            try {
                IndexResponse response = esClient.index(i -> i
                        .index(ES_INDEX)
                        .id(traceIndex.getTraceId())
                        .document(esSnapshot));
                System.out.println("[Audit] ES 写入成功: " + response.result());
            } catch (Exception e) {
                // ES 写入失败不应影响主流程，仅记录日志
                System.err.println("[Audit] ES 写入失败: " + e.getMessage());
                e.printStackTrace();
            }
        }
    }

    /**
     * 从 ES 获取完整的审计详情
     */
    @Override
    @SuppressWarnings("unchecked")
    public Map<String, Object> getDetailFromEs(String traceId) {
        try {
            GetResponse<Map> response = esClient.get(g -> g
                    .index(ES_INDEX)
                    .id(traceId),
                    Map.class);

            if (response.found()) {
                return response.source();
            }
            return null;
        } catch (Exception e) {
            System.err.println("[Audit] ES 查询失败: " + e.getMessage());
            return null;
        }
    }

    /**
     * 按 task_id 查询同一任务下所有 trace 记录
     * 按创建时间正序排列，便于重建执行链路
     */
    @Override
    public List<AiChatTraceIndex> listByTaskId(String taskId) {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .where(AI_CHAT_TRACE_INDEX.TASK_ID.eq(taskId))
                .orderBy(AI_CHAT_TRACE_INDEX.CREATE_TIME.asc());
        return traceIndexMapper.selectListByQuery(queryWrapper);
    }
}
