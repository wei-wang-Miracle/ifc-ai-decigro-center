package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.List;

/**
 * 部门表
 * 定义职能边界与工作流上下文
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Table("sys_dept")
public class SysDept extends BaseEntity {

    /**
     * 主键 ID
     */
    @Id(keyType = KeyType.Auto)
    private Long deptId;

    /**
     * 父部门 ID
     */
    private Long parentId;

    /**
     * 部门名称
     */
    private String deptName;

    /**
     * 子部门列表 (非数据库字段)
     */
    @Column(ignore = true)
    private List<SysDept> children;
}
