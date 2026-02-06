package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 租户表
 * 管理物理边界与系统接入源
 */
@Data
@Table("sys_tenant")
public class SysTenant implements Serializable {

    /**
     * 唯一租户编码 主键 ID (如 HEYI)
     */
    @Id(keyType = KeyType.None)
    private String tenantCode;

    /**
     * 租户名称
     */
    private String tenantName;

    /**
     * 是否有效
     */
    private Boolean isEnabled;

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
}
