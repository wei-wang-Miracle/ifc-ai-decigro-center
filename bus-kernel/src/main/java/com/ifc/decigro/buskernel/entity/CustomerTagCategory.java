package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 标签分类实体类
 * 功能: 对应数据库 customer_tag_category 表，支持树形结构
 * 
 * 表结构:
 * - id: 主键ID (手动维护或序列生成)
 * - name: 分类名称
 * - parent_id: 上级分类ID，一级分类设为0
 * - sort_index: 排序序号
 * - create_time / update_time: 时间戳
 */
@Data
@Table("customer_tag_category")
public class CustomerTagCategory implements Serializable {

    /**
     * 主键ID
     * 使用雪花算法自动生成，确保分布式环境下ID唯一
     */
    @Id(keyType = KeyType.Generator, value = "snowFlakeId")
    private Long id;

    /**
     * 分类名称
     */
    private String name;

    /**
     * 上级分类ID
     * 一级分类（根分类）设为 0
     */
    private Long parentId;

    /**
     * 排序序号
     * 用于控制同级分类的显示顺序，数值越小越靠前
     */
    private Integer sortIndex;

    /**
     * 创建时间
     * 插入数据时由数据库自动填充当前时间
     */
    @Column(onInsertValue = "now()")
    private LocalDateTime createTime;

    /**
     * 更新时间
     * 插入或更新数据时由数据库自动填充当前时间
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private LocalDateTime updateTime;

    /**
     * 子分类列表
     * 非数据库字段，用于构建树形结构时存放子节点
     */
    @Column(ignore = true)
    private List<CustomerTagCategory> children;
}
