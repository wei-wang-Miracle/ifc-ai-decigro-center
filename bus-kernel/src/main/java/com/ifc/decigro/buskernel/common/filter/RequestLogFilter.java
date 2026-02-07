package com.ifc.decigro.buskernel.common.filter;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import jakarta.servlet.*;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.util.ContentCachingRequestWrapper;
import org.springframework.web.util.ContentCachingResponseWrapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;

/**
 * 请求日志过滤器
 * 
 * 功能：拦截所有HTTP请求，提取请求参数并记录日志，以及响应状态和耗时
 * 适配 Spring Boot 3 (使用 jakarta.servlet)
 */
@Slf4j
@Component
@Order(10)
@RequiredArgsConstructor
public class RequestLogFilter implements Filter {

    @Override
    public void doFilter(ServletRequest servletRequest, ServletResponse servletResponse,
            FilterChain filterChain)
            throws IOException, ServletException {

        if (!(servletRequest instanceof HttpServletRequest request) ||
                !(servletResponse instanceof HttpServletResponse response)) {
            filterChain.doFilter(servletRequest, servletResponse);
            return;
        }

        // 记录请求开始时间
        long startTime = System.currentTimeMillis();
        String requestURI = request.getRequestURI();
        String method = request.getMethod();
        String contentType = request.getContentType();

        // 包装请求和响应，以便多次读取内容
        ContentCachingRequestWrapper wrappedRequest = new ContentCachingRequestWrapper(request);
        ContentCachingResponseWrapper wrappedResponse = new ContentCachingResponseWrapper(response);

        log.info(">>>>>> [请求开始] URI: {} | Method: {} | Content-Type: {}", requestURI, method, contentType);

        // 提取URL查询参数
        JSONObject urlParams = extractUrlParameters(wrappedRequest);
        if (!urlParams.isEmpty()) {
            log.info(">>>>>> [查询参数]: {}", urlParams);
        }

        try {
            // 继续过滤器链
            filterChain.doFilter(wrappedRequest, wrappedResponse);
        } finally {
            // 提取请求体参数
            JSONObject bodyParams = extractBodyParameters(wrappedRequest, contentType);
            if (!bodyParams.isEmpty()) {
                log.info(">>>>>> [请求体参数]: {}", bodyParams);
            }

            // 计算耗时
            long duration = System.currentTimeMillis() - startTime;
            int statusCode = wrappedResponse.getStatus();

            log.info("<<<<<< [请求结束] Status: {} | Time: {}ms", statusCode, duration);

            // 重要：将缓存的响应内容复制回原始响应流，否则客户端将收到空响应
            wrappedResponse.copyBodyToResponse();
        }
    }

    /**
     * 提取URL查询参数
     */
    private JSONObject extractUrlParameters(HttpServletRequest request) {
        JSONObject params = new JSONObject();
        Enumeration<String> parameterNames = request.getParameterNames();

        while (parameterNames.hasMoreElements()) {
            String paramName = parameterNames.nextElement();
            String[] paramValues = request.getParameterValues(paramName);

            if (paramValues != null) {
                if (paramValues.length == 1) {
                    params.set(paramName, paramValues[0]);
                } else {
                    params.set(paramName, paramValues);
                }
            }
        }
        return params;
    }

    /**
     * 提取请求体参数
     */
    private JSONObject extractBodyParameters(ContentCachingRequestWrapper request, String contentType) {
        JSONObject bodyParams = new JSONObject();

        byte[] content = request.getContentAsByteArray();
        if (content.length == 0) {
            return bodyParams;
        }

        String requestBody = new String(content, StandardCharsets.UTF_8);

        if (contentType != null) {
            if (contentType.contains(MediaType.APPLICATION_JSON_VALUE)) {
                bodyParams = parseJsonBody(requestBody);
            } else if (contentType.contains(MediaType.APPLICATION_FORM_URLENCODED_VALUE)) {
                bodyParams.set("formData", requestBody);
            } else if (contentType.contains(MediaType.MULTIPART_FORM_DATA_VALUE)) {
                bodyParams.set("multipart", "[Multipart Data]");
            } else {
                bodyParams.set("rawBody", truncateContent(requestBody, 500));
            }
        }

        return bodyParams;
    }

    /**
     * 解析JSON请求体
     */
    private JSONObject parseJsonBody(String jsonBody) {
        try {
            return JSONUtil.parseObj(jsonBody);
        } catch (Exception e) {
            log.warn("解析请求体JSON失败: {}", e.getMessage());
            JSONObject fallback = new JSONObject();
            fallback.set("rawJson", truncateContent(jsonBody, 200));
            return fallback;
        }
    }

    /**
     * 截断内容
     */
    private String truncateContent(String content, int maxLength) {
        if (content == null || content.length() <= maxLength) {
            return content;
        }
        return content.substring(0, maxLength) + "...(truncated)";
    }

    @Override
    public void init(FilterConfig filterConfig) throws ServletException {
        // 初始化逻辑
    }

    @Override
    public void destroy() {
        // 销毁逻辑
    }
}
