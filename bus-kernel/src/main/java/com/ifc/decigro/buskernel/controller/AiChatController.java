package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.auth.TokenProvider;
import com.ifc.decigro.buskernel.dto.CreateSessionRequest;
import com.ifc.decigro.buskernel.dto.SaveMessageRequest;
import com.ifc.decigro.buskernel.service.AiChatService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import com.ifc.decigro.buskernel.dto.MessageResponse;
import com.ifc.decigro.buskernel.dto.SessionResponse;
import com.ifc.decigro.buskernel.dto.ToolGetMessagesRequest;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.sql.Timestamp;
import java.time.LocalDateTime;

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

    /**
     * Tool: 获取当前用户的会话列表
     * POST /api/dg/ai/chat/tool/sessions
     */
    @PostMapping("/tool/sessions")
    @ToolCard(tool_name = "get_current_user_sessions", summary = "获取当前用户的会话列表", alias = "获取当前用户的会话列表", description = "获取当前登录用户的所有历史会话列表。当需要查找、回顾或管理当前用户的对话历史时使用。", tags = {
            "chat_management", "session_history", "user_context" })
    public Result<List<SessionResponse>> toolListSessions(
            @RequestHeader("X-Auth-Token") String token) {
        try {
            String[] parts = tokenProvider.validateAndParse(token);
            String userId = parts[3];

            List<Map<String, Object>> list = aiChatService.listSessions(userId);
            List<SessionResponse> result = list.stream().map(map -> {
                SessionResponse dto = new SessionResponse();
                dto.setSessionId((String) map.get("session_id"));
                dto.setUserId((String) map.get("user_id"));
                dto.setSessionTitle((String) map.get("session_title"));
                // 安全处理时间类型转换
                Object createTime = map.get("create_time");
                if (createTime instanceof Timestamp) {
                    dto.setCreateTime(((Timestamp) createTime).toLocalDateTime());
                } else if (createTime instanceof LocalDateTime) {
                    dto.setCreateTime((LocalDateTime) createTime);
                }

                Object updateTime = map.get("update_time");
                if (updateTime instanceof Timestamp) {
                    dto.setUpdateTime(((Timestamp) updateTime).toLocalDateTime());
                } else if (updateTime instanceof LocalDateTime) {
                    dto.setUpdateTime((LocalDateTime) updateTime);
                }
                return dto;
            }).collect(Collectors.toList());
            return Result.success(result);
        } catch (Exception e) {
            log.error("Tool获取会话列表失败", e);
            return Result.fail("获取会话列表失败: " + e.getMessage());
        }
    }

    /**
     * Tool: 获取指定会话的消息记录
     * POST /api/dg/ai/chat/tool/messages
     */
    @PostMapping("/tool/messages")
    @ToolCard(tool_name = "get_session_messages", summary = "获取指定会话的消息记录", alias = "获取指定会话的消息记录", description = "根据会话ID获取该会话的所有详细消息记录。当需要深入分析特定对话的内容、上下文或执行过程时使用。", tags = {
            "chat_analysis", "message_details", "context_retrieval" })
    public Result<List<MessageResponse>> toolGetMessages(
            @RequestBody ToolGetMessagesRequest request) {
        try {
            List<Map<String, Object>> list = aiChatService.getMessages(request.getSessionId());
            List<MessageResponse> result = list.stream().map(map -> {
                MessageResponse dto = new MessageResponse();
                dto.setId((Long) map.get("id"));
                dto.setSessionId((String) map.get("session_id"));
                dto.setTaskId((String) map.get("task_id"));
                dto.setTraceId((String) map.get("trace_id"));
                dto.setRole((String) map.get("role"));
                dto.setContent((String) map.get("content"));
                dto.setThoughtLog((String) map.get("thought_log"));
                dto.setAgentLog((String) map.get("agent_log"));

                Object createTime = map.get("create_time");
                if (createTime instanceof Timestamp) {
                    dto.setCreateTime(((Timestamp) createTime).toLocalDateTime());
                } else if (createTime instanceof LocalDateTime) {
                    dto.setCreateTime((LocalDateTime) createTime);
                }
                return dto;
            }).collect(Collectors.toList());
            return Result.success(result);
        } catch (Exception e) {
            log.error("Tool获取消息列表失败", e);
            return Result.fail("获取消息列表失败: " + e.getMessage());
        }
    }
}
