package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.common.api.Result;
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
            String relatedCodes,
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
            body.add("related_codes", relatedCodes != null ? relatedCodes : "");
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
     */
    public Result<Object> search(Map<String, Object> searchRequest) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<Map<String, Object>> requestEntity = new HttpEntity<>(searchRequest, headers);

            ResponseEntity<Map<String, Object>> response = restTemplate.exchange(
                    aiRagBaseUrl + "/knowledge/search",
                    HttpMethod.POST, requestEntity, (Class<Map<String, Object>>) (Class<?>) Map.class);

            return Result.success(response.getBody());
        } catch (Exception e) {
            log.error("[KnowledgeProxy] 知识库检索失败", e);
            return Result.fail("检索失败: " + e.getMessage());
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
