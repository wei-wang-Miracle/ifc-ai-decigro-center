package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.entity.SysDept;
import com.ifc.decigro.buskernel.service.SysDeptService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sys/dept")
public class SysDeptController {

    @Autowired
    private SysDeptService deptService;

    @GetMapping
    public List<SysDept> list() {
        return deptService.list();
    }

    @PostMapping
    public void save(@RequestBody SysDept dept) {
        deptService.saveOrUpdate(dept);
    }

    @DeleteMapping("/{id}")
    public void delete(@PathVariable Long id) {
        deptService.deleteById(id);
    }

    @GetMapping("/tree")
    public List<SysDept> tree() {
        return deptService.tree();
    }
}
