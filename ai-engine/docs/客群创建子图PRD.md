# 客群创建子图 PRD - 基于 LangGraph Ralph 反馈循环

## 1. 概述

### 1.1 文档目的

本文档定义了基于 LangGraph Subgraph 架构的**客群创建子图**的产品需求与设计规范。该子图通过 Ralph 反馈循环（Predict-Act-Feedback-Adjust）实现 AI Agent 与用户的协同交互，确保客群创建过程的可控性与准确性。

### 1.2 设计背景

当前 AI-Native 客群接口已通过 ToolCard 注解暴露了 5 个核心工具，AI Agent 可以独立调用完成客群创建。然而，缺少统一的流程编排与状态管理，导致：
- AI 可能跳过关键验证步骤直接创建
- 用户无法有效介入确认环节
- 条件构建错误时缺乏有效的回退机制

通过 LangGraph Subgraph 将这些工具编排为有状态的反馈循环，可实现：
- 流程强制执行（每步必达）
- 人机回环（Human-in-the-loop）
- 状态持久化与条件一致性保证

### 1.3 核心工具清单
核心输入 和 核心输出 均来自tool_registry的注册信息

| 工具名称 | 功能 | HTTP方法 | 核心输入 | 核心输出 |
|---------|------|---------|---------|---------|
| `query_all_labels` | 获取所有可用标签 | GET | 无 | 标签列表（field、valueType、supportedOperators、enumOptions） |
| `get_example_client_group` | 获取示例客群配置 | GET | 无 | 示例客群详情（含 groupConditions 结构） |
| `preview_client_group_count` | 预览客群人数 | POST | groupConditions | 人数描述字符串 |
| `create_client_group` | 创建客群 | POST | name、remark、groupConditions | clientGroupId |
| `list_my_client_groups` | 查询用户客群列表 | GET | limit | 客群列表 |


### 1.4 子图触发条件：当规划者根据用户需求判定需要进行创建客群操作时，将该子图插入到PlanStep中，并进行触发
planner必须要先知道子图的信息 **ai_client_group_creater（智能客群生成专家）** 子图
描述信息： 智能客群生成专家专用于将业务需求转化为系统规则，并实际落地创建目标客群。其特点是严格遵循“查询标签字典 -> 预览客群规模 -> 正式创建客群”的强制工作流，确保规则100%合法。具备强大的“2次报错熔断”自愈机制，遇挫会自动调取标准示例对比重构。当用户需要根据标签、条件圈选并最终生成、落地一个真实客群实体时，必须调用此专家。

---

## 2. Ralph 反馈循环设计

### 2.1 Ralph 循环原理

Ralph 反馈循环是一种人机协同的决策框架，通过四个阶段的循环迭代实现最优决策：

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐ │
│    │ PREDICT │───▶│   ACT   │───▶│ FEEDBACK│───▶│ ADJUST  │ │
│    └─────────┘    └─────────┘    └─────────┘    └─────────┘ │
│         ▲                                           │       │
│         │              Ralph Feedback Loop         │       │
│         └───────────────────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| 阶段 | 含义 | 在客群场景的映射 |
|------|------|-----------------|
| **Predict** | AI 基于输入预测输出 | AI 根据用户画像推断客群条件 |
| **Act** | 执行动作验证预测 | 调用 preview_client_group_count 预览人数 |
| **Feedback** | 获取反馈结果 | 获取人数是否符合预期 |
| **Adjust** | 根据反馈调整策略 | 若不符合，修改条件重新预测 |

### 2.2 客群创建中的 Ralph 循环

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  ┌────────────────┐                                                   │
│  │   1. 预测阶段   │  AI 基于用户画像 + 标签知识，构建 groupConditions  │
│  │   PREDICT      │                                                   │
│  └───────┬────────┘                                                   │
│          │                                                            │
│          ▼                                                            │
│  ┌────────────────┐                                                   │
│  │   2. 行动阶段   │  调用 preview_client_group_count                   │
│  │   ACT          │  预览客群人数                                      │
│  └───────┬────────┘                                                   │
│          │                                                            │
│          ▼                                                            │
│  ┌────────────────┐                                                   │
│  │  3. 反馈阶段    │  获取人数反馈：是否合理、是否为空、是否过多        │
│  │   FEEDBACK     │                                                   │
│  └───────┬────────┘                                                   │
│          │                                                            │
│          ▼                                                            │
│  ┌────────────────┐                                                   │
│  │  4. 调整阶段    │  人机回环：展示条件给用户，征求修改意见            │
│  │   ADJUST       │  用户确认后重新进入 PREDICT                       │
│  └───────┬────────┘                                                   │
│          │                                                            │
│          │      ┌─────────────────────────────────────────┐          │
│          │      │           Human-in-the-Loop              │          │
│          │      │      用户确认 → 创建客群                 │          │
│          │      └─────────────────────────────────────────┘          │
│          │                                                            │
│          │ YES  (用户确认)                                            │
│          └──────────────────────────────────────────────────────────┐│
│                                                                       │
│  ┌────────────────┐                                                   │
│  │  5. 执行阶段    │  调用 create_client_group                        │
│  │   EXECUTE      │  保持与预览时完全一致的条件                        │
│  └───────┬────────┘                                                   │
│          │                                                            │
│          ▼                                                            │
│  ┌────────────────┐                                                   │
│  │  6. 验证阶段    │  调用 list_my_client_groups                       │
│  │   VERIFY       │  确认客群已创建                                   │
│  └───────┬────────┘                                                   │
│          │                                                            │
└──────────┼───────────────────────────────────────────────────────────┘
           │
           ▼
     [子图结束]
```

---

## 3. LangGraph 架构设计

### 3.1 子图整体架构参考

```mermaid
graph TB
    subgraph ClientGroupSubgraph["客群创建子图 (ClientGroupSubgraph)"]
        direction TB
        
        START([开始: user_input])
        END([结束: result])
        
        START --> N1
        N1["query_labels\n获取标签列表"] --> N2
        N2{"标签已缓存?"} -->|否| N3["fetch_examples\n获取示例客群"]
        N2 -->|是| N4
        N3 --> N4["learn_structure\n学习客群结构"]
        N4{"用户是否提供\n客群条件?"} -->|否| N5["build_conditions\n构建初始条件"]
        N4 -->|是| N6
        N5 --> N6["preview_count\n预览客群人数"]
        N6 --> N7{"人数符合预期?"}
        N7 -->|否| N8["human_feedback\n人机回环"]
        N8 --> N9{"用户调整?"}
        N9 -->|是| N5
        N9 -->|否| END
        N7 -->|是| N10["request_confirmation\n请求用户确认"]
        N10 --> N11{"用户确认?"}
        N11 -->|是| N12["create_group\n创建客群"]
        N11 -->|否| N8
        N12 --> N13["verify_group\n验证客群"]
        N13 --> N14{"验证通过?"}
        N14 -->|是| N15["success\n返回结果"]
        N14 -->|否| N16["report_error\n报告错误"]
        N15 --> END
        N16 --> END
    end
```

---

## 4. 完整流程图 (Mermaid)

### 4.1 Ralph 反馈循环流程图参考

```mermaid
flowchart TD
    subgraph RalphLoop["Ralph 反馈循环"]
        direction TB
        
        A["🎯 PREDICT\nAI 预测"] --> B["⚡ ACT\n执行预览"]
        B --> C["📊 FEEDBACK\n获取反馈"]
        C --> D{"反馈判断"}
        
        D -->|"人数 = 0"| E["🔄 ADJUST\n调整条件"]
        D -->|"人数过多"| E
        D -->|"人数合理"| F["✅ CONFIRM\n请求确认"]
        
        E --> A
        F --> G{"用户确认?"}
        G -->|"是"| H["🚀 EXECUTE\n创建客群"]
        G -->|"否"| E
        H --> I["🔍 VERIFY\n验证结果"]
        I --> J{"验证通过?"}
        J -->|"是"| K["🎉 SUCCESS\n完成"]
        J -->|"否"| L["❌ ERROR\n报告错误"]
    end
```

### 4.2 LangGraph 状态机流程图

```mermaid
stateDiagram-v2
    [*] --> QueryLabels: 开始
    
    state QueryLabels {
        [*] --> FetchLabels
        FetchLabels --> FetchExamples
        FetchExamples --> LearnStructure
        LearnStructure --> [*]
    }
    
    QueryLabels --> BuildConditions: 标签已加载
    QueryLabels --> [*]: 标签已缓存
    
    state RalphCycle {
        direction LR
        BuildConditions: "🔵 build_conditions\n(PREDICT)"
        PreviewCount: "⚡ preview_count\n(ACT)"
        HumanFeedback: "📊 human_feedback\n(FEEDBACK/ADJUST)"
        
        BuildConditions --> PreviewCount
        PreviewCount --> HumanFeedback
        HumanFeedback --> BuildConditions: "需调整"
        HumanFeedback --> RequestConfirm: "符合预期"
    }
    
    RalphCycle --> RequestConfirmation: 条件确认
    
    state RequestConfirmation {
        [*] --> ShowPreview
        ShowPreview --> UserDecision
        UserDecision --> [*]: "确认"
        UserDecision --> HumanFeedback: "拒绝"
    }
    
    RequestConfirmation --> CreateGroup: 用户确认
    
    CreateGroup --> VerifyGroup: 创建成功
    
    state VerifyGroup {
        [*] --> QueryMyGroups
        QueryMyGroups --> CheckResult
        CheckResult --> [*]: "找到"
        CheckResult --> ReportError: "未找到"
    }
    
    VerifyGroup --> [*]: 成功
    ReportError --> [*]: 失败
```

### 4.3 数据流图参考

```mermaid
flowchart LR
    subgraph Input["📥 输入"]
        U[用户画像输入]
    end
    
    subgraph Tools["🔧 ToolCard 工具"]
        QL["query_all_labels\n获取标签"]
        GE["get_example_client_group\n获取示例"]
        PC["preview_client_group_count\n预览人数"]
        CG["create_client_group\n创建客群"]
        LG["list_my_client_groups\n查询客群"]
    end
    
    subgraph State["📊 LangGraph State"]
        Labels["labels_cache"]
        Examples["examples_cache"]
        Conditions["group_conditions"]
        PreviewRes["preview_result"]
        PreviewCond["preview_conditions"]
        CreatedID["created_group_id"]
    end
    
    subgraph Output["📤 输出"]
        Success["创建成功结果"]
        Error["错误报告"]
    end
    
    U --> QL
    QL --> Labels
    Labels --> GE
    GE --> Examples
    Examples --> Conditions
    Conditions --> PC
    PC --> PreviewRes
    PreviewRes --> PreviewCond
    PreviewCond --> CG
    CG --> CreatedID
    CreatedID --> LG
    LG --> Success
    LG --> Error
```

---

## 5. 详细交互设计参考

### 5.1 场景示例

**场景**: 用户说"我想创建一个高净值客户群，年龄30岁以上，资产50万以上"

#### LangGraph 执行序列

```mermaid
sequenceDiagram
    participant User as 用户
    participant Graph as LangGraph
    participant Tools as ToolCard 工具
    
    User->>Graph: 用户输入: "高净值客户群，年龄30岁以上"
    
    Graph->>Tools: query_all_labels()
    Tools-->>Graph: 返回标签列表
    Graph->>Graph: 更新 labels_cache
    
    Graph->>Tools: get_example_client_group()
    Tools-->>Graph: 返回示例客群
    Graph->>Graph: AI 学习结构
    
    Note over Graph: Ralph PREDICT 阶段
    Graph->>Graph: AI 解析用户输入
    Graph->>Graph: 构建 conditions:
    Note over Graph: 
        conditions: [{
            labelField: "age",
            operator: "gte",
            values: ["30"]
        }, {
            labelField: "asset_total",
            operator: "gte",
            values: ["500000"]
        }]
    end
    
    Note over Graph: Ralph ACT 阶段
    Graph->>Tools: preview_client_group_count(conditions)
    Tools-->>Graph: "客群匹配客户数量：[320]"
    
    Note over Graph: Ralph FEEDBACK 阶段
    Graph->>User: 展示预览结果 + 条件
    Graph->>User: "当前条件可匹配320位客户，是否符合预期？"
    
    User->>Graph: 用户反馈: "符合预期"
    
    Note over Graph: Ralph CONFIRM 阶段
    Graph->>User: 请求确认: "请确认创建客群"
    User->>Graph: 用户确认
    
    Note over Graph: EXECUTE 阶段
    Graph->>Tools: create_client_group(conditions)
    Note over Graph: 使用 preview_conditions，保持一致
    Tools-->>Graph: 返回 clientGroupId: 10126
    
    Note over Graph: VERIFY 阶段
    Graph->>Tools: list_my_client_groups(limit=10)
    Tools-->>Graph: 返回客群列表
    Graph->>Graph: 验证 10126 存在
    
    Graph->>User: "客群创建成功！ID: 10126"
```

### 5.2 人机回环交互

```mermaid
flowchart LR
    subgraph AI["🤖 AI Agent"]
        A1["构建条件"] --> A2["预览人数"]
        A2 --> A3{"分析反馈"}
        A3 -->|"不合理"| A4["展示调整建议"]
        A3 -->|"合理"| A5["请求确认"]
        A4 --> A1
        A5 --> A6{"用户决策"}
    end
    
    subgraph Human["👤 用户"]
        H1["查看预览结果"]
        H2["给出反馈意见"]
        H3["确认/拒绝"]
    end
    
    subgraph Tool["🔧 系统"]
        T1["展示条件详情"]
        T2["展示人数"]
    end
    
    A2 --> T2
    T2 --> H1
    H1 --> H2
    H2 --> A4
    H2 --> A3
    A4 --> H1
    A5 --> H3
    H3 -->|"确认"| A6
    H3 -->|"拒绝"| A4
```

### 5.3 条件一致性保证

```mermaid
flowchart TB
    subgraph 构建["PREDICT 阶段"]
        B1["解析用户输入"] --> B2["生成 groupConditions"]
        B2 --> B3["存入 group_conditions"]
    end
    
    subgraph 预览["ACT 阶段"]
        B3 --> P1["取出 group_conditions"]
        P1 --> P2["调用 preview 接口"]
        P2 --> P3["存入 preview_conditions"]
    end
    
    subgraph 确认["CONFIRM 阶段"]
        P3 --> C1["展示 preview_conditions"]
        C1 --> C2{"用户确认?"}
        C2 -->|"拒绝"| R1["进入 ADJUST"]
        C2 -->|"确认"| C3["准备创建"]
    end
    
    subgraph 创建["EXECUTE 阶段"]
        C3 --> E1["从 preview_conditions 取条件"]
        E1 --> E2["调用 create 接口"]
    end
    
    subgraph 验证["VERIFY 阶段"]
        E2 --> V1["调用 list 接口"]
        V1 --> V2{"验证存在?"}
        V2 -->|"是"| V3["成功"]
        V2 -->|"否"| V4["失败"]
    end
    
    R1 --> B1
```

**关键设计**: `preview_conditions` 字段记录预览时的条件，创建时强制使用该字段，确保用户确认的条件与最终创建的条件完全一致。

---

## 6. 错误处理与边界情况

### 6.1 错误类型与处理

| 错误场景 | 原因 | 处理策略 |
|---------|------|---------|
| `query_all_labels` 调用失败 | 注册中心不可用 | 降级使用缓存标签，或返回友好错误 |
| `preview_client_group_count` 调用失败 | 条件格式错误 | 解析错误信息，提示 AI 修正条件 |
| 预测循环超过 5 次 | 用户条件无法满足 | 强制进入确认阶段，告知用户限制 |
| `create_client_group` 调用失败 | 业务校验失败 | 返回具体错误原因，如"客群名称已存在" |
| `verify_group` 验证失败 | 创建后查询不到 | 记录错误，尝试重新查询 3 次 |

---

### 9.2 参考资料

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Ralph 反馈循环论文](https://arxiv.org/abs/2304.13007)

---

