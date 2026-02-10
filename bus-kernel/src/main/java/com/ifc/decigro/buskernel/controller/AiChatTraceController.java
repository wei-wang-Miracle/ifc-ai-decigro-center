package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.AiChatTraceIndex;
import com.ifc.decigro.buskernel.service.AiChatTraceIndexService;
import com.mybatisflex.core.paginate.Page;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * AI 全链路审计监控控制器
 * 功能: 提供审计列表查询 (PG) 和详情查询 (ES) API
 */
@RestController
@RequestMapping("/trace")
@Tag(name = "审计监控", description = "AI 全链路审计追踪 API")
public class AiChatTraceController {

    @Autowired
    private AiChatTraceIndexService traceIndexService;

    /**
     * 分页查询审计列表 (数据源: PostgreSQL)
     * 支持多维度筛选组合
     */
    @GetMapping("/page")
    @Operation(summary = "审计列表分页查询", description = "使用 PG 索引进行多维度筛选，响应 < 500ms")
    public Result<Page<AiChatTraceIndex>> page(
            @Parameter(description = "Trace ID (精确匹配)") @RequestParam(required = false) String traceId,
            @Parameter(description = "用户 ID (精确匹配)") @RequestParam(required = false) String userId,
            @Parameter(description = "Agent 名称") @RequestParam(required = false) String agentName,
            @Parameter(description = "执行状态: SUCCESS/FAILED/RUNNING") @RequestParam(required = false) String status,
            @Parameter(description = "包含的工具名") @RequestParam(required = false) String toolName,
            @Parameter(description = "用户反馈: 1(好评)/-1(差评)/0(无)") @RequestParam(required = false) Short userFeedback,
            @Parameter(description = "开始时间 (ISO 格式)") @RequestParam(required = false) String startTime,
            @Parameter(description = "结束时间 (ISO 格式)") @RequestParam(required = false) String endTime,
            @Parameter(description = "页码") @RequestParam(defaultValue = "1") int page,
            @Parameter(description = "每页条数") @RequestParam(defaultValue = "20") int size) {

        return Result.success(traceIndexService.pageQuery(
                traceId, userId, agentName, status, toolName,
                userFeedback, startTime, endTime, page, size));
    }

    /**
     * 获取审计详情 (数据源: Elasticsearch)
     * 返回完整的对话 Payload 和执行堆栈
     */
    @GetMapping("/detail/{traceId}")
    @Operation(summary = "审计详情查询", description = "通过 trace_id 从 ES 获取完整 Payload，响应 < 1s")
    public Result<Map<String, Object>> detail(
            @Parameter(description = "Trace ID") @PathVariable String traceId) {

        Map<String, Object> detail = traceIndexService.getDetailFromEs(traceId);
        if (detail == null) {
            return Result.fail(404, "未找到该 Trace 的详情记录");
        }
        return Result.success(detail);
    }

    /**
     * 保存审计数据 (供 AI 引擎调用)
     * 同时写入 PG 宽表 + ES 快照
     */
    @PostMapping("/save")
    @Operation(summary = "保存审计数据", description = "AI 引擎在工作流结束时调用，同时写入 PG + ES")
    public Result<Void> save(@RequestBody TraceWriteRequest request) {
        traceIndexService.saveTrace(request.getTraceIndex(), request.getEsSnapshot());
        return Result.success();
    }

    /**
     * 审计数据写入请求体
     * 包含 PG 宽表数据和 ES 快照数据
     */
    @lombok.Data
    public static class TraceWriteRequest {
        /**
         * PG 宽表数据
         */
        private AiChatTraceIndex traceIndex;

        /**
         * ES 完整快照数据 (JSON Map)
         */
        private Map<String, Object> esSnapshot;
    }
}
