package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import lombok.Data;

/**
 * Tool: 获取会话消息列表请求参数
 */
@Data
public class ToolGetMessagesRequest {
    @ToolInput(param_name = "sessionId", param_description = "目标会话ID", param_required = true)
    private String sessionId;
}
