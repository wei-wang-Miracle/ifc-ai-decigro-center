package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.dto.KnowledgeSearchRequest;
import com.ifc.decigro.buskernel.dto.KnowledgeSearchResult;
import com.ifc.decigro.buskernel.service.KnowledgeProxyService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

/**
 * 知识库管理代理控制器
 *
 * 功能: 作为 bus-kernel 统一入口，将前端和 ai-engine 的知识库请求
 * 反向代理到独立的 ai-rag Python 微服务。
 *
 * 设计理念 (方案B):
 * - bus-kernel 保持架构纯粹性，作为唯一的 API Gateway
 * - 繁重的 RAGLite 向量化和检索逻辑下沉到专属的 ai-rag 服务
 * - ai-rag 服务对外不暴露，只接受来自 bus-kernel 和 ai-engine 的调用
 */
@RestController
@RequestMapping("/knowledge")
@Tag(name = "知识库管理", description = "RAG 知识库文档管理 API（代理至 ai-rag 微服务）")
public class KnowledgeController {

    @Autowired
    private KnowledgeProxyService knowledgeProxyService;

    /**
     * 上传文档到知识库
     * 支持 PDF、Word、Markdown 等格式
     */
    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @Operation(summary = "上传文档", description = "上传文档到知识库，异步执行切块和向量化，立即返回")
    public Result<Object> uploadDocument(
            @Parameter(description = "文档文件") @RequestParam("file") MultipartFile file,
            @Parameter(description = "文档分类") @RequestParam("docType") String docType,
            @Parameter(description = "业务标签，逗号分隔") @RequestParam(value = "bizTags", required = false, defaultValue = "") String bizTags,
            @Parameter(description = "发布日期") @RequestParam(value = "publishDate", required = false) String publishDate) {
        return knowledgeProxyService.uploadDocument(file, docType, bizTags, publishDate);
    }

    /**
     * 分页查询知识库文档列表
     */
    @GetMapping("/list")
    @Operation(summary = "查询文档列表", description = "分页查询知识库文档，支持按分类和关键字筛选")
    public Result<Object> listDocuments(
            @Parameter(description = "文档分类筛选") @RequestParam(required = false) String docType,
            @Parameter(description = "关键字搜索") @RequestParam(required = false) String keyword,
            @Parameter(description = "页码") @RequestParam(defaultValue = "1") int page,
            @Parameter(description = "每页条数") @RequestParam(defaultValue = "20") int size) {
        return knowledgeProxyService.listDocuments(docType, keyword, page, size);
    }

    /**
     * 获取单个文档详情
     */
    @GetMapping("/{docId}")
    @Operation(summary = "获取文档详情")
    public Result<Object> getDocument(
            @Parameter(description = "文档ID") @PathVariable String docId) {
        return knowledgeProxyService.getDocument(docId);
    }

    /**
     * 删除文档（同时删除向量索引中的 Chunks）
     */
    @DeleteMapping("/{docId}")
    @Operation(summary = "删除文档", description = "删除文档记录及其所有向量 Chunk，不可恢复")
    public Result<Object> deleteDocument(
            @Parameter(description = "文档ID") @PathVariable String docId) {
        return knowledgeProxyService.deleteDocument(docId);
    }

    /**
     * 预览文档切块详情
     */
    @GetMapping("/{docId}/chunks")
    @Operation(summary = "预览文档切块", description = "查看文档被切分后的 Chunk 列表，用于验证切块质量")
    public Result<Object> getDocumentChunks(
            @Parameter(description = "文档ID") @PathVariable String docId) {
        return knowledgeProxyService.getDocumentChunks(docId);
    }

    /**
     * 人工修正指定 Chunk 文本并重新向量化
     */
    @PutMapping("/{docId}/chunks/{chunkId}")
    @Operation(summary = "修正 Chunk 内容", description = "修正 OCR 错误等问题，触发重新 Embedding")
    public Result<Object> updateChunk(
            @PathVariable String docId,
            @PathVariable String chunkId,
            @RequestParam String content) {
        return knowledgeProxyService.updateChunk(docId, chunkId, content);
    }

    /**
     * 重新处理文档（重新切块和向量化）
     */
    @PostMapping("/{docId}/reprocess")
    @Operation(summary = "重新处理文档", description = "触发文档重新切块和向量化，适用于处理失败后的重试")
    public Result<Object> reprocessDocument(
            @Parameter(description = "文档ID") @PathVariable String docId) {
        return knowledgeProxyService.reprocessDocument(docId);
    }

    /**
     * 知识库检索接口（供 ai-engine ToolCard 调用）
     *
     * 预校验说明：
     * - query 为必填项，长度 2~500 字符，必须是自然语言，空值会直接返回错误
     * - doc_type 可省略；若传入，最长 50 字符
     * - top_k 范围 1~10，省略默认 5
     *
     * 调用失败时，message 字段会包含具体的改正提示，AI 可据此自动修正参数后重试。
     */
    @PostMapping("/search")
    @ToolCard(tool_name = "search_knowledge_base", summary = "知识库语义检索", alias = "知识库语义检索", description = "[Action] 对内部知识库执行混合语义检索（向量相似度 + BM25 关键词），"
            +
            "返回与查询最相关的文档片段，并自动扩展上下文防止语义截断。" +
            "[Trigger] 当用户提问涉及专业知识、内部资料或产品文档，" +
            "且需要从知识库中获取事实依据时调用。" +
            "典型场景：用户询问某活动说明、考核指标、技术文档等。" +
            "[Constraint] " +
            "1. query 必须是自然语言语义描述（2~500字符），不得传入 SQL 或代码片段。" +
            "2. doc_type 仅接受已录入知识库的分类值（如考核文档、技术文档），可省略。" +
            "3. top_k 默认 5，范围 1~10，超出范围会被拒绝并告知错误原因。" +
            "4. 返回 data.items 列表已按相关度降序排列，直接取前 N 条引用即可。" +
            "[ErrorHandling] 若 code != 200，请仔细阅读 message 字段，" +
            "其中包含具体字段的错误原因 and 修正建议，参考后调整参数重新调用。", tags = { "knowledge_base", "semantic_search", "rag_retrieval",
                    "information_qa" }, privileges = "protected", input_examples = "{\"query\": \"年度考核指标的计算方法\", " +
                            "\"doc_type\": \"考核文档\", \"top_k\": 5}", output_examples = "{\"code\": 200, \"message\": \"操作成功\", "
                                    +
                                    "\"data\": {\"items\": [{\"content\": \"沪深300指数增强策略通过多因子模型...\", " +
                                    "\"doc_id\": \"d3f8a1b2-xxxx\", \"doc_name\": \"2024年一季度量化研报.pdf\", " +
                                    "\"doc_type\": \"研报\", \"score\": 0.95, \"chunk_count\": 3}], \"total\": 1}}")
    public Result<KnowledgeSearchResult> search(
            @Validated @RequestBody KnowledgeSearchRequest request) {
        return knowledgeProxyService.search(request);
    }
}
