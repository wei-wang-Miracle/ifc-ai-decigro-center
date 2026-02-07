package com.ifc.decigro.buskernel.mapper;

import com.ifc.decigro.buskernel.entity.AgentCard;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * MAS 智能体卡片 Mapper 接口
 * 功能: 继承 MyBatis-Flex 的 BaseMapper，自动获得基础 CRUD 能力
 * 
 * 注意: AgentCard 使用 Long 类型主键 (id)
 * selectOneById / deleteById 等方法接收 Long 参数
 */
@Mapper
public interface AgentCardMapper extends BaseMapper<AgentCard> {
}
