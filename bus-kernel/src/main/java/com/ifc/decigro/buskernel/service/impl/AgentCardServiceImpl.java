package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.AgentCard;
import com.ifc.decigro.buskernel.entity.ToolCard;
import com.ifc.decigro.buskernel.entity.vo.AgentCardSummaryVO;
import com.ifc.decigro.buskernel.mapper.AgentCardMapper;
import com.ifc.decigro.buskernel.mapper.ToolCardMapper;
import com.ifc.decigro.buskernel.service.AgentCardService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.stream.Collectors;

import static com.ifc.decigro.buskernel.entity.table.AgentCardTableDef.AGENT_CARD;
import static com.ifc.decigro.buskernel.entity.table.ToolCardTableDef.TOOL_CARD;

/**
 * MAS 智能体卡片服务实现类 (V2)
 */
@Service
public class AgentCardServiceImpl implements AgentCardService {

    @Autowired
    private AgentCardMapper agentCardMapper;

    @Autowired
    private ToolCardMapper toolCardMapper;

    @Override
    public Page<AgentCard> page(String keyword, String tag, int pageNum, int pageSize) {
        QueryWrapper queryWrapper = QueryWrapper.create();

        if (StringUtils.hasText(keyword)) {
            queryWrapper.and(AGENT_CARD.AGENT_NAME.like(keyword)
                    .or(AGENT_CARD.AGENT_ALIAS.like(keyword))
                    .or(AGENT_CARD.AGENT_DESCRIPTION.like(keyword)));
        }

        if (StringUtils.hasText(tag)) {
            queryWrapper.and("agent_tags @> '" + tag + "'");
        }

        queryWrapper.orderBy(AGENT_CARD.UPDATE_TIME.desc());

        return agentCardMapper.paginate(Page.of(pageNum, pageSize), queryWrapper);
    }

    @Override
    public AgentCard getByName(String agentName) {
        return agentCardMapper.selectOneById(agentName);
    }

    @Override
    public void saveOrUpdate(AgentCard agentCard) {
        // 第一步：如果是新增（检查主键是否存在）
        AgentCard existing = agentCardMapper.selectOneById(agentCard.getAgentName());

        if (existing == null) {
            agentCardMapper.insert(agentCard);
        } else {
            agentCardMapper.update(agentCard);
        }
    }

    @Override
    public void deleteByName(String agentName) {
        agentCardMapper.deleteById(agentName);
    }

    @Override
    public void updateOnlineStatus(String agentName, boolean isOnline) {
        AgentCard agentCard = agentCardMapper.selectOneById(agentName);
        if (agentCard == null) {
            throw new RuntimeException("智能体不存在: " + agentName);
        }
        agentCard.setIsOnline(isOnline);
        agentCardMapper.update(agentCard);
    }

    @Override
    public boolean existsByAgentName(String agentName) {
        return agentCardMapper.selectOneById(agentName) != null;
    }

    @Override
    public List<String> getAvailableTools() {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .where(TOOL_CARD.IS_ONLINE.eq(true))
                .orderBy(TOOL_CARD.TOOL_NAME.asc());

        List<ToolCard> tools = toolCardMapper.selectListByQuery(queryWrapper);
        return tools.stream().map(ToolCard::getToolName).collect(Collectors.toList());
    }

    @Override
    public List<AgentCardSummaryVO> getAvailableAgents() {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .select(AGENT_CARD.AGENT_NAME, AGENT_CARD.AGENT_ALIAS, AGENT_CARD.AGENT_DESCRIPTION,
                        AGENT_CARD.AGENT_TAGS, AGENT_CARD.REQUIRE_REVIEW)
                .from(AGENT_CARD)
                .where(AGENT_CARD.IS_ONLINE.eq(true));

        return agentCardMapper.selectListByQueryAs(queryWrapper, AgentCardSummaryVO.class);
    }

    @Override
    public AgentCard getAgentDetail(String agentName) {
        AgentCard agentCard = agentCardMapper.selectOneById(agentName);
        if (agentCard == null) {
            throw new RuntimeException("智能体不存在: " + agentName);
        }
        if (Boolean.FALSE.equals(agentCard.getIsOnline())) {
            throw new RuntimeException("智能体未上线: " + agentName);
        }
        return agentCard;
    }
}
