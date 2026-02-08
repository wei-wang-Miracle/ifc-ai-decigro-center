package com.ifc.decigro.buskernel.dto;

import com.ifc.decigro.buskernel.common.annotation.ToolOutput;
import lombok.Data;
import java.io.Serializable;
import java.util.List;
import java.util.Map;

/**
 * 客户标签 AI 工具输出 DTO
 * 功能: 为 AI Agent 提供标准化的标签元数据结构
 */
@Data
public class CustomerTagDto implements Serializable {

    @ToolOutput(param_name = "tagField", param_description = "标签字段名，也是唯一业务主键。生成SQL时使用此字段。", param_example = "cust_level")
    private String tagField;

    @ToolOutput(param_name = "tagTable", param_description = "标签数据所在的宽表名称", param_example = "ads_cust_tag_d")
    private String tagTable;

    @ToolOutput(param_name = "tagName", param_description = "标签的可读中文名称", param_example = "客户等级")
    private String tagName;

    @ToolOutput(param_name = "tagDesc", param_description = "标签的业务口径描述", param_example = "根据近1年消费金额计算的会员等级")
    private String tagDesc;

    @ToolOutput(param_name = "valueType", param_description = "值类型，决定了如何处理该标签的值。可选值: string, number, enum, date, array", param_example = "enum")
    private String valueType;

    @ToolOutput(param_name = "categoryName", param_description = "标签所属的一级分类名称，用于业务分组", param_example = "价值属性")
    private String categoryName;

    @ToolOutput(param_name = "tagEnums", param_type = "array", param_description = "枚举代码与名称的映射列表。仅当 valueType=enum 时有效。", param_example = "[{\"enum_code\":\"A\",\"enum_name\":\"高价值\"}]")
    private List<Map<String, String>> tagEnums;
}
