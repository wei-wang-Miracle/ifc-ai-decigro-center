package com.ifc.decigro.buskernel.mapper;

import com.ifc.decigro.buskernel.entity.AiChatTraceIndex;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;

/**
 * AI 全链路审计宽表 Mapper 接口
 * 功能: 继承 MyBatis-Flex 的 BaseMapper，自动获得基础 CRUD 能力
 *
 * 注意: AiChatTraceIndex 使用 String 类型主键 (traceId)
 */
@Mapper
public interface AiChatTraceIndexMapper extends BaseMapper<AiChatTraceIndex> {
}
