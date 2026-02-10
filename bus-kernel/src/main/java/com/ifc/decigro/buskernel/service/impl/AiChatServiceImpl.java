package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.dto.CreateSessionRequest;
import com.ifc.decigro.buskernel.dto.SaveMessageRequest;
import com.ifc.decigro.buskernel.service.AiChatService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * AI 聊天会话服务实现类
 */
@Slf4j
@Service
public class AiChatServiceImpl implements AiChatService {

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Override
    public List<Map<String, Object>> listSessions(String userId) {
        return jdbcTemplate.queryForList(
                "SELECT session_id, user_id, session_title, create_time, update_time " +
                        "FROM ai_chat_session WHERE user_id = ? ORDER BY update_time DESC",
                userId);
    }

    @Override
    @Transactional
    public Map<String, Object> createSession(String userId, CreateSessionRequest request) {
        String sessionId = "session_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        String title = (request != null && request.getTitle() != null) ? request.getTitle() : "新会话";

        jdbcTemplate.update(
                "INSERT INTO ai_chat_session (session_id, user_id, session_title, create_time, update_time) " +
                        "VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                sessionId, userId, title);

        return Map.of(
                "sessionId", sessionId,
                "userId", userId,
                "sessionTitle", title);
    }

    @Override
    public List<Map<String, Object>> getMessages(String sessionId) {
        return jdbcTemplate.queryForList(
                "SELECT id, session_id, task_id, trace_id, role, content, create_time " +
                        "FROM ai_chat_message WHERE session_id = ? ORDER BY create_time ASC",
                sessionId);
    }

    @Override
    @Transactional
    public void saveMessage(SaveMessageRequest request) {
        jdbcTemplate.update(
                "INSERT INTO ai_chat_message (session_id, task_id, trace_id, role, content, create_time) " +
                        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                request.getSessionId(),
                request.getTaskId(),
                request.getTraceId(),
                request.getRole(),
                request.getContent());

        // 同时更新会话的 update_time
        jdbcTemplate.update(
                "UPDATE ai_chat_session SET update_time = CURRENT_TIMESTAMP WHERE session_id = ?",
                request.getSessionId());
    }

    @Override
    @Transactional
    public void deleteSession(String sessionId, String userId) {
        int affected = jdbcTemplate.update(
                "DELETE FROM ai_chat_session WHERE session_id = ? AND user_id = ?",
                sessionId, userId);

        if (affected == 0) {
            throw new RuntimeException("会话不存在或无权删除");
        }
    }

    @Override
    @Transactional
    public void updateSession(String sessionId, String userId, CreateSessionRequest request) {
        int affected = jdbcTemplate.update(
                "UPDATE ai_chat_session SET session_title = ?, update_time = CURRENT_TIMESTAMP " +
                        "WHERE session_id = ? AND user_id = ?",
                request.getTitle(), sessionId, userId);

        if (affected == 0) {
            throw new RuntimeException("会话不存在或无权修改");
        }
    }
}
