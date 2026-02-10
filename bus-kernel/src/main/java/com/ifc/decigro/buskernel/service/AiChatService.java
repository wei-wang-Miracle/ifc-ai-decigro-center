package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.dto.CreateSessionRequest;
import com.ifc.decigro.buskernel.dto.SaveMessageRequest;

import java.util.List;
import java.util.Map;

/**
 * AI 聊天会话服务接口
 */
public interface AiChatService {

    /**
     * 获取用户会话列表
     */
    List<Map<String, Object>> listSessions(String userId);

    /**
     * 创建新会话
     */
    Map<String, Object> createSession(String userId, CreateSessionRequest request);

    /**
     * 获取会话历史消息
     */
    List<Map<String, Object>> getMessages(String sessionId);

    /**
     * 保存消息记录
     */
    void saveMessage(SaveMessageRequest request);

    /**
     * 删除会话
     */
    void deleteSession(String sessionId, String userId);

    /**
     * 更新会话标题
     */
    void updateSession(String sessionId, String userId, CreateSessionRequest request);
}
