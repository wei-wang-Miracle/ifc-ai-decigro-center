package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.CustomerTagCategory;
import java.util.List;

/**
 * 标签分类服务接口
 * 功能: 定义分类管理的业务方法
 */
public interface CustomerTagCategoryService {

    /**
     * 获取完整的分类树
     * 
     * 返回: 树形结构的分类列表，根节点的 parentId = 0
     */
    List<CustomerTagCategory> getTree();

    /**
     * 获取所有分类的扁平列表
     * 
     * 返回: 所有分类记录，不包含层级关系
     */
    List<CustomerTagCategory> list();

    /**
     * 递归获取某分类及其所有子孙分类的ID列表
     * 
     * 参数: categoryId 起始分类ID
     * 返回: 包含该分类及所有后代分类的ID集合
     */
    List<Long> getDescendantIds(Long categoryId);

    /**
     * 新增或更新分类
     * 
     * 参数: category 分类实体
     * - 当 id 为空时执行新增
     * - 当 id 不为空时执行更新
     */
    void saveOrUpdate(CustomerTagCategory category);

    /**
     * 删除分类
     * 
     * 参数: id 分类ID
     * 注意: 如果存在子分类或关联标签，将抛出业务异常
     */
    void deleteById(Long id);
}
