package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.dto.KnowledgeSearchRequest;
import com.ifc.decigro.buskernel.service.KnowledgeProxyService;

import java.util.List;
import java.util.Map;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

/**
 * 知识库检索控制器
 *
 * 仅提供知识库语义检索功能（search_knowledge_base）供 AI 引擎调用
 */
@RestController
@RequestMapping("/knowledge")
@Tag(name = "知识库管理", description = "RAG 知识库检索 API")
public class KnowledgeController {

    @Autowired
    private KnowledgeProxyService knowledgeProxyService;

    /**
     * 知识库检索接口（供 ai-engine ToolCard 调用）
     *
     * 预校验说明：
     * - query 为必填项，长度 2~500 字符，必须是自然语言，空值会直接返回错误
     * - k 范围 1~50，省略默认 5
     * - search_mode 可省略，默认 VECTOR_SEARCH；含专有名词时推荐 HYBRID_SEARCH
     *
     * 返回结果说明：
     * - data 为命中片段数组，已按 similarity 降序排列
     * - 每条记录的 text 字段为 Markdown 格式原文，可直接引用
     * - similarity < 0.5 时相关度较低，回答时应说明不确定性
     *
     * 调用失败时，message 字段会包含具体的改正提示，AI 可据此自动修正参数后重试。
     */
    @PostMapping("/search")
    @ToolCard(
            tool_name = "search_knowledge_base",
            summary = "知识库语义检索",
            alias = "知识库语义检索",
            description = "[Action] 对内部知识库执行语义检索，返回与查询语义最相关的文档原始片段（RAW 格式，Markdown 原文）。" +
                    "[Trigger] 当用户提问涉及内部产品资料、基金说明书、ETF特征数据、考核指标、技术文档等专业内容，" +
                    "且需要从知识库中获取事实依据时调用。" +
                    "典型场景：用户询问某基金产品说明书、ETF数据字段含义、内部考核规则等。" +
                    "[Constraint] " +
                    "1. query 必须是自然语言语义描述（2~500字符），不得传入 SQL 或代码片段。" +
                    "2. 若查询词包含基金代码（如 513120）、产品简称等精确词汇，建议使用 search_mode=HYBRID_SEARCH 以提升召回率。" +
                    "3. k 默认 5，范围 1~50；值越小精度越高，值越大覆盖面越广，一般无需超过 10。" +
                    "4. 返回 data 数组已按相关度降序排列，优先引用 no=1 的片段 text 字段作为知识依据。" +
                    "5. 若 similarity < 0.5，命中片段与查询相关度较低，应在回答中说明不确定性或建议扩大 k 值重试。" +
                    "[ErrorHandling] 若 code != 200，请仔细阅读 message 字段，其中包含具体的错误原因和修正建议，参考后调整参数重新调用。",
            tags = { "knowledge_base", "semantic_search", "rag_retrieval", "fund_document", "etf", "information_qa" },
            privileges = "protected",
            input_examples = "{\"query\": \"华夏中证香港内地国有企业ETF 513120 产品说明书\", \"k\": 5, \"search_mode\": \"HYBRID_SEARCH\"}",
            output_examples = "{\"code\": 200, \"message\": \"success\", \"data\": [{\"data_type\": \"RAW\", \"text\": \"## ETF特征完整数据字段清单\\n| 输出字段 | 类型 | 说明 |\\n|---|---|---|\\n| SHORT_TERM_RETURN_EXPECT | Float | 短期收益预期(%) |\", \"similarity\": 0.87, \"no\": 1, \"code\": \"El2TPMaI\", \"data_id\": \"s57StpwBdt2tq9rqj9k_\", \"file_id\": \"177259363533446378.md\"}]}"
    )
    public Result<List<Map<String, Object>>> search(
            @Validated @RequestBody KnowledgeSearchRequest request) {
        return knowledgeProxyService.search(request);
    }
}
