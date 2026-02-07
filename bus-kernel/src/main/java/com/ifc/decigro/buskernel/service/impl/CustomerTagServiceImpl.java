package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.CustomerTag;
import com.ifc.decigro.buskernel.entity.CustomerTagCategory;
import com.ifc.decigro.buskernel.mapper.CustomerTagMapper;
import com.ifc.decigro.buskernel.mapper.CustomerTagCategoryMapper;
import com.ifc.decigro.buskernel.service.CustomerTagService;
import com.ifc.decigro.buskernel.service.CustomerTagCategoryService;
import com.ifc.decigro.buskernel.service.CustomerTagEnumService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import cn.hutool.core.util.StrUtil;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 客户标签服务实现类
 * 功能: 实现标签的分页查询、新增更新、级联删除等业务逻辑
 */
@Service
public class CustomerTagServiceImpl implements CustomerTagService {

    @Autowired
    private CustomerTagMapper tagMapper;

    @Autowired
    private CustomerTagCategoryMapper categoryMapper;

    @Autowired
    private CustomerTagCategoryService categoryService;

    @Autowired
    private CustomerTagEnumService enumService;

    /**
     * 分页查询标签
     * 支持按分类过滤（包含子分类）和关键字搜索
     */
    @Override
    public Page<CustomerTag> page(Long categoryId, String keyword, int pageNum, int pageSize) {
        QueryWrapper query = QueryWrapper.create();

        // 条件1：按分类过滤（包含所有子孙分类）
        if (categoryId != null && categoryId > 0) {
            List<Long> categoryIds = categoryService.getDescendantIds(categoryId);
            query.where("category_id IN (" +
                    categoryIds.stream().map(String::valueOf).collect(Collectors.joining(",")) + ")");
        }

        // 条件2：关键字模糊匹配
        if (StrUtil.isNotBlank(keyword)) {
            query.and("(tag_name LIKE ? OR tag_field LIKE ?)",
                    "%" + keyword + "%", "%" + keyword + "%");
        }

        // 排序
        query.orderBy("sort_index", true);

        // 执行分页查询
        Page<CustomerTag> page = tagMapper.paginate(Page.of(pageNum, pageSize), query);

        // 回填分类名称（用于前端展示）
        fillCategoryNames(page.getRecords());

        return page;
    }

    /**
     * 批量填充分类名称
     */
    private void fillCategoryNames(List<CustomerTag> tags) {
        if (tags == null || tags.isEmpty()) {
            return;
        }
        // 收集所有分类ID
        List<Long> categoryIds = tags.stream()
                .map(CustomerTag::getCategoryId)
                .distinct()
                .collect(Collectors.toList());

        // 批量查询分类
        List<CustomerTagCategory> categories = categoryMapper.selectListByIds(categoryIds);
        Map<Long, String> categoryNameMap = categories.stream()
                .collect(Collectors.toMap(
                        CustomerTagCategory::getId,
                        CustomerTagCategory::getName));

        // 设置分类名称
        for (CustomerTag tag : tags) {
            tag.setCategoryName(categoryNameMap.get(tag.getCategoryId()));
        }
    }

    @Override
    public CustomerTag getByField(String tagField) {
        return tagMapper.selectOneById(tagField);
    }

    @Override
    public void saveOrUpdate(CustomerTag tag) {
        // 检查是否已存在
        CustomerTag existing = tagMapper.selectOneById(tag.getTagField());
        if (existing == null) {
            // 新增
            if (tag.getSortIndex() == null) {
                tag.setSortIndex(0);
            }
            tagMapper.insert(tag);
        } else {
            // 更新
            tagMapper.update(tag);
        }
    }

    /**
     * 删除标签（级联删除枚举值）
     */
    @Override
    @Transactional
    public void deleteByField(String tagField) {
        // 第一步：删除关联的枚举值
        enumService.deleteByTagField(tagField);

        // 第二步：删除标签本身
        tagMapper.deleteById(tagField);
    }

    /**
     * 批量迁移标签实现
     * 使用 MyBatis-Flex 的 updateChain 进行批量更新
     */
    @Override
    @Transactional
    public void migrateTags(Long sourceCategoryId, Long targetCategoryId) {
        if (sourceCategoryId == null || targetCategoryId == null) {
            return;
        }

        // 创建更新对象，只设置要修改的字段
        CustomerTag updater = new CustomerTag();
        updater.setCategoryId(targetCategoryId);

        // 构建查询条件并更新数据
        QueryWrapper query = QueryWrapper.create()
                .where("category_id = ?", sourceCategoryId);

        tagMapper.updateByQuery(updater, query);
    }
}
