package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.SysRole;
import com.ifc.decigro.buskernel.service.SysRoleService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 角色管理控制器
 */
@RestController
@RequestMapping("/api/sys/role")
public class SysRoleController {

    @Autowired
    private SysRoleService roleService;

    /**
     * 获取角色列表
     */
    @GetMapping
    public Result<List<SysRole>> list() {
        return Result.success(roleService.list());
    }

    /**
     * 保存或更新角色
     */
    @PostMapping
    public Result<Void> save(@RequestBody SysRole role) {
        roleService.saveOrUpdate(role);
        return Result.success();
    }

    /**
     * 删除角色
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        roleService.deleteById(id);
        return Result.success();
    }
}
