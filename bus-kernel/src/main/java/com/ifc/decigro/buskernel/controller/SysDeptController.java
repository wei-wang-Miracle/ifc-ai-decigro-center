package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.SysDept;
import com.ifc.decigro.buskernel.service.SysDeptService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 部门管理控制器
 */
@RestController
@RequestMapping("/dept")
public class SysDeptController {

    @Autowired
    private SysDeptService deptService;

    /**
     * 获取部门列表
     */
    @GetMapping("/list")
    public Result<List<SysDept>> list() {
        return Result.success(deptService.list());
    }

    /**
     * 保存或更新部门
     */
    @PostMapping("/save")
    public Result<Void> save(@RequestBody SysDept dept) {
        deptService.saveOrUpdate(dept);
        return Result.success();
    }

    /**
     * 删除部门
     */
    @DeleteMapping("/remove/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        deptService.deleteById(id);
        return Result.success();
    }

    /**
     * 获取部门树结构
     */
    @GetMapping("/tree")
    public Result<List<SysDept>> tree() {
        return Result.success(deptService.tree());
    }
}
