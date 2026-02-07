package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.CustomerTagEnum;
import com.ifc.decigro.buskernel.service.CustomerTagEnumService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 标签枚举值管理控制器
 * 功能: 提供枚举值的增删改查API
 */
@RestController
@RequestMapping("/api/tag-enums")
public class CustomerTagEnumController {

    @Autowired
    private CustomerTagEnumService enumService;

    /**
     * 获取指定标签的枚举值列表
     */
    @GetMapping("/{tagField}")
    public Result<List<CustomerTagEnum>> list(@PathVariable String tagField) {
        return Result.success(enumService.listByTagField(tagField));
    }

    /**
     * 新增或更新单个枚举值
     */
    @PostMapping
    public Result<Void> save(@RequestBody CustomerTagEnum enumItem) {
        enumService.saveOrUpdate(enumItem);
        return Result.success();
    }

    /**
     * 批量保存枚举值
     * 替换指定标签的所有枚举值
     */
    @PostMapping("/batch/{tagField}")
    public Result<Void> batchSave(
            @PathVariable String tagField,
            @RequestBody List<CustomerTagEnum> items) {
        enumService.batchSave(tagField, items);
        return Result.success();
    }

    /**
     * 删除单个枚举值
     */
    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        enumService.deleteById(id);
        return Result.success();
    }
}
