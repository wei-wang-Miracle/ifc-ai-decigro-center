package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolInput;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 查询场内基金ETF特征值请求 DTO
 */
@Data
public class FundEtfFeaturesRequest {

    @ToolInput(
            param_name = "fundCode",
            param_type = "string",
            param_required = true,
            param_description = "6位纯数字格式的场内基金（ETF）代码。" +
                    "不得携带交易所前缀（如 sh/sz），只传纯数字部分。",
            param_example = "510050"
    )
    @NotBlank(message = "[AI调用错误] fundCode 为必填项，不可为空。")
    @Pattern(regexp = "^\\d{6}$", message = "[AI调用错误] fundCode 必须是精确的 6 位纯数字格式（例如 510050），当前传入的值不合法。")
    private String fundCode;
}
