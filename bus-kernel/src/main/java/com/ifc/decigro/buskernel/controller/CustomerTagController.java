package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.CustomerTag;
import com.ifc.decigro.buskernel.service.CustomerTagService;
import com.mybatisflex.core.paginate.Page;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

/**
 * 客户标签管理控制器
 * 功能: 提供标签主数据的增删改查API
 */
@RestController
@RequestMapping("/api/tags")
public class CustomerTagController {

    @Autowired
    private CustomerTagService tagService;

    /**
     * 分页查询标签
     * 
     * 参数说明:
     * - categoryId: 分类ID（可选），传入时查询该分类及子分类的标签
     * - keyword: 关键字（可选），模糊搜索标签名称或字段名
     * - page: 页码，默认1
     * - size: 每页条数，默认20
     */
    @GetMapping
    public Result<Page<CustomerTag>> page(
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int size) {
        return Result.success(tagService.page(categoryId, keyword, page, size));
    }

    /**
     * 根据字段名获取标签详情
     */
    @GetMapping("/{tagField}")
    public Result<CustomerTag> getByField(@PathVariable String tagField) {
        return Result.success(tagService.getByField(tagField));
    }

    /**
     * 新增或更新标签
     */
    @PostMapping
    public Result<Void> save(@RequestBody CustomerTag tag) {
        tagService.saveOrUpdate(tag);
        return Result.success();
    }

    /**
     * 删除标签
     * 会级联删除关联的枚举值
     */
    @DeleteMapping("/{tagField}")
    public Result<Void> delete(@PathVariable String tagField) {
        tagService.deleteByField(tagField);
        return Result.success();
    }
}
