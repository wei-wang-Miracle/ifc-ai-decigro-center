package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.SysTenant;
import com.ifc.decigro.buskernel.service.SysTenantService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 租户管理控制器
 */
@RestController
@RequestMapping("/tenant")
public class SysTenantController {

    @Autowired
    private SysTenantService tenantService;

    /**
     * 获取租户列表
     */
    @GetMapping("/list")
    public Result<List<SysTenant>> list() {
        return Result.success(tenantService.list());
    }

    /**
     * 保存或更新租户
     */
    @PostMapping("/save")
    public Result<Void> save(@RequestBody SysTenant tenant) {
        tenantService.saveOrUpdate(tenant);
        return Result.success();
    }

    /**
     * 删除租户
     */
    @DeleteMapping("/remove/{id}")
    public Result<Void> delete(@PathVariable String id) {
        tenantService.deleteById(id);
        return Result.success();
    }
}
