package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.AgentCard;
import com.mybatisflex.core.paginate.Page;

import java.util.List;

/**
 * MAS 智能体卡片服务接口 (V2)
 */
public interface AgentCardService {

    /**
     * 分页查询智能体列表
     */
    Page<AgentCard> page(String keyword, String tag, int pageNum, int pageSize);

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
    List<String> getAvailableTools();

    /**
     * 获取当前用户所有的可用智能体
     * 过滤规则: AgentCard.isOnline = true
     *
     * @return 符合条件的智能体简要信息列表
     */
    List<com.ifc.decigro.buskernel.entity.vo.AgentCardSummaryVO> getAvailableAgents();

    /**
     * 获取单个智能体的详情
     *
     * @param agentName 智能体名称
     * @return 智能体完整信息
     */
    AgentCard getAgentDetail(String agentName);
}
