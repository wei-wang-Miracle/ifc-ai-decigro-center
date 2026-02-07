# AI引擎

## 主要职责

基于Multi-Agent系统设计思想构建系统大脑，负责推理、决策和意图识别，Agent编排和工具调用

## 技术要求

| 技术              | 版本   | 用途                  |
| ----------------- | ------ | --------------------- |
| **Python**        | 3.12+  | 编程语言              |
| **FastAPI**       | 0.115+ | Web框架               |
| **LangChain**     | 1.2+   | LLM应用框架（Agent）  |
| **LangGraph**     | 1.0+   | Agent工作流和记忆管理 |
| **uv**            | latest | Python包管理工具      |
| **Pydantic**      | 2.9+   | 数据验证大模型格式化  |
| **python-dotenv** | 1.0+   | 环境变量管理          |

## 设计模式

plan and execute、COT、 ReAct

## 系统架构图

```mermaid
graph TD
    START([开始]) --> intent_recognition_node["Intent Recognition Node<br/>(意图识别)"]

    intent_recognition_node --> |识别成功| dispatcher_node["Dispatcher Node<br/>(调度中心)"]
    intent_recognition_node --> |结束| END1([结束])

    dispatcher_node --> |规划任务| planner_node["Planner Node<br/>(规划执行)"]
    dispatcher_node --> |执行任务| plan_task_execute_node["Plan Task Execute Node<br/>(任务执行)"]
    dispatcher_node --> |重新规划| intent_recognition_node
    dispatcher_node --> |完成| END2([结束])

    planner_node --> |规划完成| dispatcher_node

    plan_task_execute_node --> |需要审核| human_review_node["Human Review Node<br/>(人工审核)"]
    plan_task_execute_node --> |继续执行| dispatcher_node

    human_review_node --> |APPROVE<br/>审核通过| dispatcher_node
    human_review_node --> |REJECT<br/>审核驳回| feedback_handler_node["Feedback Handler Node<br/>(反馈处理)"]

    feedback_handler_node --> |处理完成| dispatcher_node

    style dispatcher_node fill:#ff9800,stroke:#e65100,stroke-width:3px
    style intent_recognition_node fill:#2196f3,stroke:#0d47a1,stroke-width:2px
    style planner_node fill:#4caf50,stroke:#1b5e20,stroke-width:2px
    style plan_task_execute_node fill:#4caf50,stroke:#1b5e20,stroke-width:2px
    style human_review_node fill:#9c27b0,stroke:#4a148c,stroke-width:2px
    style feedback_handler_node fill:#f44336,stroke:#b71c1c,stroke-width:2px
```
