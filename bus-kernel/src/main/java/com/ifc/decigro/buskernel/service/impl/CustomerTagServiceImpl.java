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
import java.util.HashMap;
import java.util.stream.Collectors;
import com.ifc.decigro.buskernel.dto.CustomerTagDto;
import com.ifc.decigro.buskernel.entity.CustomerTagEnum;
import com.ifc.decigro.buskernel.mapper.CustomerTagEnumMapper;

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

    @Autowired
    private CustomerTagEnumMapper enumMapper;

    /**
     * 分页查询标签
     * 支持按分类过滤（包含子分类）和关键字搜索
     */
    /**
     * 查询所有标签 (AI Tool 专用)
     */
    @Override
    public List<CustomerTagDto> listAllForTool() {
        // 1. 查询所有基础数据 (一次性查出避免 N+1)
        List<CustomerTag> tags = tagMapper.selectAll();
        List<CustomerTagCategory> categories = categoryMapper.selectAll();
        List<CustomerTagEnum> enums = enumMapper.selectAll();

        // 2. 构建数据映射
        Map<Long, CustomerTagCategory> categoryMap = categories.stream()
                .collect(Collectors.toMap(CustomerTagCategory::getId, c -> c));

        Map<String, List<CustomerTagEnum>> enumsMap = enums.stream()
                .collect(Collectors.groupingBy(CustomerTagEnum::getTagField));

        // 3. 转换为 DTO
        return tags.stream().map(tag -> convertToDto(tag, categoryMap, enumsMap))
                .collect(Collectors.toList());
    }

    /**
     * 转换为 DTO 并填充扩展信息
     */
    private CustomerTagDto convertToDto(CustomerTag tag,
            Map<Long, CustomerTagCategory> categoryMap,
            Map<String, List<CustomerTagEnum>> enumsMap) {
        CustomerTagDto dto = new CustomerTagDto();
        dto.setTagField(tag.getTagField());
        dto.setTagTable(tag.getTagTable());
        dto.setTagName(tag.getTagName());
        dto.setTagDesc(tag.getTagDesc());
        dto.setValueType(tag.getValueType());

        // 解析一级分类名称
        String rootCategoryName = findRootCategoryName(tag.getCategoryId(), categoryMap);
        dto.setCategoryName(rootCategoryName);

        // 如果是枚举类型，填充枚举值
        if ("enum".equalsIgnoreCase(tag.getValueType())) {
            List<CustomerTagEnum> tagEnums = enumsMap.get(tag.getTagField());
            if (tagEnums != null && !tagEnums.isEmpty()) {
                List<Map<String, String>> enumList = tagEnums.stream().map(e -> {
                    Map<String, String> m = new HashMap<>();
                    m.put("enum_code", e.getEnumCode());
                    m.put("enum_name", e.getEnumName());
                    return m;
                }).collect(Collectors.toList());
                dto.setTagEnums(enumList);
            }
        }
        return dto;
    }

    /**
     * 递归查找一级分类名称
     */
    private String findRootCategoryName(Long categoryId, Map<Long, CustomerTagCategory> map) {
        if (categoryId == null || !map.containsKey(categoryId)) {
            return "未分类";
        }

        CustomerTagCategory current = map.get(categoryId);
        int safetyCounter = 0; // 防止数据异常导致死循环

        // 向上溯源直到 parentId 为 0 (根节点) 或 null
        while (current.getParentId() != null && current.getParentId() != 0 && safetyCounter++ < 20) {
            CustomerTagCategory parent = map.get(current.getParentId());
            if (parent == null)
                break;
            current = parent;
        }

        return current.getName();
    }

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
