package com.ifc.decigro.buskernel.service.impl;

import com.ifc.decigro.buskernel.entity.AgentCard;
import com.ifc.decigro.buskernel.entity.SysRole;
import com.ifc.decigro.buskernel.entity.SysUser;
import com.ifc.decigro.buskernel.entity.ToolCard;
import com.ifc.decigro.buskernel.entity.vo.AgentCardSummaryVO;
import com.ifc.decigro.buskernel.mapper.AgentCardMapper;
import com.ifc.decigro.buskernel.mapper.ToolCardMapper;
import com.ifc.decigro.buskernel.service.AgentCardService;
import com.ifc.decigro.buskernel.service.SysRoleService;
import com.ifc.decigro.buskernel.service.SysUserService;
import com.mybatisflex.core.paginate.Page;
import com.mybatisflex.core.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
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

    @Autowired
    private SysUserService sysUserService;

    @Autowired
    private SysRoleService sysRoleService;

    @Override
    public Page<AgentCard> page(String keyword, String tag, String agentType, int pageNum, int pageSize) {
        QueryWrapper queryWrapper = QueryWrapper.create();

        if (StringUtils.hasText(keyword)) {
            queryWrapper.and(AGENT_CARD.AGENT_NAME.like(keyword)
                    .or(AGENT_CARD.AGENT_ALIAS.like(keyword))
                    .or(AGENT_CARD.AGENT_DESCRIPTION.like(keyword)));
        }

        if (StringUtils.hasText(tag)) {
            queryWrapper.and("agent_tags @> '" + tag + "'");
        }

        if (StringUtils.hasText(agentType)) {
            queryWrapper.and(AGENT_CARD.AGENT_TYPE.eq(agentType));
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
    public List<String> getAvailableExecutors() {
        QueryWrapper queryWrapper = QueryWrapper.create()
                .where(AGENT_CARD.AGENT_TYPE.eq("EXECUTOR"))
                .and(AGENT_CARD.IS_ONLINE.eq(true))
                .orderBy(AGENT_CARD.AGENT_NAME.asc());
        List<AgentCard> agents = agentCardMapper.selectListByQuery(queryWrapper);
        return agents.stream().map(AgentCard::getAgentName).collect(Collectors.toList());
    }

    @Override
    public List<AgentCard> getExecutorListByPlanner(String plannerName) {
        AgentCard planner = agentCardMapper.selectOneById(plannerName);
        if (planner == null || !"PLANNER".equals(planner.getAgentType())) {
            throw new RuntimeException("Planner不存在或类型不匹配: " + plannerName);
        }
        List<String> boundAgents = planner.getBoundAgents();
        if (boundAgents == null || boundAgents.isEmpty()) {
            return Collections.emptyList();
        }
        QueryWrapper queryWrapper = QueryWrapper.create()
                .where(AGENT_CARD.AGENT_NAME.in(boundAgents))
                .and(AGENT_CARD.IS_ONLINE.eq(true)); // 只返回已上线的Executor
        return agentCardMapper.selectListByQuery(queryWrapper);
    }

    @Override
    public List<ToolCard> getToolListByExecutor(String executorName) {
        AgentCard executor = agentCardMapper.selectOneById(executorName);
        if (executor == null || !"EXECUTOR".equals(executor.getAgentType())) {
            throw new RuntimeException("Executor不存在或类型不匹配: " + executorName);
        }

        List<String> boundTools = executor.getBoundTools();
        QueryWrapper queryWrapper = QueryWrapper.create()
                .where(TOOL_CARD.IS_ONLINE.eq(true));

        if (boundTools != null && !boundTools.isEmpty()) {
            // 如果 Executor 显式绑定了某些 tool，则可以直接使用并在其中检索 (包含 public 和 protected)
            queryWrapper.and(TOOL_CARD.TOOL_NAME.in(boundTools));
        } else if (boundTools != null && boundTools.isEmpty()) {
            // '[]' 表示不使用任何工具
            return Collections.emptyList();
        } else {
            // NULL 表示全量可用工具。为了合规，全量情况只能拉取 public 工具
            queryWrapper.and(TOOL_CARD.TOOL_PRIVILEGES.eq("public"));
        }
        return toolCardMapper.selectListByQuery(queryWrapper);
    }

    @Override
    public List<AgentCardSummaryVO> getAvailableAgents(String username) {
        // 第一步：获取当前用户、角色、租户绑定的 Agent 列表
        Set<String> allowedAgentNames = new HashSet<>();
        SysUser user = sysUserService.getByUsername(username);
        if (user != null) {
            // 1. 角色绑定的 Agent
            if (user.getRoleId() != null) {
                SysRole role = sysRoleService.getById(user.getRoleId());
                if (role != null && role.getAgentList() != null) {
                    allowedAgentNames.addAll(role.getAgentList());
                }
            }
            // 2. 租户绑定的 Agent (暂时从 User 上下文中获取 tenantCode，或者通过 SysTenantService)
            // 这里假设系统中有逻辑能获取当前用户的租户。为了简化，我们根据用户所属部门获取租户，或者直接通过上下文。
            // 逻辑由具体业务实现，此处示例：
            // SysTenant tenant = sysTenantService.getById(user.getTenantCode());
            // if (tenant != null && tenant.getAgentList() != null)
            // allowedAgentNames.addAll(tenant.getAgentList());
        }

        // 第二步：构建查询
        QueryWrapper queryWrapper = QueryWrapper.create()
                .select(AGENT_CARD.AGENT_NAME, AGENT_CARD.AGENT_ALIAS, AGENT_CARD.AGENT_DESCRIPTION,
                        AGENT_CARD.AGENT_TAGS, AGENT_CARD.REQUIRE_REVIEW)
                .from(AGENT_CARD)
                .where(AGENT_CARD.IS_ONLINE.eq(true));

        if (!allowedAgentNames.isEmpty()) {
            queryWrapper.and(AGENT_CARD.AGENT_NAME.in(allowedAgentNames));
        } else {
            // 如果没有任何绑定，且不是超级管理员，则可能返回空 (此处根据业务调整)
            // queryWrapper.and(AGENT_CARD.AGENT_NAME.eq("none"));
        }

        return agentCardMapper.selectListByQueryAs(queryWrapper, AgentCardSummaryVO.class);
    }

    @Override
    public AgentCard getAgentDetail(String agentName, String username) {
        AgentCard agentCard = agentCardMapper.selectOneById(agentName);
        if (agentCard == null) {
            throw new RuntimeException("智能体不存在: " + agentName);
        }
        if (Boolean.FALSE.equals(agentCard.getIsOnline())) {
            throw new RuntimeException("智能体未上线: " + agentName);
        }

        // 校验权限：用户是否有权访问该 Agent
        // (逻辑与 getAvailableAgents 类似)

        return agentCard;
    }
}
