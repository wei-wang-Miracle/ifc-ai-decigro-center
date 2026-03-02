package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolOutput;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.util.List;

/**
 * 知识库语义检索响应 DTO
 *
 * 功能: 封装 search_knowledge_base 工具的出参结构。
 * 字段均标注了 @ToolOutput，帮助 AI Agent 准确解析和引用返回内容。
 *
 * 设计说明: 外层由 Result<KnowledgeSearchResponse> 包裹，
 * data 字段为 KnowledgeSearchResponse 对象。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class KnowledgeSearchResult {

    /**
     * 单条检索结果，对应 ai-rag 返回的 SearchResult
     */
    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Item {

        @ToolOutput(param_name = "content", param_type = "string", param_description = "检索命中的文档原文片段（已扩展上下文，可直接引用作为答案依据）。", param_example = "沪深300指数增强策略通过多因子模型控制跟踪误差...")
        private String content;

        @ToolOutput(param_name = "doc_id", param_type = "string", param_description = "来源文档的唯一ID，可用于进一步查询文档详情或溯源。", param_example = "d3f8a1b2-4c3d-11ef-9d2b-0242ac120002")
        private String docId;

        @ToolOutput(param_name = "doc_name", param_type = "string", param_description = "来源文档的原始文件名，用于向用户标注引用出处。", param_example = "2024年一季度量化研报.pdf")
        private String docName;

        @ToolOutput(param_name = "doc_type", param_type = "string", param_description = "文档分类标签，与入参 doc_type 对应。", param_example = "研报")
        private String docType;

        @ToolOutput(param_name = "score", param_type = "number", param_description = "相关性得分（越高越相关）。结果已按得分排序，优先使用排名靠前的内容。", param_example = "0.95")
        private double score;

        @ToolOutput(param_name = "chunk_count", param_type = "integer", param_description = "本条结果包含的切块数量（上下文扩展后拼合的 Chunk 数）。值 > 1 表示已自动补充了上下文。", param_example = "3")
        private int chunkCount;
    }

    /**
     * 检索到的文档片段列表（按相关度降序，已完成 FlashRank 重排序）
     */
    @ToolOutput(param_name = "items", param_type = "array", param_description = "命中的文档片段列表，按相关度降序排列。" +
            "若列表为空，表示知识库中暂无与 query 匹配的内容，请调整查询词后重试。", param_required = true)
    private List<Item> items;

    /**
     * 实际返回结果数量
     */
    @ToolOutput(param_name = "total", param_type = "integer", param_description = "本次检索实际返回的结果数量，等于 items.size()。若为 0 则表示未命中。", param_example = "5")
    private int total;
}
