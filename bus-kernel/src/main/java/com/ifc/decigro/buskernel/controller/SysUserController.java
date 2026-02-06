package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.common.context.UserContext;
import com.ifc.decigro.buskernel.entity.SysUser;
import com.ifc.decigro.buskernel.service.SysUserService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 用户管理控制器
 * 功能: 处理用户列表、增删改查及个人资料维护
 */
@Slf4j
@RestController
@RequestMapping("/api/sys/user")
public class SysUserController {

    @Autowired
    private SysUserService userService;

    /**
     * 查询用户列表
     * 返回: 统一响应格式包装的用户列表
     */
    @GetMapping
    public Result<List<SysUser>> list() {
        return Result.success(userService.list());
    }

    /**
     * 保存或更新用户
     * 参数: 用户实体信息
     * 返回: 成功标志
     */
    @PostMapping
    public Result<Void> save(@RequestBody SysUser user) {
        userService.saveOrUpdate(user);
        return Result.success();
    }

    /**
     * 删除用户
     * 参数: 用户 ID
     * 返回: 成功标志
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        userService.deleteById(id);
        return Result.success();
    }

    /**
     * 获取当前登录用户信息
     * 返回: 当前用户实体对象包装类
     */
    @GetMapping("/profile")
    public Result<SysUser> profile() {
        String username = UserContext.getUserName();
        return Result.success(userService.getByUsername(username));
    }

    /**
     * 更新当前登录用户信息
     * 参数: 待更新的用户信息
     * 返回: 成功标志
     */
    @PutMapping("/profile")
    public Result<Void> updateProfile(@RequestBody SysUser user) {
        String username = UserContext.getUserName();
        SysUser currentUser = userService.getByUsername(username);

        if (currentUser != null) {
            currentUser.setNickName(user.getNickName());
            currentUser.setGender(user.getGender());
            currentUser.setEmail(user.getEmail());
            currentUser.setPhone(user.getPhone());
            userService.saveOrUpdate(currentUser);
        }
        return Result.success();
    }

    /**
     * 修改当前登录用户密码
     * 参数: 包含 oldPassword 和 newPassword 的 Map
     * 返回: 成功标志
     */
    @PutMapping("/password")
    public Result<Void> updatePassword(@RequestBody Map<String, String> params) {
        String username = UserContext.getUserName();
        String oldPassword = params.get("oldPassword");
        String newPassword = params.get("newPassword");

        log.info("修改密码请求: username={}", username);
        userService.updatePassword(username, oldPassword, newPassword);
        return Result.success();
    }
}
