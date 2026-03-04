package com.ifc.decigro.buskernel.dto;

import com.alibaba.fastjson2.JSONObject;
import com.ifc.decigro.buskernel.common.annotation.ToolOutput;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.util.List;

/**
 * 知识库语义检索响应 DTO
 *
 * 功能: 封装 search_knowledge_base 工具的出参结构。
 * 适配外部知识库 API 返回，包含语义检索结果列表。
 *
 * 设计说明: 外层由 Result<KnowledgeSearchResult> 包裹，
 * data 字段为 KnowledgeSearchResult 对象。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class KnowledgeSearchResult {
    /**
     * 检索结果列表（按相关度降序排列）
     */
    @ToolOutput(param_name = "list", param_type = "array",
            param_description = "检索命中的文档片段列表，按相关度降序排列。若列表为空，说明知识库中暂无匹配内容，请换用更具体的查询词或切换 HYBRID_SEARCH 模式重试。",
            param_required = true)
    private List<JSONObject> list;
}
