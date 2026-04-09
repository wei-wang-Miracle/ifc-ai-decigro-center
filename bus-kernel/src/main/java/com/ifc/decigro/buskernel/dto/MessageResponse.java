package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolOutput;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 消息响应 DTO
 */
@Data
public class MessageResponse {
    @ToolOutput(param_name = "id", param_description = "消息ID")
    private Long id;

    @ToolOutput(param_name = "sessionId", param_description = "会话ID")
    private String sessionId;

    @ToolOutput(param_name = "taskId", param_description = "任务ID")
    private String taskId;

    @ToolOutput(param_name = "traceId", param_description = "追踪ID")
    private String traceId;

    @ToolOutput(param_name = "role", param_description = "角色")
    private String role;

    @ToolOutput(param_name = "content", param_description = "内容")
    private String content;

    @ToolOutput(param_name = "thoughtLog", param_description = "思考日志")
    private String thoughtLog;

    @ToolOutput(param_name = "agentLog", param_description = "Agent执行日志")
    private String agentLog;

    @ToolOutput(param_name = "reviewDetail", param_description = "审核详情")
    private String reviewDetail;

    @ToolOutput(param_name = "createTime", param_description = "创建时间")
    private LocalDateTime createTime;
}
