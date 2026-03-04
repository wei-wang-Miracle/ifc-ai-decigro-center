package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.ToolCard;
import com.ifc.decigro.buskernel.entity.vo.ToolCardSummaryVO;
import com.ifc.decigro.buskernel.mapper.ToolCardMapper;
import com.ifc.decigro.buskernel.service.ToolCardService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;

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
     * 根据名称查询工具详情
     */
    @Override
    public ToolCard getById(String toolName) {
        return toolCardMapper.selectOneById(toolName);
    }

    /**
     * 新增或更新工具
     */
    @Override
    public void saveOrUpdate(ToolCard toolCard) {
        // 使用 toolName 作为主键
        ToolCard existing = getById(toolCard.getToolName());
        if (existing == null) {
            // 新增操作
            toolCardMapper.insert(toolCard);
        } else {
            // 更新操作
            // 由于 toolName 是主键也是更新标识，直接 update
            toolCardMapper.update(toolCard);
        }
    }

    /**
     * 删除工具
     */
    @Override
    public void deleteById(String toolName) {
        toolCardMapper.deleteById(toolName);
    }

    /**
     * 更新工具上线状态
     */
    @Override
    public void updateOnlineStatus(String toolName, boolean isOnline) {
        // 第一步：获取现有记录
        ToolCard toolCard = toolCardMapper.selectOneById(toolName);
        if (toolCard == null) {
            throw new RuntimeException("工具不存在: " + toolName);
        }

        // 第二步：更新状态
        toolCard.setIsOnline(isOnline);
        toolCardMapper.update(toolCard);
    }

    /**
     * 实现获取可用工具列表
     * 规则: isOnline = true
     * 注意: 不再按 toolPrivileges 过滤 —— public/protected 均返回摘要。
     * 权限控制由 Agent 的 boundTools 机制承担，未绑定的 protected 工具
     * 即使出现在摘要里，也不会被 Agent 调用。
     */
    @Override
    public List<ToolCardSummaryVO> getAvailableTools(String username) {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .select(TOOL_CARD.TOOL_NAME, TOOL_CARD.TOOL_ALIAS, TOOL_CARD.TOOL_DESCRIPTION, TOOL_CARD.TOOL_TAGS)
                .from(TOOL_CARD)
                .where(TOOL_CARD.IS_ONLINE.eq(true));

        return toolCardMapper.selectListByQueryAs(queryWrapper, ToolCardSummaryVO.class);
    }

    /**
     * 实现获取工具详情（含权限校验）
     */
    @Override
    public ToolCard getToolDetail(String toolName, String username) {
        ToolCard toolCard = toolCardMapper.selectOneById(toolName);
        if (toolCard == null) {
            throw new RuntimeException("工具不存在: " + toolName);
        }

        if (Boolean.FALSE.equals(toolCard.getIsOnline())) {
            throw new RuntimeException("工具未上线: " + toolName);
        }

        // 目前仅允许公开工具或通过 Agent 间接访问 (此处简化为仅校验上线状态)
        return toolCard;
    }

    /**
     * 检查工具名称是否已存在
     */
    @Override
    public boolean existsByToolName(String toolName) {
        return toolCardMapper.selectOneById(toolName) != null;
    }

    @Override
    public List<ToolCardSummaryVO> listAll() {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .select(TOOL_CARD.TOOL_NAME, TOOL_CARD.TOOL_ALIAS, TOOL_CARD.TOOL_DESCRIPTION, TOOL_CARD.TOOL_TAGS)
                .from(TOOL_CARD)
                .where(TOOL_CARD.IS_ONLINE.eq(true))
                .orderBy(TOOL_CARD.TOOL_ALIAS.asc(), TOOL_CARD.TOOL_NAME.asc());
        return toolCardMapper.selectListByQueryAs(queryWrapper, ToolCardSummaryVO.class);
    }
}
