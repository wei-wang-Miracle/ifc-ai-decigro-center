package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import lombok.Data;

/**
 * 查询标签分组数量请求 DTO
 * 接收用户自然语言查询，内部调用 NL2SQL 服务转换后执行 StarRocks 查询。
 */
@Data
public class LabelGroupCountRequest {

    @ToolInput(
            param_name = "question",
            param_type = "string",
            param_required = true,
            param_description = "用户的自然语言查询问题，描述想要统计的数据内容。示例：'风险等级(corp_risk_level)大于C4且资产(asset_td)大于5万的客户数量'",
            param_example = "风险等级(corp_risk_level)大于C4且资产(asset_td)大于5万的客户数量"
    )
    private String question;
}
