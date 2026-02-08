package com.ifc.decigro.buskernel.mapper;

import com.ifc.decigro.buskernel.entity.ToolCard;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * MAS 工具卡片 Mapper 接口
 * 功能: 继承 MyBatis-Flex 的 BaseMapper，自动获得基础 CRUD 能力
 * 
 * 注意: ToolCard 使用 String 类型主键 (toolName)
 * selectOneById / deleteById 等方法接收 String 参数
 */
@Mapper
public interface ToolCardMapper extends BaseMapper<ToolCard> {
}
