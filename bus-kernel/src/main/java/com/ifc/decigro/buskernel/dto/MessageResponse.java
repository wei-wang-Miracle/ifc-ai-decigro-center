package com.ifc.decigro.buskernel.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 消息响应 DTO
 */
@Data
public class MessageResponse {
    private Long id;
    private String sessionId;
    private String taskId;
    private String traceId;
    private String role;
    private String content;
    private LocalDateTime createTime;
}
