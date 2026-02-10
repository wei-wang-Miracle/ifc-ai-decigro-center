package com.ifc.decigro.buskernel.dto;

import lombok.Data;

/**
 * 用户个人资料更新请求对象
 */
@Data
public class ProfileUpdateRequest {
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
}
