package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.CustomerTagCategory;
import com.ifc.decigro.buskernel.mapper.CustomerTagCategoryMapper;
import com.ifc.decigro.buskernel.mapper.CustomerTagMapper;
import com.ifc.decigro.buskernel.service.CustomerTagCategoryService;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 标签分类服务实现类
 * 功能: 实现分类树构建、级联查询、增删改查等业务逻辑
 */
@Service
public class CustomerTagCategoryServiceImpl implements CustomerTagCategoryService {

    @Autowired
    private CustomerTagCategoryMapper categoryMapper;

    @Autowired
    private CustomerTagMapper tagMapper;

    /**
     * 获取完整分类树
     * 实现思路:
     * 1. 查询所有分类记录
     * 2. 按 parentId 分组
     * 3. 递归构建树形结构
     */
    @Override
    public List<CustomerTagCategory> getTree() {
        // 第一步：获取所有分类
        List<CustomerTagCategory> allCategories = categoryMapper.selectAll();

        // 第二步：按 parentId 分组，便于快速查找子节点
        Map<Long, List<CustomerTagCategory>> parentIdMap = allCategories.stream()
                .collect(Collectors.groupingBy(
                        c -> c.getParentId() == null ? 0L : c.getParentId()));

        // 第三步：递归构建树，从根节点(parentId=0)开始
        return buildTree(0L, parentIdMap);
    }

    /**
     * 递归构建树形结构
     * 
     * 参数: parentId 当前层级的父ID
     * 参数: parentIdMap 按父ID分组的分类Map
     * 返回: 该父节点下的所有子节点（包含嵌套的孙节点）
     */
    private List<CustomerTagCategory> buildTree(Long parentId, Map<Long, List<CustomerTagCategory>> parentIdMap) {
        List<CustomerTagCategory> children = parentIdMap.get(parentId);
        if (children == null) {
            return new ArrayList<>();
        }
        // 为每个子节点递归设置其子节点
        for (CustomerTagCategory child : children) {
            child.setChildren(buildTree(child.getId(), parentIdMap));
        }
        return children;
    }

    @Override
    public List<CustomerTagCategory> list() {
        // 返回扁平列表，按 sortIndex 排序
        return categoryMapper.selectListByQuery(
                QueryWrapper.create()
                        .orderBy("sort_index", true));
    }

    /**
     * 递归获取某分类及其所有子孙分类的ID
     * 用于支持"点击分类 → 展示该分类及子分类下所有标签"的需求
     */
    @Override
    public List<Long> getDescendantIds(Long categoryId) {
        List<Long> result = new ArrayList<>();
        result.add(categoryId);

        // 使用递归方式收集所有子孙ID
        collectDescendantIds(categoryId, result);
        return result;
    }

    /**
     * 递归收集子孙分类ID
     */
    private void collectDescendantIds(Long parentId, List<Long> result) {
        // 查询直接子分类
        List<CustomerTagCategory> children = categoryMapper.selectListByQuery(
                QueryWrapper.create()
                        .where("parent_id = ?", parentId));
        for (CustomerTagCategory child : children) {
            result.add(child.getId());
            // 递归收集孙子分类
            collectDescendantIds(child.getId(), result);
        }
    }

    @Override
    public void saveOrUpdate(CustomerTagCategory category) {
        if (category.getId() == null) {
            // 新增：设置默认值
            if (category.getParentId() == null) {
                category.setParentId(0L);
            }
            if (category.getSortIndex() == null) {
                category.setSortIndex(1);
            }
            categoryMapper.insert(category);
        } else {
            // 更新
            categoryMapper.update(category);
        }
    }

    /**
     * 删除分类
     * 业务校验：
     * 1. 如果存在子分类，禁止删除
     * 2. 如果存在关联标签，禁止删除
     */
    @Override
    public void deleteById(Long id) {
        // 校验1：是否存在子分类
        long childCount = categoryMapper.selectCountByQuery(
                QueryWrapper.create()
                        .where("parent_id = ?", id));
        if (childCount > 0) {
            throw new RuntimeException("该分类下存在子分类，请先删除子分类");
        }

        // 校验2：是否存在关联标签
        long tagCount = tagMapper.selectCountByQuery(
                QueryWrapper.create()
                        .where("category_id = ?", id));
        if (tagCount > 0) {
            throw new RuntimeException("该分类下存在关联标签，请先删除或移动标签");
        }

        // 执行删除
        categoryMapper.deleteById(id);
    }
}
