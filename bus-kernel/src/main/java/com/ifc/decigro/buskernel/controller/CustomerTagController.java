package com.ifc.decigro.buskernel.controller;

import com.ifc.decigro.buskernel.common.api.Result;
import com.ifc.decigro.buskernel.entity.CustomerTag;
import com.ifc.decigro.buskernel.service.CustomerTagService;
import com.mybatisflex.core.paginate.Page;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import com.ifc.decigro.buskernel.dto.CustomerTagDto;
import com.ifc.decigro.buskernel.common.annotation.ToolCard;
import java.util.List;

/**
 * 客户标签管理控制器
 * 功能: 提供标签主数据的增删改查API
 */
@RestController
@RequestMapping("/tag")
public class CustomerTagController {

    @Autowired
    private CustomerTagService tagService;

    /**
     * 获取所有标签列表
     * 返回: 包含所有客户标签的完整列表
     */
    @ToolCard(tool_name = "get_all_customer_tags", summary = "获取所有客户标签", description = "获取系统中定义的所有客户标签列表。通常用于提取标签元数据或进行标签匹配。返回结果包含标签字段名、名称及所属分类。")
    @PostMapping("/get_all_customer_tags")
    public Result<List<CustomerTagDto>> get_all_customer_tags() {
        return Result.success(tagService.listAllForTool());
    }

    /**
     * 分页查询标签
     * 
     * 参数说明:
     * - categoryId: 分类ID（可选），传入时查询该分类及子分类的标签
     * - keyword: 关键字（可选），模糊搜索标签名称或字段名
     * - page: 页码，默认1
     * - size: 每页条数，默认20
     */
    @GetMapping("/page")
    public Result<Page<CustomerTag>> page(
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return Result.success(tagService.page(categoryId, keyword, page, size));
    }

    /**
     * 根据字段名获取标签详情
     */
    @GetMapping("/detail/{tagField}")
    public Result<CustomerTag> getByField(@PathVariable String tagField) {
        return Result.success(tagService.getByField(tagField));
    }

    /**
     * 新增或更新标签
     */
    @PostMapping("/save")
    public Result<Void> save(@RequestBody CustomerTag tag) {
        tagService.saveOrUpdate(tag);
        return Result.success();
    }

    /**
     * 删除标签
     * 会级联删除关联的枚举值
     */
    @DeleteMapping("/remove/{tagField}")
    public Result<Void> delete(@PathVariable String tagField) {
        tagService.deleteByField(tagField);
        return Result.success();
    }

    /**
     * 批量迁移分类下的标签
     * 
     * 参数说明:
     * - sourceId: 迁出的分类ID
     * - targetId: 迁入的分类ID
     */
    @PostMapping("/migrate")
    public Result<Void> migrate(
            @RequestParam Long sourceId,
            @RequestParam Long targetId) {
        tagService.migrateTags(sourceId, targetId);
        return Result.success();
    }
}
