package com.ifc.decigro.buskernel.entity;

import com.ifc.decigro.buskernel.common.handler.Fastjson2TypeHandler;
import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.List;

/**
 * 租户表
 * 管理物理边界与系统接入源
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Table("sys_tenant")
public class SysTenant extends BaseEntity {

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
     * 绑定的工具列表 (JSONB)
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> toolList;

    /**
     * 是否有效
     */
    private Boolean isEnabled;
}
