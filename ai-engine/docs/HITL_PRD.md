# 深度 PRD：多智能体人机回环 (HITL) 全生命周期与实体架构

## 一、 核心实体与映射关联性 (Entity Relationships)

在整个生命周期中，流转着 4 个核心数据实体。它们之间并非孤立，而是存在**严格的父子继承与约束关系**。

1.  **实体 A：`Agent_HITL_Config` (系统预设Agent级别的人机回环配置)**
    * **作用：** 决定了当前智能体“该看什么、该想什么”。
    * **去向：** 作为 System Prompt 的一部分，约束大模型的输出。
    * **前端维护，最终进到后端配置中心**，持久化到agent_cards.humanReviewConfig
2.  **实体 B：`Universal_HITL_Response` (大模型输出实体，模型组织内容框架限制格式ProfessionalAuditResponse)**
    * **关联性：** 实体 B 的结构必须 100% 遵守实体 A 的约束。
    * **去向：** 透传给前端，由前端渲染成对应的 UI 界面。
3.  **实体 C：`HumanDecisionPayload` (实体 B 的人类交互结果)**
    * **关联性：** 实体 C 的内容直接来源于人类对实体 B 的交互。
    * **去向：** 传回后端 Router，作为唤醒下游的入参，目的是将人类的决策结构化地传递给智能体。
    * **关注点:** 本质上智能体仅需要接收用户交互结果，即用户反馈信息，不关心用户是如何得到这个反馈的，以及对应关系是什么样的。所以HumanDecisionPayload 仅需要包含用户交互结果即可，不需要包含实体B的结构，可以分为接受的部分和不接受的部分，以及接受后需要补充的信息。接受的部分可以包含用户确认的check_list，接受的proposal，以及接受后需要补充的信息。不接受的部分可以包含用户拒绝的check_list，拒绝的proposal，以及拒绝后需要补充的信息。


---

## 二、 结构实体定义 (Data Contracts)

### 1. 实体 A：配置项契约 (`Agent_HITL_Config`)
*部署位置：后端数据库/配置中心，由产品经理或产研配置。*

```json
{
  "agent_name": "fund_profiling_agent",
  "hitl_config": {
    // 配置开关
    "ui_switches": {
        // 是否开启
      "visual_data_enable": true,
      "check_list_enable": true,
      "proposals_enable": true
    },
    "generation_constraints": {
        // 深度洞察方向：指导AI朝着什么方向“比用户多想一步”（如合规、收益、未来趋势），"未来一个月合规风险预期", "潜在的业务穿透影响"
        "predictive_foresight_focus": [],
        // 摘要约束视角
        "executive_summary_perspectives": [],
        // 图表约束视角
        "visual_data_perspectives":[],  
       "check_list_dimensions": [],
       "proposal_perspectives": []
    }
  }
}
```

### 2. 实体 B：响应协议契约 (`Universal_HITL_Response`)
*部署位置：LLM 结构化输出 -> 传递给前端。*

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal

# --- 1. 前端友好：ECharts 协议对象 ---
class EChartsConfig(BaseModel):
    # 图表标题
    title: Optional[str] = None
    # 显式声明这是一个什么图表，方便前端决定容器的高宽或做降级处理
    chart_type: Literal["radar", "bar", "pie", "funnel", "sankey", "line", "none"] = Field(
        ..., description="图表的主要类型"
    )
    
    # 核心：使用 Dict[str, Any] 彻底放开限制 进行echars渲染
    option: Dict[str, Any] = Field(
        ..., 
        description="""
        完全符合 Apache ECharts 官方 option 规范的 JSON 对象。
        大模型必须根据 chart_type 输出对应的完整配置，例如包含 title, tooltip, legend, series 等。
        前端收到后将直接执行：myChart.setOption(option)
        """
    )
    
    # 辅助字段：向用户解释为什么要画这张图，这张图的意义是什么
    insight_text: str = Field(..., description="对该图表数据的一句话专业解读")

# --- 2. 用户友好：结构化 CheckList 条目 ---
class AuditCheckItem(BaseModel):
    item_id: str
    task_label: str = Field(..., description="待办任务描述，如 '核对基金经理变更时间'")
    ai_observation: str = Field(..., description="AI的观察发现，如 '公告与持仓变动存在2周偏差'")
    severity: Literal["low", "medium", "high"] = "medium"
    is_confirmed: bool = False

# --- 3. 智能感：多维建议方案 ---
class StrategicProposal(BaseModel):
    option_id: str
    title: str
    is_recommond: bool = Field(..., description="是否是最推荐的方案")
    recommond_reason: str = Field(..., description="推荐理由")
    # 用户视角的执行成本估算
    effort_estimation: Literal["low", "medium", "high"] = Field(..., description="实施该方案的工作量/落地成本评估")
    # 专业视角的潜在影响评估
    impact_analysis: str = Field(..., description="采纳该方案可能带来的深远影响（如：风险化解程度、可能的副作用、时间窗口）")

# --- 4. 综合输出模型 (The Grand Schema) ---
class ProfessionalAuditResponse(BaseModel):
    # 总结阶段
    summary_title: str
    executive_summary: str = Field(..., description="专业总结，体现洞察力")
    # 顶层设计：多想一步的高阶预警
    advanced_foresight: str = Field(..., description="超出常规视角的深度预警或机会提示（例如关联宏观环境或同类资产历史教训，体现专家系统价值）")
    visual_data: List[EChartsConfig] = Field(..., description="前端直接提取并渲染的图表协议")

    # 审核阶段
    check_list: List[AuditCheckItem] = Field(..., description="结构化审核清单")
    
    # 建议阶段
    proposals: List[StrategicProposal] = Field(..., description="专家级建议列表")
```

### 3. 实体 C：用户提交契约 (`HumanDecisionPayload`)
*部署位置：前端表单组装 -> 传递给后端。*

```json
{
  "session_id": "workflow_trace_8848",
  "quick_decision_flag": "custom",  // 快捷交互标识：枚举值为 "approve_all_ai_recommendations" / "reject_all" / "custom" 
  "accepted": {
    "check_list": [
      {
        "item_id": "chk_01",
        "task_label": "核对基金经理变更时间",
        "ai_observation": "公告与持仓变动存在2周偏差"
      }
    ],
    "proposals": [
      {
        "option_id": "opt_a_override",
        "title": "修改标签并预警"
      }
    ]
  },
  "rejected": {
    "check_list": [
      {
        "item_id": "chk_02",
        "task_label": "审查持仓集中度",
        "ai_observation": "单只股票占比超过10%"
      }
    ],
    "proposals": [
      {
        "option_id": "opt_b_ignore",
        "title": "忽略异常"
      }
    ]
  },
  "comprehensive_supplementary_notes": "考虑到近期半导体波动大，接受修改标签和预警；另外chk_02为正常业务波动，无需关注。" // 用户对当前审批方案的整体补充说明
}
```

---

## 三、 全生命周期流转详述 (Lifecycle Stages)

### 阶段 1：Config 融合与触发 (Agent ➡️ LLM)
**核心动作：将配置项“无缝”织入提示词，强迫大模型按规矩办事。**

1.  **触发异常**：基金画像 Agent 执行时，发现计算出的行业偏离度超过阈值。
2.  **融合配置**：Router 拦截该异常，调取该 Agent 的 `Agent_HITL_Config` (实体 A)。
3.  **动态 Prompt 组装**：将实体 A 作为 System Instruction 的一部分传递给大模型，并调用 `with_structured_output` 强制要求返回 `Universal_HITL_Response` (实体 B) 格式。
    * *Prompt 示例：“你是一个基金风控专家，你必须对发现的异常进行总结。你必须严格检查【公告一致性、基金经理变更】这两个维度并输出 CheckList。你的建议必须包含【合规、业务】两个视角的分析。”*

### 阶段 2：前端表单动态展示 (LLM ➡️ Frontend)
**核心动作：前端作为“无脑渲染引擎”，将协议映射为专业 UI。**

1.  **解析渲染**：前端收到实体 B。
    * 读取 `visual_data`，直接挂载 `<ECharts option={chart_config.option} />`。
    * 读取 `check_list`，循环渲染 `<Checkbox />` 组件，初始状态为 `unchecked`。
    * 读取 `proposals`，循环渲染 Radio Button Card 组，并将视角分析以 Tab 或列表形式展示在卡片内。
2.  **交互约束**：前端实现强防呆设计。如果 CheckList 有未勾选项，且用户没有输入拒绝理由，则“提交审批”按钮置灰（Disabled）。

### 阶段 3：用户干预与结构化提交 (Frontend ➡️ Router)
**核心动作：将人类的复杂决策收敛为极简的确定性 Payload。**

1.  **收集状态**：用户审阅雷达图，勾选 CheckList，选中“方案A”，并在补充意见框填写了“加一个 R5 预警”。
2.  **组装发送**：前端需要将用户交互结果处理为实体C， `HumanDecisionPayload` (实体 C) 发送给后端 Router。

### 阶段 4：AI 友好化交互与唤醒下游 (Router ➡️ Next Agent)
**核心动作：处理人类的非结构化备注，根据结果不同执行不同的动作。**

---

## 四、 边界与熔断机制 (Edge Cases & Fallbacks)

为了保证工业级可用性，在生命周期中需考虑以下边界：

1.  **LLM 格式崩溃（幻觉兜底）**：
    * 如果阶段 1 中 LLM 未能按照实体 B 输出标准的 ECharts 格式，后端的 Pydantic 校验会抛出异常。
    * *处理：* 后端执行重试机制（Max Retries = 2）。若仍失败，则降级为纯文本回环面板（忽略图表，仅展示异常摘要和简单选项）。
2.  **全盘驳回/全盘接受（Escape Hatch）**：
    * 如果 AI 的选项都不对，用户在前端点击了**“彻底驳回 (Reject & Terminate)”**。


通过这套实体映射与全生命周期设计，你的多智能体系统不仅在前端具备了极高的专业度，在后端也具备了企业级软件必须拥有的**高内聚、低耦合**与**可追溯性**。

---

## 五、 工程落地实现参考 (Implementation Reference)

本章节记录 PRD 各实体在三端（Python AI 引擎 / Java 业务内核 / Vue 前端）的具体落地方式，方便后续维护者快速定位代码。

### 1. 文件地图

```
ai-engine/
├── src/ai_engine/graph/
│   ├── hitl_models.py                          ← ★ 新增：Entity A/B/C Pydantic 模型定义
│   ├── state.py                                ← 修改：StepResult 新增 structured_audit 字段
│   └── nodes/
│       ├── plan_task_execute_node.py           ← 修改：新增 _generate_structured_audit()，_check_review() 双模式
│       └── human_review_node.py                ← 修改：interrupt 传递结构化数据，resume 解析结构化决策
├── src/ai_engine/api/
│   └── routes.py                               ← 修改：ReviewEvent 扩展，ChatRequest 扩展，review 路由增强

bus-kernel/
├── src/.../dto/
│   └── HumanReviewConfigDTO.java               ← ★ 新增：Entity A 的 Java 侧 DTO 校验
├── src/.../controller/
│   └── AgentCardController.java                ← 修改：save 接口增加 humanReviewConfig 结构校验

decigro-fe/
├── src/stores/
│   └── chatStore.ts                            ← 修改：新增 StructuredAuditData / HumanDecisionPayload 类型
├── src/views/chat/
│   ├── index.vue                               ← 修改：集成 ReviewPanel，SSE 解析 structured_audit
│   └── components/
│       └── ReviewPanel.vue                     ← ★ 新增：结构化审核面板（ECharts + CheckList + Proposal）
```

### 2. 实体 A 落地：`AgentHITLConfig`

**Python 侧** — `hitl_models.py`

```
AgentHITLConfig
  ├── ui_switches: HITLUISwitches
  │     ├── visual_data_enable   (bool, 默认 False)
  │     ├── check_list_enable    (bool, 默认 False)
  │     └── proposals_enable     (bool, 默认 False)
  ├── generation_constraints: HITLGenerationConstraints
  │     ├── predictive_foresight_focus     (list[str])
  │     ├── executive_summary_perspectives (list[str])
  │     ├── visual_data_perspectives       (list[str])
  │     ├── check_list_dimensions          (list[str])
  │     └── proposal_perspectives          (list[str])
  └── 旧版兼容字段
        ├── review_dimensions   (list[str])
        ├── review_instruction  (str)
        └── summary_prompt      (str)
```

- 通过 `has_structured_hitl()` 判断是否启用结构化 HITL（至少一个 UI 开关为 True）
- 从 `agent_config.human_review_config` 字典解析得到（运行时校验）

**Java 侧** — `HumanReviewConfigDTO.java`

- 在 `AgentCardController.save()` 中对 `humanReviewConfig` 做反序列化校验
- 兼容旧版配置：旧字段 `reviewDimensions / reviewInstruction / summaryPrompt` 仍可用

### 3. 实体 B 落地：`ProfessionalAuditResponse`

**Python 侧** — `hitl_models.py` 定义，`plan_task_execute_node.py` 生成

生成时机：`_check_review()` → `_generate_structured_audit()`

```
执行结果 output
    │
    ▼
_generate_structured_audit()
    │  1. 从 human_review_config 解析 AgentHITLConfig
    │  2. 检查 has_structured_hitl()，未启用则返回 None（走原有文本路径）
    │  3. 根据 ui_switches 动态构建 prompt（仅启用的模块要求 LLM 输出）
    │  4. 使用 llm.with_structured_output(ProfessionalAuditResponse) 强制结构化
    │  5. 失败时返回 None，由 _extract_conclusion() 兜底
    │
    ▼
StepResult
    ├── conclusion: str          ← 纯文本摘要（fallback，始终有值）
    └── structured_audit: dict   ← ProfessionalAuditResponse.model_dump()（结构化时有值）
```

**SSE 传输** — `routes.py`

```
ReviewEvent {
    type: "review",
    step_index, step_description, review_message,
    agent_name, agent_alias,
    structured_audit: dict | null    ← 新增字段
}
```

**前端渲染** — `ReviewPanel.vue`

```
structuredAudit 数据
    │
    ├── 摘要区 ─── summary_title + executive_summary + advanced_foresight（蓝色提示框）
    │
    ├── 图表区 ─── v-for visual_data → echarts.init(dom).setOption(item.option)
    │                                    + insight_text 文字解读
    │
    ├── 清单区 ─── v-for check_list → el-checkbox（默认全部勾选）
    │                                   + severity 标签（high/medium/low）
    │
    ├── 方案区 ─── v-for proposals → 可点选卡片（默认选中 is_recommond=true 的）
    │                                  + recommond_reason + effort/impact 指标
    │
    └── 操作栏 ─── [全部接受] [提交自定义决策] [全部驳回]
```

### 4. 实体 C 落地：`HumanDecisionPayload`

**前端组装** — `ReviewPanel.vue` 的 `buildPayload()`

```
用户交互状态
    │
    ├── checkedItems（CheckList 勾选状态）───┐
    ├── selectedProposalId（方案选择）────────┤
    └── supplementaryNotes（补充说明）────────┤
                                              ▼
                                    HumanDecisionPayload {
                                      session_id,
                                      quick_decision_flag,     ← "approve_all" / "reject_all" / "custom"
                                      accepted: { check_list, proposals },
                                      rejected: { check_list, proposals },
                                      comprehensive_supplementary_notes
                                    }
```

**传输** — `index.vue` → `handleReviewSubmit()` → `POST /chat/stream`

```json
{
  "query": "[审核决策] 全部接受 / 全部驳回 / 自定义",
  "task_id": "当前 task_id",
  "review_decision": { ... HumanDecisionPayload ... }
}
```

**后端路由** — `routes.py` + `human_review_node.py`

```
ChatRequest.review_decision 有值？
    │
    ├── 是 → Command(resume={"action": "structured", "structured_decision": {...}})
    │         │
    │         ▼  human_review_node 解析 HumanDecisionPayload
    │         ├── approve_all_ai_recommendations → _approve()  → dispatcher → 下一步
    │         ├── reject_all                     → _reject()   → feedback handler
    │         └── custom
    │               ├── 仅有 accepted 项 → _approve()
    │               └── 含 rejected 项   → _reject(feedback_text)
    │                                        ↑ to_feedback_text() 将结构化决策转为自然语言
    │
    └── 否 → 走原有关键词 / LLM 意图检测（向后兼容）
```

### 5. 向后兼容策略

| 场景 | 行为 |
|------|------|
| Agent 未配置 `humanReviewConfig` | 纯文本 `_extract_conclusion()` → markdown 审核消息 → 用户文字回复 |
| Agent 配了旧版字段（`review_dimensions` 等）但无 `ui_switches` | 同上，`has_structured_hitl()` 返回 False |
| Agent 配了 `ui_switches` 但 LLM 结构化输出失败 | 回退到纯文本路径，`structured_audit = None` |
| 前端收到 `structured_audit = null` 的 ReviewEvent | 渲染原有文本审核卡片 + 输入框回复 |
| 前端收到 `structured_audit` 有值的 ReviewEvent | 渲染 ReviewPanel 结构化面板 |
| 用户在文字输入框回复（无 `review_decision`） | 走原有关键词/LLM 检测逻辑 |