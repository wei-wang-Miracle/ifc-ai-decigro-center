package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 客户标签实体类
 * 功能: 对应数据库 customer_tag 表，定义标签主数据
 * 
 * 表结构:
 * - tag_field: 主键，标签字段英文名 (用于SQL拼接)
 * - tag_table: 标签对应的来源表名
 * - tag_name: 标签中文名称
 * - tag_desc: 标签维护口径/详细描述
 * - value_type: 值类型 (string, number, enum, date, array)
 * - category_id: 关联分类ID
 * - remark: 备注
 * - sort_index: 排序序号
 */
@Data
@Table("customer_tag")
public class CustomerTag implements Serializable {

    /**
     * 标签字段名（主键）
     * 英文名称，用于后续SQL动态拼接，创建后不可修改
     * 例如: "customer_age", "income_level"
     */
    @Id(keyType = KeyType.None)
    private String tagField;

    /**
     * 标签来源表名
     * 标识该标签数据存储在哪张表中
     */
    private String tagTable;

    /**
     * 标签中文名称
     * 用于界面展示的可读性名称
     */
    private String tagName;

    /**
     * 标签描述/维护口径
     * 详细说明标签的含义、计算逻辑、数据来源等
     */
    private String tagDesc;

    /**
     * 值类型
     * 可选值: string, number, enum, date, array
     * 当类型为 enum 时，需要配置枚举值列表
     */
    private String valueType;

    /**
     * 关联分类ID
     * 外键，指向 customer_tag_category.id
     */
    private Long categoryId;

    /**
     * 备注信息
     */
    private String remark;

    /**
     * 排序序号
     * 用于控制同分类下标签的显示顺序
     */
    private Integer sortIndex;

    /**
     * 创建时间
     */
    @Column(onInsertValue = "now()")
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private LocalDateTime updateTime;

    /**
     * 分类名称
     * 非数据库字段，用于列表展示时回显分类名
     */
    @Column(ignore = true)
    private String categoryName;
}
