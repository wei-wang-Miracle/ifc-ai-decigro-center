package com.ifc.decigro.buskernel.dto;

import lombok.Data;

/**
 * 修改密码请求对象
 */
@Data
public class UpdatePasswordRequest {
    /**
     * 旧密码
     */
    private String oldPassword;

    /**
     * 新密码
     */
    private String newPassword;
}
