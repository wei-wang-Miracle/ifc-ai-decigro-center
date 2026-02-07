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
}
