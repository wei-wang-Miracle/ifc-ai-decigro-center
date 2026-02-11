package com.ifc.decigro.buskernel.dto;

import lombok.Data;

/**
 * 保存消息请求 DTO
 */
@Data
public class SaveMessageRequest {
    private String sessionId;
    private String taskId;
    private String traceId;
    private String role; // "user" 或 "assistant"
    private String content;
    private String thoughtLog; // 思考过程 (JSON字符串)
}
