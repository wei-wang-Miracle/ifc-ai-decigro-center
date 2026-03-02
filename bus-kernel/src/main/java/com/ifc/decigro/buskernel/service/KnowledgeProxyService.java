package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.dto.KnowledgeSearchRequest;
import com.ifc.decigro.buskernel.dto.KnowledgeSearchResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 知识库代理服务
 *
 * 功能: 通过 HTTP 将知识库相关请求转发到 ai-rag Python 微服务。
 * 封装了所有与 ai-rag 服务的通信细节，包括错误处理和响应转换。
 *
 * 参数: ai-rag 服务地址从配置文件 application.yml 读取
 * 返回: 统一封装为 bus-kernel 的 Result<T> 格式
 */
@Slf4j
@Service
public class KnowledgeProxyService {

    @Value("${ai.rag.base-url:http://localhost:8002/api/rag}")
    private String aiRagBaseUrl;

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 上传文档到 ai-rag 微服务
     */
    public Result<Object> uploadDocument(
            MultipartFile file,
            String docType,
            String bizTags,
            String publishDate) {
        try {
            // 构建 multipart 请求体
            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();

            // 将文件转换为 ByteArrayResource，以便通过 RestTemplate 发送
            ByteArrayResource fileResource = new ByteArrayResource(file.getBytes()) {
                @Override
                public String getFilename() {
                    return file.getOriginalFilename();
                }
            };
            body.add("file", fileResource);
            body.add("doc_type", docType);
            body.add("biz_tags", bizTags != null ? bizTags : "");
            if (publishDate != null) {
                body.add("publish_date", publishDate);
            }

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);
            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    aiRagBaseUrl + "/knowledge/upload", HttpMethod.POST, requestEntity,
                    (Class<Map<String, Object>>) (Class<?>) Map.class);

            return Result.success(response.getBody());
        } catch (IOException e) {
            log.error("[KnowledgeProxy] 文件读取失败", e);
            return Result.fail("文件读取失败: " + e.getMessage());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 上传文档失败", e);
            return Result.fail("上传失败: " + e.getMessage());
        }
    }

    /**
     * 查询文档列表
     */
    public Result<Object> listDocuments(String docType, String keyword, int page, int size) {
        try {
            StringBuilder url = new StringBuilder(aiRagBaseUrl + "/knowledge/list?page=" + page + "&size=" + size);
            if (docType != null && !docType.isEmpty()) {
                url.append("&doc_type=").append(docType);
            }
            if (keyword != null && !keyword.isEmpty()) {
                url.append("&keyword=").append(keyword);
            }

            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(url.toString(), HttpMethod.GET, null,
                    (Class<Map<String, Object>>) (Class<?>) Map.class);
            return Result.success(response.getBody());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 查询文档列表失败", e);
            return Result.fail("查询失败: " + e.getMessage());
        }
    }

    /**
     * 获取单个文档详情
     */
    public Result<Object> getDocument(String docId) {
        return doGet("/knowledge/" + docId);
    }

    /**
     * 删除文档
     */
    public Result<Object> deleteDocument(String docId) {
        try {
            restTemplate.delete(aiRagBaseUrl + "/knowledge/" + docId);
            return Result.success();
        } catch (HttpClientErrorException e) {
            if (e.getStatusCode() == HttpStatus.NOT_FOUND) {
                return Result.fail(404, "文档不存在");
            }
            log.error("[KnowledgeProxy] 删除文档失败", e);
            return Result.fail("删除失败: " + e.getMessage());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 删除文档失败", e);
            return Result.fail("删除失败: " + e.getMessage());
        }
    }

    /**
     * 获取文档切块列表
     */
    public Result<Object> getDocumentChunks(String docId) {
        return doGet("/knowledge/" + docId + "/chunks");
    }

    /**
     * 修正 Chunk 内容
     */
    public Result<Object> updateChunk(String docId, String chunkId, String content) {
        try {
            MultiValueMap<String, String> body = new LinkedMultiValueMap<>();
            body.add("content", content);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);
            HttpEntity<MultiValueMap<String, String>> requestEntity = new HttpEntity<>(body, headers);

            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    aiRagBaseUrl + "/knowledge/" + docId + "/chunks/" + chunkId,
                    HttpMethod.PUT,
                    requestEntity,
                    (Class<Map<String, Object>>) (Class<?>) Map.class);

            return Result.success(response.getBody());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 更新 Chunk 失败", e);
            return Result.fail("更新失败: " + e.getMessage());
        }
    }

    /**
     * 重新处理文档
     */
    public Result<Object> reprocessDocument(String docId) {
        try {
            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    aiRagBaseUrl + "/knowledge/" + docId + "/reprocess",
                    HttpMethod.POST, null, (Class<Map<String, Object>>) (Class<?>) Map.class);
            return Result.success(response.getBody());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 重新处理文档失败", e);
            return Result.fail("重新处理失败: " + e.getMessage());
        }
    }

    /**
     * 执行知识库语义检索（供 ai-engine 调用，包装为 ToolCard 出参）
     *
     * 功能: 将强类型 KnowledgeSearchRequest 转换为 ai-rag 接受的 snake_case Map，
     * 调用 ai-rag /knowledge/search 接口，再将响应的原始 Map 解析为结构化的
     * KnowledgeSearchResult 返回，方便 AI Agent 精准解析出参。
     */
    public Result<KnowledgeSearchResult> search(KnowledgeSearchRequest request) {
        try {
            // 第一步：构建发往 ai-rag 的参数体（字段名与 Python SearchRequest 模型对齐）
            Map<String, Object> body = new HashMap<>();
            body.put("query", request.getQuery());
            body.put("top_k", request.getTopK() != null ? request.getTopK() : 5);
            if (request.getDocType() != null && !request.getDocType().isBlank()) {
                body.put("doc_type", request.getDocType());
            }

            // 第二步：发送请求到 ai-rag 微服务
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(body, headers);

            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    aiRagBaseUrl + "/knowledge/search",
                    HttpMethod.POST, requestEntity, (Class<Map<String, Object>>) (Class<?>) Map.class);

            // 第三步：将 ai-rag 原始响应解析为强类型 KnowledgeSearchResult
            Map<String, Object> responseBody = response.getBody();
            if (responseBody == null) {
                return Result.fail("[知识库检索] ai-rag 返回空响应，请稍后重试。");
            }

            // 解析 data 字段（ai-rag 返回 {code, message, data: [...]}）
            Object dataObj = responseBody.get("data");
            List<KnowledgeSearchResult.Item> items = new ArrayList<>();

            if (dataObj instanceof List<?> rawList) {
                // 遍历 ai-rag 返回的 SearchResult 列表，逐项映射为 KnowledgeSearchResult.Item
                for (Object rawItem : rawList) {
                    if (rawItem instanceof Map) {
                        // 强转为 Map<String, Object>，ai-rag 使用 Jackson 序列化，key 均为 String 类型
                        @SuppressWarnings("unchecked")
                        Map<String, Object> itemMap = (Map<String, Object>) rawItem;
                        KnowledgeSearchResult.Item item = new KnowledgeSearchResult.Item();
                        item.setContent(String.valueOf(itemMap.getOrDefault("content", "")));
                        item.setDocId(String.valueOf(itemMap.getOrDefault("doc_id", "")));
                        item.setDocName(String.valueOf(itemMap.getOrDefault("doc_name", "")));
                        item.setDocType(String.valueOf(itemMap.getOrDefault("doc_type", "")));
                        Object scoreObj = itemMap.get("score");
                        item.setScore(scoreObj instanceof Number ? ((Number) scoreObj).doubleValue() : 0.0);
                        Object chunkCountObj = itemMap.get("chunk_count");
                        item.setChunkCount(chunkCountObj instanceof Number ? ((Number) chunkCountObj).intValue() : 0);
                        items.add(item);
                    }
                }
            }

            KnowledgeSearchResult result = new KnowledgeSearchResult(items, items.size());
            return Result.success(result);

        } catch (HttpClientErrorException e) {
            // 客户端错误（4xx）通常是参数问题，透传给 AI 以便自我修正
            log.warn("[KnowledgeProxy] 知识库检索请求参数错误: {}", e.getResponseBodyAsString());
            return Result.fail(400, "[AI调用错误] ai-rag 拒绝了本次请求，原因：" + e.getResponseBodyAsString()
                    + "。请检查参数后重试。");
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 知识库检索失败", e);
            return Result.fail("[知识库检索] 服务调用失败，错误信息：" + e.getMessage() + "。若问题持续，请联系系统管理员。");
        }
    }

    /**
     * 通用 GET 请求封装
     */
    private Result<Object> doGet(String path) {
        try {
            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(aiRagBaseUrl + path, HttpMethod.GET,
                    null, (Class<Map<String, Object>>) (Class<?>) Map.class);
            return Result.success(response.getBody());
        } catch (HttpClientErrorException e) {
            if (e.getStatusCode() == HttpStatus.NOT_FOUND) {
                return Result.fail(404, "资源不存在");
            }
            log.error("[KnowledgeProxy] GET {} 失败", path, e);
            return Result.fail("请求失败: " + e.getMessage());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] GET {} 失败", path, e);
            return Result.fail("请求失败: " + e.getMessage());
        }
    }
}
