package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import com.mybatisflex.core.handler.Fastjson2TypeHandler;
import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 角色表
 * 定义基础权限与工具集模板
 */
@Data
@Table("sys_role")
public class SysRole implements Serializable {

    /**
     * 主键 ID
     */
    @Id(keyType = KeyType.Auto)
    private Long roleId;

    /**
     * 角色显示名称
     */
    private String roleName;

    /**
     * 描述
     */
    private String roleDesc;

    /**
     * 工具列表
     * JSONB 存储，对应 PRD 工具分配
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> toolList;

    /**
     * 是否有效
     */
    private Boolean isEnabled;
}
