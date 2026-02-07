package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.CustomerTag;
import com.mybatisflex.core.paginate.Page;

/**
 * 客户标签服务接口
 * 功能: 定义标签主数据管理的业务方法
 */
public interface CustomerTagService {

    /**
     * 分页查询标签列表
     * 
     * 参数: categoryId 分类ID（可选），传入时查询该分类及子分类下的标签
     * 参数: keyword 关键字（可选），模糊匹配标签名称或字段名
     * 参数: pageNum 页码，从1开始
     * 参数: pageSize 每页条数
     * 返回: 分页结果
     */
    Page<CustomerTag> page(Long categoryId, String keyword, int pageNum, int pageSize);

    /**
     * 根据主键查询标签
     * 
     * 参数: tagField 标签字段名（主键）
     * 返回: 标签实体，不存在时返回null
     */
    CustomerTag getByField(String tagField);

    /**
     * 新增或更新标签
     * 
     * 参数: tag 标签实体
     * - 新增时检查 tagField 是否已存在
     * - 更新时根据 tagField 匹配记录
     */
    void saveOrUpdate(CustomerTag tag);

    /**
     * 删除标签
     * 
     * 参数: tagField 标签字段名（主键）
     * 注意: 会级联删除关联的枚举值记录
     */
    void deleteByField(String tagField);

    /**
     * 批量迁移标签
     * 
     * 功能: 将源分类下的所有标签全量迁移到目标分类
     * 参数: sourceCategoryId 源分类ID
     * 参数: targetCategoryId 目标分类ID
     */
    void migrateTags(Long sourceCategoryId, Long targetCategoryId);
}
