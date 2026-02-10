package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.entity.AiChatTraceIndex;
import lombok.Data;

import java.util.Map;

/**
 * 审计数据写入请求体
 * 包含 PG 宽表数据和 ES 快照数据
 */
@Data
public class TraceWriteRequest {
    /**
     * PG 宽表数据
     */
    private AiChatTraceIndex traceIndex;

    /**
     * ES 完整快照数据 (JSON Map)
     */
    private Map<String, Object> esSnapshot;
}
