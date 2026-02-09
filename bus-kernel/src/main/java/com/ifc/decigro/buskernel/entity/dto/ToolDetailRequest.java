package com.ifc.decigro.buskernel.entity.dto;

import lombok.Data;

import java.io.Serializable;

/**
 * 获取工具详情请求 DTO
 */
@Data
public class ToolDetailRequest implements Serializable {

    /**
     * 工具名称
     */
    private String toolName;
}
