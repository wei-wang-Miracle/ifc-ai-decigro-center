package com.ifc.decigro.buskernel.controller;

import com.alibaba.fastjson2.JSONObject;
import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.dto.FundEtfFeaturesRequest;
import com.ifc.decigro.buskernel.service.GenericMongoService;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 通用 MongoDB 查询工具控制器
 * 功能: 提供具体的业务接口，内部通过策略模式分发至相应的 Service 实现。
 * 既保证了接口的清晰性（每个工具一个接口），又保证了 Service 层的可扩展性。
 */
@Slf4j
@RestController
@RequestMapping("/tool/mongo")
@Tag(name = "MongoDB 业务工具库", description = "提供各类基于 MongoDB 的行情与模型数据查询")
public class GenericMongoController {

    @Autowired
    private List<GenericMongoService> mongoServices;

    /**
     * 接口：查询单只场内基金的基金特征值
     * 业务标识: fund-etf-features
     */
    @PostMapping("/fund-etf-features")
    @ToolCard(tool_name = "query_fund_etf_features", summary = "查询单只场内基金（ETF）的量化特征数据", alias = "查询单只场内基金的基金特征值", description = "Trigger: 当需要分析具体ETF（如510050、510300）的量化特征因子或提取模型输入特征时使用。Action: 根据传入的6位基金代码拉取该基金的详细特征指标列表。Constraint: 必须提供精确匹配的合法的6位纯数字格式基金代码作为参数。", tags = {
            "fund_analysis", "quantitative_data", "etf_features",
            "mongo_query" }, privileges = "public", input_examples = "{\"fundCode\": \"510050\"}", output_examples = "[{\"FUND_CODE\": \"510050\", \"OVERALL_RETURN_EXPECT\": 0.125, \"OVERALL_RISK\": 0.182, \"OVERALL_RETURN_LEVEL\": \"OVERALL_RL3\", \"IS_BROAD_MARKET_ETF\": 1, \"FUND_STYLE_RR\": \"高收益高风险\", \"COMPREHENSIVE_SCORE\": 88.5}]")
    public Result<List<JSONObject>> queryFundEtfFeatures(@Valid @RequestBody FundEtfFeaturesRequest request) {
        Map<String, Object> params = new HashMap<>();
        params.put("fundCode", request.getFundCode());
        return dispatch("fund-etf-features", params);
    }

    /**
     * 内部调度方法
     * 根据 toolPath 路由到具体的 Service 实现
     */
    private Result<List<JSONObject>> dispatch(String toolPath, Map<String, Object> params) {
        GenericMongoService targetService = mongoServices.stream()
                .filter(service -> service.supports(toolPath))
                .findFirst()
                .orElse(null);

        if (targetService == null) {
            log.warn("未找到业务处理器: {}", toolPath);
            return Result.fail(404, "业务处理器未定义: " + toolPath);
        }

        try {
            List<JSONObject> results = targetService.executeQuery(params);
            return Result.success(results);
        } catch (IllegalArgumentException e) {
            return Result.fail(400, e.getMessage());
        } catch (Exception e) {
            log.error("MongoDB 查询异常 [{}]: ", toolPath, e);
            return Result.fail("查询失败: " + e.getMessage());
        }
    }
}
