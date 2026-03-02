package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import jakarta.validation.constraints.*;
import lombok.Data;

/**
 * 知识库语义检索请求 DTO
 *
 * 功能: 封装 AI Agent 调用 search_knowledge_base 工具时的入参结构。
 * 字段均标注了 @ToolInput，帮助 Agent 生成准确的 JSON 参数。
 *
 * 使用场景: 由 KnowledgeController.search() 接收，代理转发至 ai-rag 服务。
 */
@Data
public class KnowledgeSearchRequest {

    /**
     * 语义查询词（必填）
     * 必须是自然语言描述，不得为 SQL 或代码片段
     */
    @ToolInput(param_name = "query", param_type = "string", param_required = true, param_description = "语义查询词，必须是自然语言描述。"
            +
            "例如：'沪深300指数增强策略的风险控制方法'。" +
            "不得传入 SQL、JSON 代码或纯关键词列表。", param_example = "沪深300指数增强策略的风险控制方法")
    @NotBlank(message = "[AI调用错误] query 为必填项，请提供自然语言语义描述，不可为空或纯空白字符。")
    @Size(min = 2, max = 500, message = "[AI调用错误] query 长度须在 2~500 个字符之间，当前长度不合法。")
    private String query;

    /**
     * 文档分类过滤（选填）
     * 仅接受已录入知识库的分类值
     */
    @ToolInput(param_name = "doc_type", param_type = "string", param_required = false, param_description = "文档分类过滤，仅接受知识库中已存在的分类值（如'研报'、'规则文档'、'产品说明书'）。"
            +
            "若传入未知分类，检索结果将为空。省略则不限制分类。", param_example = "研报")
    @Size(max = 50, message = "[AI调用错误] doc_type 长度不得超过 50 个字符。")
    private String docType;

    /**
     * 精确匹配业务代码（选填）
     * 用于精确过滤关联了特定基金代码的文档
     */
    @ToolInput(param_name = "must_match_code", param_type = "string", param_required = false, param_description = "精确匹配关联的业务代码（如基金代码 '000001'）。"
            +
            "须为完整代码，不支持模糊匹配。省略则不限制业务代码。", param_example = "000001")
    @Pattern(regexp = "^[a-zA-Z0-9]{4,10}$", message = "[AI调用错误] must_match_code 须为 4~10 位字母或数字的完整代码（如 '000001'），不支持模糊或正则。")
    private String mustMatchCode;

    /**
     * 返回结果数量上限（选填，默认 5）
     */
    @ToolInput(param_name = "top_k", param_type = "integer", param_required = false, param_description = "返回最相关的文档片段数量，默认 5，最大 10。"
            +
            "超过 10 会显著增加响应延迟，不建议设置过大。", param_example = "5")
    @Min(value = 1, message = "[AI调用错误] top_k 最小值为 1，请勿传入 0 或负数。")
    @Max(value = 10, message = "[AI调用错误] top_k 最大值为 10，传入过大的值会导致响应超时，请调整为 10 以内。")
    private Integer topK = 5;
}
