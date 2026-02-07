package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.ToolCard;
import com.ifc.decigro.buskernel.mapper.ToolCardMapper;
import com.ifc.decigro.buskernel.service.ToolCardService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import static com.ifc.decigro.buskernel.entity.table.ToolCardTableDef.TOOL_CARD;

/**
 * MAS 工具卡片服务实现类
 * 功能: 实现工具元数据的 CRUD 和业务逻辑
 */
@Service
public class ToolCardServiceImpl implements ToolCardService {

    @Autowired
    private ToolCardMapper toolCardMapper;

    /**
     * 分页查询工具列表
     * 支持按关键字和标签筛选
     */
    @Override
    public Page<ToolCard> page(String keyword, String tag, int pageNum, int pageSize) {
        // 第一步：构建查询条件
        QueryWrapper queryWrapper = QueryWrapper.create();

        // 第二步：添加关键字模糊匹配（名称或描述）
        if (StringUtils.hasText(keyword)) {
            queryWrapper.and(TOOL_CARD.TOOL_NAME.like(keyword)
                    .or(TOOL_CARD.TOOL_DESCRIPTION.like(keyword)));
        }

        // 第三步：添加标签筛选（PostgreSQL 数组包含查询）
        // 注意：使用原生 SQL 表达式处理 TEXT[] 类型的 @> 操作
        if (StringUtils.hasText(tag)) {
            queryWrapper.and("tool_tags @> ARRAY['" + tag + "']::text[]");
        }

        // 第四步：按更新时间倒序排列
        queryWrapper.orderBy(TOOL_CARD.UPDATE_TIME.desc());

        // 第五步：执行分页查询
        return toolCardMapper.paginate(Page.of(pageNum, pageSize), queryWrapper);
    }

    /**
     * 根据 ID 查询工具详情
     */
    @Override
    public ToolCard getById(Long id) {
        return toolCardMapper.selectOneById(id);
    }

    /**
     * 新增或更新工具
     * 包含工具名称唯一性校验
     */
    @Override
    public void saveOrUpdate(ToolCard toolCard) {
        // 第一步：校验 toolName 唯一性
        if (existsByToolName(toolCard.getToolName(), toolCard.getId())) {
            throw new RuntimeException("工具名称 '" + toolCard.getToolName() + "' 已存在");
        }

        // 第二步：判断新增还是更新
        if (toolCard.getId() == null) {
            // 新增操作
            toolCardMapper.insert(toolCard);
        } else {
            // 更新操作
            toolCardMapper.update(toolCard);
        }
    }

    /**
     * 删除工具
     */
    @Override
    public void deleteById(Long id) {
        toolCardMapper.deleteById(id);
    }

    /**
     * 更新工具上线状态
     */
    @Override
    public void updateOnlineStatus(Long id, boolean isOnline) {
        // 第一步：获取现有记录
        ToolCard toolCard = toolCardMapper.selectOneById(id);
        if (toolCard == null) {
            throw new RuntimeException("工具不存在: " + id);
        }

        // 第二步：更新状态
        toolCard.setIsOnline(isOnline);
        toolCardMapper.update(toolCard);
    }

    /**
     * 检查工具名称是否已存在
     */
    @Override
    public boolean existsByToolName(String toolName, Long excludeId) {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .where(TOOL_CARD.TOOL_NAME.eq(toolName));

        // 编辑时排除自身
        if (excludeId != null) {
            queryWrapper.and(TOOL_CARD.ID.ne(excludeId));
        }

        return toolCardMapper.selectCountByQuery(queryWrapper) > 0;
    }
}
