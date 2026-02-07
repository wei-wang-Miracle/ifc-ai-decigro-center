package com.ifc.decigro.buskernel.mapper;

import com.ifc.decigro.buskernel.entity.CustomerTagEnum;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 标签枚举值Mapper接口
 * 功能: 继承 MyBatis-Flex 的 BaseMapper，自动获得基础CRUD能力
 * 
 * 该Mapper用于操作 customer_tag_enum 表
 * 存储枚举类型标签的可选值列表
 */
@Mapper
public interface CustomerTagEnumMapper extends BaseMapper<CustomerTagEnum> {
}
