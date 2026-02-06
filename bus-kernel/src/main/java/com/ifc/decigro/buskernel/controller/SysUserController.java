package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.context.UserContext;
import com.ifc.decigro.buskernel.entity.SysUser;
import com.ifc.decigro.buskernel.service.SysUserService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/sys/user")
public class SysUserController {

    @Autowired
    private SysUserService userService;

    @GetMapping
    public List<SysUser> list() {
        return userService.list();
    }

    @PostMapping
    public void save(@RequestBody SysUser user) {
        userService.saveOrUpdate(user);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        userService.deleteById(id);
    }

    /**
     * 获取当前登录用户信息
     * 功能: 获取 UserContext 中当前用户的详细资料
     * 返回: 当前用户实体对象
     */
    @GetMapping("/profile")
    public SysUser profile() {
        String username = UserContext.getUserName();
        return userService.getByUsername(username);
    }

    /**
     * 更新当前登录用户信息
     * 功能: 允许用户修改昵称、性别、邮箱、电话等基本信息
     * 参数: 包含更新信息的用户对象
     */
    @PutMapping("/profile")
    public void updateProfile(@RequestBody SysUser user) {
        String username = UserContext.getUserName();
        SysUser currentUser = userService.getByUsername(username);

        if (currentUser != null) {
            currentUser.setNickName(user.getNickName());
            currentUser.setGender(user.getGender());
            currentUser.setEmail(user.getEmail());
            currentUser.setPhone(user.getPhone());
            userService.saveOrUpdate(currentUser);
        }
    }

    /**
     * 修改当前登录用户密码
     * 功能: 验证旧密码并更新为新密码
     * 参数: 包含 oldPassword 和 newPassword 的 Map
     */
    @PutMapping("/password")
    public void updatePassword(@RequestBody Map<String, String> params) {
        String username = UserContext.getUserName();
        String oldPassword = params.get("oldPassword");
        String newPassword = params.get("newPassword");

        log.info("修改密码尝试：username={}, oldPassword={}, newPassword={}", username, oldPassword, newPassword);

        if (username == null) {
            log.error("修改密码失败：未发现当前登录用户名");
            throw new RuntimeException("未登录或登录已过期");
        }

        userService.updatePassword(username, oldPassword, newPassword);
    }
}
