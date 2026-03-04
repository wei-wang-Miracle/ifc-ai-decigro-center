package com.ifc.decigro.buskernel.entity.vo;

import com.ifc.decigro.buskernel.common.handler.Fastjson2TypeHandler;
import com.mybatisflex.annotation.Column;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.List;

/**
 * 工具卡片简要信息 VO
 * 用于 AI 引擎加载阶段获取工具介绍
 * 符合渐进式加载思想
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ToolCardSummaryVO implements Serializable {

    /**
     * 工具名称
     */
    private String toolName;

    /**
     * 工具别名
     */
    private String toolAlias;

    /**
     * 工具描述
     */
    private String toolDescription;

    /**
     * 工具标签列表
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> toolTags;

    /**
     * 工具权限
     * public: 公开工具
     * protected: 受保护工具（需要 Agent 绑定）
     */
    private String toolPrivileges;
}
