package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolOutput;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 会话响应 DTO
 */
@Data
public class SessionResponse {
    @ToolOutput(param_name = "sessionId", param_description = "会话ID")
    private String sessionId;

    @ToolOutput(param_name = "userId", param_description = "用户ID")
    private String userId;

    @ToolOutput(param_name = "sessionTitle", param_description = "会话标题")
    private String sessionTitle;

    @ToolOutput(param_name = "createTime", param_description = "创建时间")
    private LocalDateTime createTime;

    @ToolOutput(param_name = "updateTime", param_description = "更新时间")
    private LocalDateTime updateTime;

    @ToolOutput(param_name = "messages", param_description = "会话消息列表", param_type = "array")
    private java.util.List<MessageResponse> messages;
}
