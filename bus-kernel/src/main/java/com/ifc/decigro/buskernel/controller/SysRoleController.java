package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.entity.SysRole;
import com.ifc.decigro.buskernel.service.SysRoleService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sys/role")
public class SysRoleController {

    @Autowired
    private SysRoleService roleService;

    @GetMapping
    public List<SysRole> list() {
        return roleService.list();
    }

    @PostMapping
    public void save(@RequestBody SysRole role) {
        roleService.saveOrUpdate(role);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        roleService.deleteById(id);
    }
}
