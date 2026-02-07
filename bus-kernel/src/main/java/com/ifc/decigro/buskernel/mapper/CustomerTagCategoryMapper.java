package com.ifc.decigro.buskernel.mapper;

import com.ifc.decigro.buskernel.entity.CustomerTagCategory;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 标签分类Mapper接口
 * 功能: 继承 MyBatis-Flex 的 BaseMapper，自动获得基础CRUD能力
 * 
 * BaseMapper 提供的方法包括:
 * - insert(entity): 插入单条记录
 * - insertBatch(list): 批量插入
 * - deleteById(id): 根据主键删除
 * - update(entity): 更新记录
 * - selectAll(): 查询所有记录
 * - selectOneById(id): 根据主键查询
 */
@Mapper
public interface CustomerTagCategoryMapper extends BaseMapper<CustomerTagCategory> {
}
