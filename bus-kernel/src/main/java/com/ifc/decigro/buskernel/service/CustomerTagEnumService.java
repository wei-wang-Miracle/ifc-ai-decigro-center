package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.CustomerTagEnum;
import java.util.List;

/**
 * 标签枚举值服务接口
 * 功能: 定义枚举值管理的业务方法
 */
public interface CustomerTagEnumService {

    /**
     * 获取指定标签的枚举值列表
     * 
     * 参数: tagField 标签字段名
     * 返回: 该标签关联的所有枚举值
     */
    List<CustomerTagEnum> listByTagField(String tagField);

    /**
     * 新增或更新单个枚举值
     * 
     * 参数: enumItem 枚举值实体
     */
    void saveOrUpdate(CustomerTagEnum enumItem);

    /**
     * 删除单个枚举值
     * 
     * 参数: id 枚举值ID
     */
    void deleteById(Long id);

    /**
     * 批量保存枚举值
     * 先删除该标签的所有现有枚举值，再批量插入新值
     * 
     * 参数: tagField 标签字段名
     * 参数: items 枚举值列表
     */
    void batchSave(String tagField, List<CustomerTagEnum> items);

    /**
     * 删除指定标签的所有枚举值
     * 
     * 参数: tagField 标签字段名
     */
    void deleteByTagField(String tagField);
}
