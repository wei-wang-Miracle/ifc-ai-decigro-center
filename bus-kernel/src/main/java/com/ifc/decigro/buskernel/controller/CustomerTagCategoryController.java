package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.CustomerTagCategory;
import com.ifc.decigro.buskernel.service.CustomerTagCategoryService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 标签分类管理控制器
 * 功能: 提供分类树的增删改查API
 */
@RestController
@RequestMapping("/api/tag-categories")
public class CustomerTagCategoryController {

    @Autowired
    private CustomerTagCategoryService categoryService;

    /**
     * 获取分类树
     * 返回嵌套的树形结构JSON
     */
    @GetMapping("/tree")
    public Result<List<CustomerTagCategory>> getTree() {
        return Result.success(categoryService.getTree());
    }

    /**
     * 获取分类扁平列表
     * 用于下拉选择等场景
     */
    @GetMapping
    public Result<List<CustomerTagCategory>> list() {
        return Result.success(categoryService.list());
    }

    /**
     * 新增或更新分类
     */
    @PostMapping
    public Result<Void> save(@RequestBody CustomerTagCategory category) {
        categoryService.saveOrUpdate(category);
        return Result.success();
    }

    /**
     * 删除分类
     * 如存在子分类或关联标签，返回错误信息
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        try {
            categoryService.deleteById(id);
            return Result.success();
        } catch (RuntimeException e) {
            return Result.fail(e.getMessage());
        }
    }
}
