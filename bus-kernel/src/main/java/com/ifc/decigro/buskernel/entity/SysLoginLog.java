package com.ifc.decigro.buskernel.entity;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.KeyType;
import com.mybatisflex.annotation.Table;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.time.LocalDateTime;

/**
 * 用户登录日志表
 * 满足 4.4 监控需求
 */
@Data
@EqualsAndHashCode(callSuper = true)
@Table("sys_login_log")
public class SysLoginLog extends BaseEntity {

    /**
     * Token 签名 (主键)
     */
    @Id(keyType = KeyType.None)
    private String tokenSign;

    /**
     * 用户名
     */
    private String username;

    /**
     * 登录 IP
     */
    private String ipAddress;

    /**
     * 登录时间
     */
    private LocalDateTime loginTime;

    /**
     * 租户编码
     * 日志也需要隔离
     */
    @Column(tenantId = true)
    private String tenantCode;

    /**
     * 登录状态 (1:启用, 0:禁用)，踢下线
     */
    private Boolean isEnabled;
}
