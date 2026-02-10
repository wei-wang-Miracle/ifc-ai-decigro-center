package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.auth.TokenProvider;
import com.ifc.decigro.buskernel.dto.CreateSessionRequest;
import com.ifc.decigro.buskernel.dto.SaveMessageRequest;
import com.ifc.decigro.buskernel.service.AiChatService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * AI 聊天会话控制器
 * 功能: 提供会话管理 CRUD API
 */
@Slf4j
@RestController
@RequestMapping("/ai/chat")
public class AiChatController {

    @Autowired
    private AiChatService aiChatService;

    @Autowired
    private TokenProvider tokenProvider;

    // ========================================
    // API 端点
    // ========================================

    /**
     * 获取当前用户的会话列表
     * GET /api/dg/ai/chat/sessions
     */
    @GetMapping("/sessions")
    public Result<List<Map<String, Object>>> listSessions(
            @RequestHeader("X-Auth-Token") String token) {
        try {
            String[] parts = tokenProvider.validateAndParse(token);
            String userId = parts[3]; // username 作为 user_id

            return Result.success(aiChatService.listSessions(userId));
        } catch (Exception e) {
            log.error("获取会话列表失败", e);
            return Result.fail("获取会话列表失败: " + e.getMessage());
        }
    }

    /**
     * 创建新会话
     * POST /api/dg/ai/chat/sessions
     */
    @PostMapping("/sessions")
    public Result<Map<String, Object>> createSession(
            @RequestHeader("X-Auth-Token") String token,
            @RequestBody(required = false) CreateSessionRequest request) {
        try {
            String[] parts = tokenProvider.validateAndParse(token);
            String userId = parts[3];

            return Result.success(aiChatService.createSession(userId, request));
        } catch (Exception e) {
            log.error("创建会话失败", e);
            return Result.fail("创建会话失败: " + e.getMessage());
        }
    }

    /**
     * 获取会话的历史消息
     * GET /api/dg/ai/chat/sessions/{sessionId}/messages
     */
    @GetMapping("/sessions/{sessionId}/messages")
    public Result<List<Map<String, Object>>> getMessages(
            @RequestHeader("X-Auth-Token") String token,
            @PathVariable String sessionId) {
        try {
            // 验证 token
            tokenProvider.validateAndParse(token);

            return Result.success(aiChatService.getMessages(sessionId));
        } catch (Exception e) {
            log.error("获取消息列表失败", e);
            return Result.fail("获取消息列表失败: " + e.getMessage());
        }
    }

    /**
     * 保存消息记录
     * POST /api/dg/ai/chat/messages
     * 前端在发送消息和收到 AI 回复后分别调用此接口持久化
     */
    @PostMapping("/messages")
    public Result<Void> saveMessage(
            @RequestHeader("X-Auth-Token") String token,
            @RequestBody SaveMessageRequest request) {
        try {
            // 验证 token
            tokenProvider.validateAndParse(token);

            aiChatService.saveMessage(request);
            return Result.success();
        } catch (Exception e) {
            log.error("保存消息失败", e);
            return Result.fail("保存消息失败: " + e.getMessage());
        }
    }

    /**
     * 删除会话
     * DELETE /api/dg/ai/chat/sessions/{sessionId}
     */
    @DeleteMapping("/sessions/{sessionId}")
    public Result<Void> deleteSession(
            @RequestHeader("X-Auth-Token") String token,
            @PathVariable String sessionId) {
        try {
            String[] parts = tokenProvider.validateAndParse(token);
            String userId = parts[3];

            aiChatService.deleteSession(sessionId, userId);
            return Result.success();
        } catch (Exception e) {
            log.error("删除会话失败", e);
            return Result.fail("删除会话失败: " + e.getMessage());
        }
    }

    /**
     * 更新会话标题
     * PUT /api/dg/ai/chat/sessions/{sessionId}
     */
    @PutMapping("/sessions/{sessionId}")
    public Result<Void> updateSession(
            @RequestHeader("X-Auth-Token") String token,
            @PathVariable String sessionId,
            @RequestBody CreateSessionRequest request) {
        try {
            String[] parts = tokenProvider.validateAndParse(token);
            String userId = parts[3];

            aiChatService.updateSession(sessionId, userId, request);
            return Result.success();
        } catch (Exception e) {
            log.error("更新会话失败", e);
            return Result.fail("更新会话失败: " + e.getMessage());
        }
    }
}
