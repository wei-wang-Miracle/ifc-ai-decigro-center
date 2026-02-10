package com.ifc.decigro.buskernel.dto;

import lombok.Data;
import java.time.LocalDateTime;

/**
 * 会话响应 DTO
 */
@Data
public class SessionResponse {
    private String sessionId;
    private String userId;
    private String sessionTitle;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
