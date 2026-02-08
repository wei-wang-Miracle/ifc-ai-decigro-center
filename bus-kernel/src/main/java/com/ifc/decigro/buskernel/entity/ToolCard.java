package com.ifc.decigro.buskernel.entity;

import com.ifc.decigro.buskernel.common.handler.Fastjson2TypeHandler;
import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * MAS 工具卡片实体类
 * 功能: 对应数据库 tool_cards 表，定义 Agent 可调用的工具元数据
 * 
 * 设计理念：AI-First Schema
 * - 语义优先：包含 Context 和 Constraint 信息
 * - 自愈契约：参数定义包含示例，便于 Agent 理解
 * - 少样本增强：input/output examples 用于动态注入 Prompt
 */
@Data
@Table("tool_cards")
public class ToolCard implements Serializable {

    /**
     * 工具唯一标识（主键）
     * 必须符合 snake_case 格式，如 'get_weather_data'
     * 创建后不可修改
     */
    @Id
    private String toolName;

    /**
     * 工具描述（核心 Prompt）
     * 应包含：Trigger（何时触发）、Action（执行什么）、Constraint（限制条件）
     * 示例："Retrieves weather data. Use when user asks for temperature. Input must be
     * city name in English."
     */
    private String toolDescription;

    /**
     * 工具标签列表
     * 用于分类检索，如 ["finance", "external_api"]
     * 数据库存储为 TEXT[] 类型
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<String> toolTags;

    /**
     * 工具版本号
     * 默认 "1.0.0"
     */
    private String toolVersion;

    /**
     * 权限级别
     * 枚举值：public（公开可用）、protected（需授权）
     */
    private String toolPrivileges;

    /**
     * 调用协议
     * 枚举值：http（HTTP 接口）、reference（内部引用）
     */
    private String toolProtocol;

    /**
     * HTTP URL 路径
     * 当 toolProtocol = 'http' 时必填
     * 可以是相对路径（如 '/api/v1/weather'）或完整 URL
     */
    private String urlPath;

    /**
     * 引用目标
     * 当 toolProtocol = 'reference' 时必填
     * 指向内部资源（如表名、服务名）
     */
    private String referenceTarget;

    /**
     * 参数定义列表（JSONB）
     * 结构: [{ "param_name": "city", "param_type": "string",
     * "param_description": "目标城市名", "param_required": true,
     * "param_example": "Shanghai" }]
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<Map<String, Object>> toolParameters;

    /**
     * 出参定义列表（JSONB）
     * 结构与 toolParameters 相同: [{ "param_name": "temperature", "param_type":
     * "number",
     * "param_description": "返回的温度值", "param_required": true,
     * "param_example": 25 }]
     * 用于描述工具返回数据的结构
     */
    @Column(typeHandler = Fastjson2TypeHandler.class)
    private List<Map<String, Object>> outputSchema;

    /**
     * 输入示例（Few-Shot Input）- TEXT 类型
     * 可填入任意文本（含 JSON），用于信息补充
     * 例如用户可能的提问方式、参数示例等
     */
    private String inputExamples;

    /**
     * 输出示例（Few-Shot Output）- TEXT 类型
     * 可填入任意文本（含 JSON），用于信息补充
     * 例如工具返回的数据结构示例
     */
    private String outputExamples;

    /**
     * 是否上线
     * true = 对 Agent 可见可用
     * false = 草稿状态，不参与工具调度
     */
    private Boolean isOnline;

    /**
     * 创建时间
     */
    @Column(onInsertValue = "now()")
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    @Column(onInsertValue = "now()", onUpdateValue = "now()")
    private LocalDateTime updateTime;

    /**
     * 管理人
     * 记录工具的创建/维护人员
     */
    private String managerBy;
}
