package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.AgentCard;
import com.ifc.decigro.buskernel.entity.ToolCard;
import com.mybatisflex.core.paginate.Page;

import java.util.List;
import com.ifc.decigro.buskernel.entity.vo.AgentCardSummaryVO;
import com.ifc.decigro.buskernel.entity.vo.ToolCardSummaryVO;

/**
 * MAS 智能体卡片服务接口 (V2)
 */
public interface AgentCardService {

    /**
     * 分页查询智能体列表
     */
    Page<AgentCard> page(String keyword, String tag, String agentType, int pageNum, int pageSize);

    /**
     * 根据名称查询智能体详情 (主键变更为 String)
     */
    AgentCard getByName(String agentName);

    /**
     * 新增或更新智能体
     */
    void saveOrUpdate(AgentCard agentCard);

    /**
     * 删除智能体
     */
    void deleteByName(String agentName);

    /**
     * 更新智能体上线状态
     */
    void updateOnlineStatus(String agentName, boolean isOnline);

    /**
     * 检查智能体名称是否已存在
     */
    boolean existsByAgentName(String agentName);

    /**
     * 获取所有可绑定的工具列表
     */
    List<ToolCardSummaryVO> getAvailableTools();

    /**
     * 获取所有可绑定的 Executor 列表
     */
    List<String> getAvailableExecutors();

    /**
     * 向 ai-engine 提供接口：根据 Planner ID 获取其名下所有的 Executor
     * 
     * @param plannerName Planner 智能体名称
     * @return Executor 列表
     */
    List<AgentCard> getExecutorListByPlanner(String plannerName);

    /**
     * 向 ai-engine 提供接口：根据 Executor ID 获取其被授权的可用 Tool 列表
     * 
     * @param executorName Executor 智能体名称
     * @return ToolCard 列表
     */
    List<ToolCard> getToolListByExecutor(String executorName);

    /**
     * 获取当前用户所有的可用智能体
     * 过滤规则: AgentCard.isOnline = true AND (租户/角色的 agentList 包含该 agent)
     *
     * @param username 当前登录用户名
     * @return 符合条件的智能体简要信息列表
     */
    List<AgentCardSummaryVO> getAvailableAgents(String username);

    /**
     * 获取单个智能体的详情
     *
     * @param agentName 智能体名称
     * @param username  当前登录用户名 (用于权限校验)
     * @return 智能体完整信息
     */
    AgentCard getAgentDetail(String agentName, String username);
}
