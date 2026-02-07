package com.ifc.decigro.buskernel.mapper;

import com.ifc.decigro.buskernel.entity.CustomerTag;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * 客户标签Mapper接口
 * 功能: 继承 MyBatis-Flex 的 BaseMapper，自动获得基础CRUD能力
 * 
 * 注意: CustomerTag 使用 String 类型主键 (tagField)
 * 因此 selectOneById / deleteById 等方法接收 String 参数
 */
@Mapper
public interface CustomerTagMapper extends BaseMapper<CustomerTag> {
}
