package com.ifc.decigro.buskernel.controller;

import com.alibaba.fastjson2.JSONObject;
import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.common.api.Result;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 通用 StarRocks 查询工具控制器
 * 功能: 提供基于 StarRocks 的业务数据查询接口，面向 AI Agent 工具调用设计。
 */
@Slf4j
@RestController
@RequestMapping("/tool/starrocks")
@Tag(name = "StarRocks 业务工具库", description = "提供各类基于 StarRocks 宽表的客户数据查询")
public class GenericStarRocksController {

    private static final int DEFAULT_LIMIT = 100;
    private static final int MAX_LIMIT = 1000;

    private final JdbcTemplate starRocksJdbcTemplate;

    public GenericStarRocksController(@Qualifier("starRocksJdbcTemplate") JdbcTemplate starRocksJdbcTemplate) {
        this.starRocksJdbcTemplate = starRocksJdbcTemplate;
    }

    /**
     * 接口：查询客群数据详情
     * 客群是指满足某一类标签筛选条件的客户群体
     *
     * @param request 包含 sql 和 limit 的请求体
     * @return 客群数据列表
     */
    @PostMapping("/customer-group-detail")
    @ToolCard(
            tool_name = "query_customer_group_detail",
            summary = "查询客群数据详情",
            alias = "查询客群数据详情",
            description = "Trigger: 当需要查询满足特定标签筛选条件的客户群体（客群）的详细数据时使用，例如查询高净值客户、特定风险偏好客户或持有某类产品的客户群体。Action: 根据传入的 SQL 语句在 StarRocks 宽表 dm.sr_wide_client 中执行查询，返回符合条件的客群数据列表，支持通过 limit 控制返回数量。Constraint: SQL 必须是合法的 SELECT 查询语句且只能查询 dm.sr_wide_client 表；limit 范围为 1~1000，默认 100；禁止执行 DDL 或 DML 操作。",
            tags = {"customer_group", "starrocks_query", "label_filter", "client_data"},
            privileges = "public",
            input_examples = "{\"sql\": \"SELECT * FROM dm.sr_wide_client WHERE risk_level = '高风险'\", \"limit\": 50}",
            output_examples = "[{\"client_id\": \"C001\", \"client_name\": \"张三\", \"risk_level\": \"高风险\", \"asset_total\": 1500000.00}]"
    )
    public Result<List<JSONObject>> queryCustomerGroupDetail(
            @Parameter(description = "请求体，包含 sql（查询语句）和 limit（返回条数，默认100，最大1000）")
            @RequestBody JSONObject request) {

        if (request == null || !request.containsKey("sql")) {
            return Result.fail(400, "参数校验失败: 请求体不能缺少 'sql' 参数。请使用类似 {\"sql\": \"SELECT * FROM dm.sr_wide_client WHERE ...\", \"limit\": 100} 的 JSON 结构调用。");
        }

        String sql = request.getString("sql");
        if (sql == null || sql.isBlank()) {
            return Result.fail(400, "参数校验失败: 'sql' 不能为空。");
        }

        // 安全校验：只允许 SELECT 语句
        String trimmedSql = sql.trim().toLowerCase();
        if (!trimmedSql.startsWith("select")) {
            return Result.fail(400, "参数校验失败: 仅支持 SELECT 查询语句，不允许执行 DDL 或 DML 操作。");
        }

        // 校验必须查询指定表
        if (!trimmedSql.contains("dm.sr_wide_client")) {
            return Result.fail(400, "参数校验失败: SQL 必须包含目标表 dm.sr_wide_client。");
        }

        int limit = DEFAULT_LIMIT;
        if (request.containsKey("limit")) {
            limit = request.getIntValue("limit");
            if (limit <= 0 || limit > MAX_LIMIT) {
                return Result.fail(400, "参数校验失败: 'limit' 必须在 1 到 " + MAX_LIMIT + " 之间，当前值为: " + limit + "。");
            }
        }

        // 拼接 LIMIT 子句（防止 SQL 中已有 limit 时重复添加）
        String finalSql = trimmedSql.contains(" limit ") ? sql : sql + " LIMIT " + limit;

        try {
            List<Map<String, Object>> rows = starRocksJdbcTemplate.queryForList(finalSql);
            List<JSONObject> result = rows.stream()
                    .map(row -> new JSONObject(row))
                    .collect(Collectors.toList());
            log.debug("StarRocks 客群查询完成，返回 {} 条记录，SQL: {}", result.size(), finalSql);
            return Result.success(result);
        } catch (Exception e) {
            log.error("StarRocks 客群查询异常，SQL: {}", finalSql, e);
            return Result.fail("查询失败: " + e.getMessage());
        }
    }
}
