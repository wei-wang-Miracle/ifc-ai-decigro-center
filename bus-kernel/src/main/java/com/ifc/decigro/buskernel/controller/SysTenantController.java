package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.entity.SysTenant;
import com.ifc.decigro.buskernel.service.SysTenantService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sys/tenant")
public class SysTenantController {

    @Autowired
    private SysTenantService tenantService;

    @GetMapping
    public List<SysTenant> list() {
        return tenantService.list();
    }

    @PostMapping
    public void save(@RequestBody SysTenant tenant) {
        tenantService.saveOrUpdate(tenant);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable String id) {
        tenantService.deleteById(id);
    }
}
