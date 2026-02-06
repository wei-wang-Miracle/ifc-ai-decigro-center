package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import com.mybatisflex.core.handler.Fastjson2TypeHandler;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 用户表
 * 系统的核心，承载记忆与当前职能
 */
@Data
@Table("sys_user")
public class SysUser implements Serializable {

    /**
     * 主键 ID
     */
    @Id(keyType = KeyType.Auto)
    private Long id;

    /**
     * 用户名 (全局唯一)
     */
    private String username;

    /**
     * 加密密码 (Symmetric Encrypted)
     */
    private String password;

    /**
     * 密码版本
     */
    private String passwordV;

    /**
     * 昵称
     */
    private String nickName;

    /**
     * 性别
     */
    private Integer gender;

    /**
     * 邮箱
     */
    private String email;

    /**
     * 电话
     */
    private String phone;

    /**
     * 头像路径
     */
    private String avatarPath;

    /**
     * 当前部门 ID
     */
    private Long deptId;

    /**
     * 当前角色 ID
     */
    private Long roleId;

    /**
     * 个性化工具 (覆盖角色配置)
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> toolList;

    /**
     * 账户状态 (1:启用, 0:禁用)
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
