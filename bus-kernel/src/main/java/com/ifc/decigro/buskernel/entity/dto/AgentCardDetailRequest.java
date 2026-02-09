package com.ifc.decigro.buskernel.entity.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 获取智能体详情请求 DTO
 */
@Data
public class AgentCardDetailRequest implements Serializable {

    /**
     * 智能体名称
     */
    private String agentName;
}
