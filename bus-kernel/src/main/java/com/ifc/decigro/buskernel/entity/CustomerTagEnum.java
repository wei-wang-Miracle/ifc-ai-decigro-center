package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 标签枚举值实体类
 * 功能: 对应数据库 customer_tag_enum 表，存储枚举类型标签的可选值
 * 
 * 表结构:
 * - id: 主键ID
 * - tag_field: 关联 customer_tag 的字段名
 * - enum_code: 枚举值代码 (存储值，用于SQL拼接)
 * - enum_name: 枚举展示名称 (界面显示值)
 */
@Data
@Table("customer_tag_enum")
public class CustomerTagEnum implements Serializable {

    /**
     * 主键ID
     * 使用雪花算法自动生成
     */
    @Id(keyType = KeyType.Generator, value = "snowFlakeId")
    private Long id;

    /**
     * 关联的标签字段名
     * 外键，指向 customer_tag.tag_field
     */
    private String tagField;

    /**
     * 枚举值代码
     * 实际存入数据库的值，用于SQL查询条件拼接
     * 例如: "1", "A", "HIGH"
     */
    private String enumCode;

    /**
     * 枚举展示名称
     * 界面上供用户选择时显示的可读名称
     * 例如: "是", "优秀", "高等级"
     */
    private String enumName;

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
}
