package com.ifc.decigro.buskernel.service;

import com.ifc.decigro.buskernel.entity.ToolCard;
import com.mybatisflex.core.paginate.Page;

/**
 * MAS 工具卡片服务接口
 * 功能: 定义工具元数据管理的业务方法
 */
public interface ToolCardService {

    /**
     * 分页查询工具列表
     * 
     * 参数: keyword 关键字（可选），模糊匹配工具名称或描述
     * 参数: tag 标签（可选），筛选包含该标签的工具
     * 参数: pageNum 页码，从1开始
     * 参数: pageSize 每页条数
     * 返回: 分页结果
     */
    Page<ToolCard> page(String keyword, String tag, int pageNum, int pageSize);

    /**
     * 根据 ID 查询工具详情
     * 
     * 参数: id 工具ID
     * 返回: 工具实体，不存在时返回 null
     */
    ToolCard getById(Long id);

    /**
     * 新增或更新工具
     * 
     * 参数: toolCard 工具实体
     * - 新增时检查 toolName 是否已存在（唯一性校验）
     * - 更新时根据 id 匹配记录
     * 抛出: 业务异常（当 toolName 重复时）
     */
    void saveOrUpdate(ToolCard toolCard);

    /**
     * 删除工具
     * 
     * 参数: id 工具ID
     */
    void deleteById(Long id);

    /**
     * 更新工具上线状态
     * 
     * 参数: id 工具ID
     * 参数: isOnline true=上线, false=下线
     */
    void updateOnlineStatus(Long id, boolean isOnline);

    /**
     * 检查工具名称是否已存在
     * 
     * 参数: toolName 工具名称
     * 参数: excludeId 排除的ID（编辑时排除自身）
     * 返回: true=已存在, false=不存在
     */
    boolean existsByToolName(String toolName, Long excludeId);
}
