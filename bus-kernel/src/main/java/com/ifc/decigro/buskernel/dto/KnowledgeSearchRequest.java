package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import jakarta.validation.constraints.*;
import lombok.Data;

import java.util.List;

/**
 * 知识库语义检索请求 DTO
 *
 * 功能: 封装 AI Agent 调用 search_knowledge_base 工具时的入参结构。
 * 字段均标注了 @ToolInput，帮助 Agent 生成准确的 JSON 参数。
 *
 * 使用场景: 由 KnowledgeController.search() 接收，代理转发至外部知识库检索 API。
 */
@Data
public class KnowledgeSearchRequest {

    /**
     * 语义查询词（必填）
     * 用于检索的用户问题，须为自然语言，不可为 SQL 或代码片段
     */
    @ToolInput(param_name = "query", param_type = "string", param_required = true,
            param_description = "用于检索的自然语言问题或关键语义描述，不可为 SQL、代码或单个词汇。",
            param_example = "华夏中证香港内地国有企业ETF 513120 的产品说明")
    @NotBlank(message = "[AI调用错误] query 为必填项，请提供自然语言语义描述，不可为空或纯空白字符。")
    @Size(min = 2, max = 500, message = "[AI调用错误] query 长度须在 2~500 个字符之间，当前长度不合法。")
    private String query;

    /**
     * 返回记录数（选填，默认 5）
     * 建议优先使用较小的 k 值（如 3~5），相关度更高
     */
    @ToolInput(param_name = "k", param_type = "integer", param_required = false,
            param_description = "返回的结果条数，默认为 5，建议范围 1~10。值越小结果精度越高，值越大覆盖面越广。",
            param_example = "5")
    @Min(value = 1, message = "[AI调用错误] k 最小值为 1，请勿传入 0 或负数。")
    @Max(value = 50, message = "[AI调用错误] k 最大值为 50，请调整为合理范围。")
    private Integer k = 5;

    /**
     * 检索模式（选填）
     * VECTOR_SEARCH: 纯语义向量检索（默认，适合模糊问题）
     * HYBRID_SEARCH: 增强检索（向量+BM25关键词，适合含专有名词或代码的查询）
     */
    @ToolInput(param_name = "search_mode", param_type = "string", param_required = false,
            param_description = "检索模式：VECTOR_SEARCH（纯语义检索，默认）或 HYBRID_SEARCH（向量+关键词增强检索，适合含基金代码、专有名词等精确词汇的查询）。",
            param_example = "HYBRID_SEARCH")
    private String searchMode;
}
