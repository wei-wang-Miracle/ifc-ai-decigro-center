package com.ifc.decigro.buskernel.controller;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.dto.CustomerGroupDetailRequest;
import com.ifc.decigro.buskernel.dto.LabelGroupCountRequest;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

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

    private static final String NL2SQL_URL = "https://chatbi.cnht.com.cn/api/v1/chat/completions";
    private static final String NL2SQL_AUTH = "Bearer chatbi_70485dbbdc1d91e697a476e6aca27c6e";
    private static final String NL2SQL_MODEL = "wide_client";

    private final JdbcTemplate starRocksJdbcTemplate;
    private final RestTemplate restTemplate;

    public GenericStarRocksController(@Qualifier("starRocksJdbcTemplate") JdbcTemplate starRocksJdbcTemplate) {
        this.starRocksJdbcTemplate = starRocksJdbcTemplate;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(360_000); // NL2SQL 接口耗时可达 120s+，设 180s 留余量
        this.restTemplate = new RestTemplate(factory);
    }

    /**
     * 接口：查询客群数据详情
     * 客群是指满足某一类标签筛选条件的客户群体
     *
     * @param request 包含 sql 和 limit 的请求体（使用 DTO 以驱动 @ToolInput Schema 自动注册）
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
            @RequestBody CustomerGroupDetailRequest request) {

        if (request == null || request.getSql() == null || request.getSql().isBlank()) {
            return Result.fail(400, "参数校验失败: 'sql' 不能为空。");
        }

        String sql = request.getSql();

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
        if (request.getLimit() != null) {
            limit = request.getLimit();
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

    /**
     * 接口：根据自然语言查询标签分组数量
     * 流程：自然语言 → NL2SQL 服务 → 提取 SQL → StarRocks 执行 → 返回条数
     *
     * @param request 包含用户自然语言问题的请求体
     * @return 查询结果条数
     */
    @PostMapping("/label-group-count")
    @ToolCard(
            tool_name = "query_label_group_count",
            summary = "查询标签分组条件的预估客户人数",
            alias = "标签人群预估数量查询",
            description = "Trigger: 当需要预估某组标签筛选条件覆盖的客户人数时使用，例如规划一批客群策略前需要了解目标人群规模。典型场景：用户描述一组标签组合条件（如风险等级、资产规模、持仓产品类型等），需要知道满足该条件的客户有多少人。Action: 将自然语言描述的标签筛选条件发送给 NL2SQL 服务自动转换为 SQL，在 StarRocks 宽表中执行 COUNT 查询，返回预估客户人数及对应 SQL。Constraint: 仅用于人数预估统计，不返回客户明细；问题应描述具体的标签筛选条件；NL2SQL 服务不可用时返回错误。",
            tags = {"label_group", "count", "nl2sql", "audience_estimate", "starrocks_query"},
            input_examples = "{\"question\": \"风险等级(corp_risk_level)大于C4且资产(asset_td)大于5万的客户数量\"}",
            output_examples = "{\"count\": 1280, \"sql\": \"SELECT COUNT(1) FROM tag_acc_base_wide_client a INNER JOIN tag_ast_wide_client b ON a.client_id = b.client_id WHERE a.corp_risk_level IN (4,9) AND b.asset_td > 50000\"}"
    )
    public Result<JSONObject> queryLabelGroupCount(
            @Parameter(description = "请求体，包含 question（用户自然语言查询问题）")
            @RequestBody LabelGroupCountRequest request) {

        if (request == null || request.getQuestion() == null || request.getQuestion().isBlank()) {
            return Result.fail(400, "参数校验失败: 'question' 不能为空。");
        }

        log.info("[queryLabelGroupCount] 收到请求，question: {}", request.getQuestion());

        // Step 1: 调用 NL2SQL 服务，将自然语言转换为 SQL
        String sql;
        try {
            log.info("[queryLabelGroupCount] Step1 开始调用 NL2SQL 服务，URL: {}", NL2SQL_URL);
            sql = callNl2SqlService(request.getQuestion());
        } catch (Exception e) {
            log.error("[queryLabelGroupCount] Step1 NL2SQL 服务调用异常，question: {}", request.getQuestion(), e);
            return Result.fail("NL2SQL 服务调用失败: " + e.getMessage());
        }

        if (sql == null || sql.isBlank()) {
            log.warn("[queryLabelGroupCount] Step1 NL2SQL 服务返回空 SQL，question: {}", request.getQuestion());
            return Result.fail("NL2SQL 服务未返回有效的 SQL 语句。");
        }

        log.info("[queryLabelGroupCount] Step1 NL2SQL 转换成功，question: {}，sql: {}", request.getQuestion(), sql);

        // Step 2: 安全校验，只允许 SELECT
        String trimmedSql = sql.trim().toLowerCase();
        if (!trimmedSql.startsWith("select")) {
            log.warn("[queryLabelGroupCount] Step2 SQL 安全校验失败，非 SELECT 语句，sql: {}", sql);
            return Result.fail(400, "SQL 安全校验失败: NL2SQL 返回的不是 SELECT 语句。");
        }
        log.info("[queryLabelGroupCount] Step2 SQL 安全校验通过");

        // Step 3: 执行 SQL，统计返回条数
        log.info("[queryLabelGroupCount] Step3 开始执行 StarRocks 查询，sql: {}", sql);
        try {
            List<Map<String, Object>> rows = starRocksJdbcTemplate.queryForList(sql);
            JSONObject result = new JSONObject();

            // 判断 SQL 是否为聚合查询（COUNT/SUM 等），若是则直接读取聚合值，否则返回行数
            String lowerSql = sql.trim().toLowerCase();
            boolean isAggQuery = lowerSql.startsWith("select count") || lowerSql.startsWith("select sum")
                    || lowerSql.startsWith("select avg") || lowerSql.startsWith("select max")
                    || lowerSql.startsWith("select min");

            if (isAggQuery && !rows.isEmpty()) {
                // 取第一行第一列的值作为聚合结果
                Object aggValue = rows.get(0).values().iterator().next();
                result.put("count", aggValue);
                log.info("[queryLabelGroupCount] Step3 聚合查询完成，aggValue: {}，SQL: {}", aggValue, sql);
            } else {
                result.put("count", rows.size());
                log.info("[queryLabelGroupCount] Step3 列表查询完成，count: {}，SQL: {}", rows.size(), sql);
            }

            result.put("sql", sql);
            return Result.success(result);
        } catch (Exception e) {
            log.error("[queryLabelGroupCount] Step3 StarRocks 查询异常，SQL: {}", sql, e);
            return Result.fail("查询失败: " + e.getMessage());
        }
    }

    /**
     * 调用 NL2SQL 服务，将自然语言转换为 SQL
     */
    private String callNl2SqlService(String question) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set(HttpHeaders.AUTHORIZATION, NL2SQL_AUTH);

        JSONObject body = new JSONObject();
        body.put("model", NL2SQL_MODEL);
        body.put("messages", new Object[]{
                JSON.parseObject("{\"role\":\"user\",\"content\":\"" + question.replace("\"", "\\\"") + "\"}")
        });
        body.put("stream", false);
        body.put("cache_enabled", true);
        body.put("question_rewrite_enabled", true);
        body.put("gen_graph", false);
        body.put("memory_rounds", 1);
        body.put("sql_explain_enabled", false);
        body.put("sql_validation_enabled", false);

        log.info("[callNl2SqlService] 发送请求，body: {}", body.toJSONString());
        HttpEntity<String> entity = new HttpEntity<>(body.toJSONString(), headers);
        ResponseEntity<String> response = restTemplate.exchange(NL2SQL_URL, HttpMethod.POST, entity, String.class);

        log.info("[callNl2SqlService] 收到响应，状态码: {}", response.getStatusCode());
        log.debug("[callNl2SqlService] 响应体: {}", response.getBody());

        if (!response.getStatusCode().is2xxSuccessful() || response.getBody() == null) {
            log.error("[callNl2SqlService] NL2SQL 服务返回异常，状态码: {}，body: {}", response.getStatusCode(), response.getBody());
            throw new RuntimeException("NL2SQL 服务返回异常，状态码: " + response.getStatusCode());
        }

        JSONObject responseBody = JSON.parseObject(response.getBody());
        // 提取 choices[0].message.content 中的 SQL 字段
        String content = responseBody
                .getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .getString("content");

        log.info("[callNl2SqlService] 原始 content: {}", content);

        // content 可能是 Markdown 代码块格式（```sql\n...\n```），也可能是 JSON 格式（{"SQL": "..."}）
        String extractedSql;
        String trimmedContent = content.trim();
        if (trimmedContent.startsWith("```")) {
            // 去除 Markdown 代码块包装，提取纯 SQL
            extractedSql = trimmedContent
                    .replaceAll("(?s)^```[a-zA-Z]*\\n?", "")  // 去除开头的 ```sql 或 ```
                    .replaceAll("(?s)\\n?```[\\s\\S]*$", "")  // 去除结尾的 ``` 及其后内容（如 <question> 标签）
                    .trim();
        } else {
            JSONObject contentJson = JSON.parseObject(trimmedContent);
            extractedSql = contentJson.getString("SQL");
        }
        log.info("[callNl2SqlService] 提取到 SQL: {}", extractedSql);
        return extractedSql;
    }
}
