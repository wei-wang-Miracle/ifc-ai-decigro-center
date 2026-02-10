package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.auth.TokenProvider;
import com.ifc.decigro.buskernel.dto.CreateSessionRequest;
import com.ifc.decigro.buskernel.dto.SaveMessageRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * AI 聊天会话控制器
 * 功能: 提供会话管理 CRUD API
 */
@Slf4j
@RestController
@RequestMapping("/ai/chat")
public class AiChatController {

    @Autowired
    private JdbcTemplate jdbcTemplate;

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

            List<Map<String, Object>> sessions = jdbcTemplate.queryForList(
                    "SELECT session_id, user_id, session_title, create_time, update_time " +
                            "FROM ai_chat_session WHERE user_id = ? ORDER BY update_time DESC",
                    userId);

            return Result.success(sessions);
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

            String sessionId = "session_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
            String title = (request != null && request.getTitle() != null) ? request.getTitle() : "新会话";

            jdbcTemplate.update(
                    "INSERT INTO ai_chat_session (session_id, user_id, session_title, create_time, update_time) " +
                            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    sessionId, userId, title);

            Map<String, Object> result = Map.of(
                    "sessionId", sessionId,
                    "userId", userId,
                    "sessionTitle", title);

            return Result.success(result);
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

            List<Map<String, Object>> messages = jdbcTemplate.queryForList(
                    "SELECT id, session_id, task_id, trace_id, role, content, create_time " +
                            "FROM ai_chat_message WHERE session_id = ? ORDER BY create_time ASC",
                    sessionId);

            return Result.success(messages);
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

            jdbcTemplate.update(
                    "INSERT INTO ai_chat_message (session_id, task_id, trace_id, role, content, create_time) " +
                            "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    request.getSessionId(),
                    request.getTaskId(),
                    request.getTraceId(),
                    request.getRole(),
                    request.getContent());

            // 同时更新会话的 update_time，让最近活跃的会话排在前面
            jdbcTemplate.update(
                    "UPDATE ai_chat_session SET update_time = CURRENT_TIMESTAMP WHERE session_id = ?",
                    request.getSessionId());

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

            // 只允许删除自己的会话
            int affected = jdbcTemplate.update(
                    "DELETE FROM ai_chat_session WHERE session_id = ? AND user_id = ?",
                    sessionId, userId);

            if (affected == 0) {
                return Result.fail("会话不存在或无权删除");
            }

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

            int affected = jdbcTemplate.update(
                    "UPDATE ai_chat_session SET session_title = ?, update_time = CURRENT_TIMESTAMP " +
                            "WHERE session_id = ? AND user_id = ?",
                    request.getTitle(), sessionId, userId);

            if (affected == 0) {
                return Result.fail("会话不存在或无权修改");
            }

            return Result.success();
        } catch (Exception e) {
            log.error("更新会话失败", e);
            return Result.fail("更新会话失败: " + e.getMessage());
        }
    }
}
