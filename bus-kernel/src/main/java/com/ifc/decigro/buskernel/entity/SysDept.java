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
 * 部门表
 * 定义职能边界与工作流上下文
 */
@Data
@Table("sys_dept")
public class SysDept implements Serializable {

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
     * 租户编码
     * 用于多租户隔离
     */
    @Column(tenantId = true)
    private String tenantCode;

    /**
     * 创建时间
     */
    @Column(onInsertValue = "now()")
    private LocalDateTime createdTime;

    /**
     * 更新时间
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private LocalDateTime updatedTime;

    /**
     * 子部门列表 (非数据库字段)
     */
    @Column(ignore = true)
    private List<SysDept> children;
}
