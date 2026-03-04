package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import lombok.Data;

/**
 * 查询客群数据详情请求 DTO
 * 替代原有的 JSONObject，用于驱动 ToolCardAutoRegistrar 正确生成 tool_parameters Schema。
 */
@Data
public class CustomerGroupDetailRequest {

    @ToolInput(
            param_name = "sql",
            param_type = "string",
            param_required = true,
            param_description = "合法的 SELECT 查询语句，只能查询 dm.sr_wide_client 表。" +
                    "禁止携带 DDL/DML 操作。示例：SELECT client_id, client_name FROM dm.sr_wide_client WHERE risk_level = '高风险'",
            param_example = "SELECT client_id, client_name, asset_td FROM dm.sr_wide_client WHERE corp_risk_level_name = 'C4积极型' AND asset_td >= 50000"
    )
    private String sql;

    @ToolInput(
            param_name = "limit",
            param_type = "integer",
            param_required = false,
            param_description = "返回记录条数上限，范围 1~1000，默认 100。",
            param_example = "100"
    )
    private Integer limit;
}
