package com.ifc.decigro.buskernel.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.util.Map;

/**
 * 通用 MongoDB 查询请求 DTO
 * 功能: 封装工具名和动态查询参数，用于 Controller 层的统一分发
 */
@Data
@Schema(description = "通用 MongoDB 查询请求")
public class MongoQueryRequest {

    @Schema(description = "工具路径/业务标识 (如: fund-etf-features)", required = true)
    private String toolPath;

    @Schema(description = "查询参数 Map (如: { \"fundCode\": \"510050\" })")
    private Map<String, Object> params;
}
