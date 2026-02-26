package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.SysUser;
import com.ifc.decigro.buskernel.entity.dto.LoginRequest;
import jakarta.servlet.http.HttpServletRequest;

import java.util.List;
import java.util.Map;
import com.ifc.decigro.buskernel.dto.ProfileUpdateRequest;

/**
 * 用户业务接口
 */
public interface SysUserService {

    /**
     * 用户登录
     */
    Map<String, Object> login(LoginRequest request, HttpServletRequest httpRequest);

    /**
     * 用户退出
     */
    void logout(String token);

    /**
     * 获取用户列表
     */
    List<SysUser> list();

    /**
     * 保存或更新用户
     */
    void saveOrUpdate(SysUser user);

    /**
     * 删除用户
     */
    void deleteById(Long id);

    /**
     * 根据用户名获取用户信息
     */
    SysUser getByUsername(String username);

    /**
     * 修改密码
     */
    void updatePassword(String username, String oldPassword, String newPassword);

    /**
     * 更新个人资料
     */
    void updateProfile(String username, ProfileUpdateRequest request);
}
