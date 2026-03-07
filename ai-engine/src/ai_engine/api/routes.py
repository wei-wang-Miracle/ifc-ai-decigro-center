"""
FastAPI 路由定义
提供工作流 API 接口
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio

# from ..graph import create_workflow_graph, create_initial_state, AgentState
# from ..graph.nodes.human_review_node import handle_review_decision


# ========================================
# API 路由器
# ========================================
router = APIRouter(prefix="/api/v1/workflow", tags=["Workflow"])


# ========================================
# 请求/响应模型
# ========================================

class ChatRequest(BaseModel):
    """
    功能: 发起任务请求模型
    """
    query: str = Field(..., description="用户输入的任务描述")
    user_id: str = Field(..., description="用户标识")
    session_id: str = Field(..., description="会话标识")
    task_id: Optional[str] = Field(default=None, description="任务标识（可选，若上一任务未完成则复用）")


class ChatResponse(BaseModel):
    """
    功能: 发起任务响应模型
    """
    task_id: str = Field(..., description="任务标识")
    trace_id: str = Field(..., description="链路追踪 ID")
    status: str = Field(..., description="执行状态")
    message: str = Field(..., description="响应消息")
    require_review: bool = Field(default=False, description="是否需要人工审核")


class ReviewRequest(BaseModel):
    """
    功能: 提交审核请求模型
    """
    action: str = Field(..., description="审核动作: approve 或 reject")
    feedback: Optional[str] = Field(default="", description="审核反馈（驳回时必填）")


class ReviewResponse(BaseModel):
    """
    功能: 审核响应模型
    """
    task_id: str
    trace_id: str
    status: str
    message: str


class PendingReview(BaseModel):
    """
    功能: 待审核任务信息
    """
    task_id: str
    trace_id: str
    query: str
    current_step: str
    tools_called: list[str]
    context: str


class PendingReviewsResponse(BaseModel):
    """
    功能: 待审核任务列表响应
    """
    count: int
    reviews: list[PendingReview]


# ========================================
# 工作流实例存储（简单内存存储，生产环境应使用 Redis）
# ========================================
_active_workflows: dict[str, dict] = {}


# ========================================
# 人机回环：关键词 + LLM 意图检测
# ========================================

_APPROVE_KEYWORDS = [
    "通过", "批准", "确认", "同意", "好的", "可以", "继续", "执行吧",
    "approve", "yes", "ok", "没问题",
]
_REJECT_KEYWORDS = [
    "驳回", "拒绝", "不同意", "不可以", "不行", "停止", "取消",
    "reject", "no", "算了", "不要", "重新规划", "重来", "换个",
    "撤", "撤销", "修改", "调整", "重点关注",
]

# 否定前缀：approve 关键词前出现这些字，视为否定，交 LLM 处理
_NEGATION_PREFIXES = ["不", "没", "别", "勿", "莫"]

_REVIEW_INTENT_PROMPT = """判断以下用户回复是批准(approve)还是拒绝/修改(reject)某个AI待执行操作。

当前正在执行的任务：{current_task}

判断规则：
- approve：用户对当前任务表示认可、同意、确认，希望继续执行
- reject：用户否定、修改、调整当前任务，或者提出了涉及不同主体/目标的新需求（即使语气友好，只要任务主体或目标发生了变化，也应归为 reject）

用户回复：{query}

只返回 "approve" 或 "reject"，无需其他任何内容。"""


def _classify_review_by_keywords(query: str) -> str | None:
    """关键词优先检测审核意图，返回 'approve'/'reject'/None（模糊待LLM处理）

    策略：
    1. reject 优先检查，避免否定句被 approve 关键词抢先命中
    2. approve 关键词加否定前缀保护，命中后检查前 2 字符是否含否定词，有则回落 LLM
    3. 单字、短词等容易误判的词不列入关键词，由 LLM 兜底处理
    """
    q = query.strip().lower()

    # reject 优先：含明确否定/修改意图的词直接判定
    for kw in _REJECT_KEYWORDS:
        if kw.lower() in q:
            return "reject"

    # approve：检查关键词是否被否定前缀修饰（如「不好」中的「好」应回落 LLM）
    for kw in _APPROVE_KEYWORDS:
        kw_lower = kw.lower()
        idx = q.find(kw_lower)
        if idx == -1:
            continue
        prefix_window = q[max(0, idx - 2):idx]
        if any(neg in prefix_window for neg in _NEGATION_PREFIXES):
            continue
        return "approve"

    return None


async def _classify_review_by_llm(query: str, current_task: str) -> str:
    """LLM 兜底检测审核意图（仅在关键词匹配失败时调用，节省 token）"""
    try:
        from ..config import get_settings
        from langchain_openai import ChatOpenAI
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=0.0,
            max_tokens=10,
        )
        prompt = _REVIEW_INTENT_PROMPT.format(current_task=current_task, query=query)
        response = await llm.ainvoke(prompt)
        result = response.content.strip().lower()
        return "approve" if "approve" in result else "reject"
    except Exception as e:
        print(f"[ReviewDetect] LLM 检测失败，默认 reject: {e}")
        return "reject"


async def _detect_review_intent(query: str, current_task: str = "") -> tuple[str, str]:
    """
    检测用户回复中的审核意图（关键词优先 + LLM 兜底）
    返回: (action, feedback)  action='approve'|'reject'
    """
    action = _classify_review_by_keywords(query)
    if action is None:
        print(f"[ReviewDetect] 关键词未命中，调用 LLM 检测...")
        action = await _classify_review_by_llm(query, current_task)
    feedback = query if action == "reject" else ""
    print(f"[ReviewDetect] 意图={action}, feedback={feedback[:40] if feedback else ''}")
    return action, feedback


# ========================================
# API 端点
# ========================================

@router.post("/chat", response_model=ChatResponse)
async def start_workflow(
    request: ChatRequest,
    req: Request,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
):
    """
    功能: 发起新的工作流任务（非流式）
    """
    try:
        from ..graph import create_initial_state

        trace_id = f"trace_{uuid.uuid4().hex[:16]}"
        task_id = request.task_id or f"task_{uuid.uuid4().hex[:12]}"

        # 从 app.state 获取预初始化的持久化 workflow
        workflow = getattr(req.app.state, "workflow", None)
        if workflow is None:
            from ..graph import create_workflow_graph
            workflow = create_workflow_graph()

        initial_state = create_initial_state(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            task_id=task_id,
            trace_id=trace_id,
            token=x_auth_token,
        )

        config = {"configurable": {"thread_id": request.session_id}}
        
        # 运行工作流
        result = None
        require_review = False
        final_message = ""
        
        async for event in workflow.astream(initial_state, config):
            result = event
            
            # 检查是否有节点输出
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    # 检查是否需要审核
                    if node_output.get("require_review"):
                        require_review = True
                        final_message = "任务需要人工审核"
                        break
                    
                    # 获取消息
                    messages = node_output.get("messages", [])
                    if messages:
                        final_message = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        
        # 存储工作流状态（用于后续审核），key 使用 task_id
        if require_review:
            _active_workflows[task_id] = {
                "workflow": workflow,
                "config": config,
                "state": result,
                "trace_id": trace_id,
            }
        
        return ChatResponse(
            task_id=task_id,
            trace_id=trace_id,
            status="pending_review" if require_review else "completed",
            message=final_message or "任务已完成",
            require_review=require_review,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")


# 节点名称友好映射（覆盖所有注册节点）
NODE_NAME_MAP = {
    "intent_recognition": "意图识别",
    "dispatcher": "任务调度",
    "planner": "计划制定",
    "executor": "任务执行",
    "normal": "智能对话",
    "responder": "结果汇总",
    "review": "人工审核",
    "feedback": "反馈处理",
}

# 所有需要在前端展示进度的节点（dispatcher 是内部路由节点，不展示）
_VISIBLE_NODES = {"intent_recognition", "planner", "executor", "normal", "responder", "review", "feedback"}

# 产生结构化 JSON 输出、不应在前端展示为正文的节点
_JSON_NODES = {"intent_recognition", "planner", "dispatcher"}

# 产生中间思考过程、应在 Agent 面板展示而非主聊天流的节点
_THOUGHT_NODES = {"executor", "normal"}

@router.post("/chat/stream")
async def start_workflow_stream(
    request: ChatRequest,
    req: Request,
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
):
    """
    功能: 发起新的工作流任务 (流式响应)
    若 task_id 对应一个待 review 的工作流，则作为 review 响应处理（对话式人机回环）。
    """
    from ..graph import create_initial_state

    trace_id = f"trace_{uuid.uuid4().hex[:16]}"

    # 从 app.state 获取预初始化的持久化 workflow（降级为临时 MemorySaver）
    _app_workflow = getattr(req.app.state, "workflow", None)
    if _app_workflow is None:
        from ..graph import create_workflow_graph
        _app_workflow = create_workflow_graph()

    # ── 判断是否为 review 响应 ────────────────────────────────────────
    is_review_response = bool(
        request.task_id and request.task_id in _active_workflows
    )

    if is_review_response:
        task_id = request.task_id
        wf_data = _active_workflows[task_id]
        workflow = wf_data["workflow"]
        config = wf_data["config"]
        _initial_state = None   # review 场景不需要
    else:
        task_id = request.task_id or f"task_{uuid.uuid4().hex[:12]}"
        workflow = _app_workflow

        # 从 ContextManager 获取跨轮次上下文摘要，注入初始状态
        from ..context import get_context_manager
        ctx_mgr = get_context_manager()

        # 从 checkpointer 恢复的 messages 构建短期记忆摘要
        # （此处暂用轻量摘要；messages 会在节点执行时由 checkpointer 自动恢复）
        session_config = {"configurable": {"thread_id": request.session_id}}
        try:
            snapshot = await workflow.aget_state(session_config)
            existing_messages = snapshot.values.get("messages", []) if snapshot and snapshot.values else []
        except Exception:
            existing_messages = []

        ctx_window = ctx_mgr.build_context_window(
            session_id=request.session_id,
            messages=existing_messages,
            current_query=request.query,
        )

        _initial_state = create_initial_state(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            task_id=task_id,
            trace_id=trace_id,
            token=x_auth_token,
            context_turns_summary=ctx_window.recent_turns_summary,
            context_entities_summary=ctx_window.tracked_entities_summary,
        )
        # thread_id 统一为 session_id，checkpointer 按 session 隔离
        config = {"configurable": {"thread_id": request.session_id}}

    async def event_generator():
        print(f"[Stream] 开始事件生成: task_id={task_id}, review={is_review_response}, query={request.query[:20]}...")
        # 发送 2KB 空格填充，强制代理刷新缓冲区
        yield ":" + " " * 2048 + "\n\n"
        try:
            yield f"data: {json.dumps({'type': 'meta', 'task_id': task_id, 'trace_id': trace_id})}\n\n"

            from ..registry import get_tool_registry
            tool_reg = get_tool_registry()

            current_node = None
            active_step_id = None

            # ── 确定状态输入 ──────────────────────────────────────────
            if is_review_response:
                # 检测用户意图（关键词优先 + LLM 兜底）
                # 从已保存的 state 中提取当前任务查询，作为"任务主体"上下文传入 LLM
                current_task = wf_data.get("state", {}).get("query", "")
                action, feedback = await _detect_review_intent(request.query, current_task)
                # 移除 active_workflows 记录（后面若还需 review 会重新加入）
                if task_id in _active_workflows:
                    del _active_workflows[task_id]
                # 用 Command(resume=...) 恢复图执行，将审核结果直接传入 interrupt() 的返回值
                from langgraph.types import Command as LGCommand
                state_input = LGCommand(resume={"action": action, "feedback": feedback})
                # 发送一个轻量提示节点，让前端有视觉反馈
                stage_name = "审核确认" if action == "approve" else "反馈处理"
                stage_node = "review" if action == "approve" else "feedback"
                yield f"data: {json.dumps({'type': 'node_start', 'node': stage_node, 'display_name': stage_name})}\n\n"
            else:
                state_input = _initial_state

            # ── 事件流 ───────────────────────────────────────────────
            async for event in workflow.astream_events(state_input, config, version="v2"):
                event_type = event["event"]
                metadata = event.get("metadata", {})
                ev_node = metadata.get("langgraph_node")
                if ev_node:
                    current_node = ev_node

                # ── 节点进入 ──────────────────────────────────────────
                if event_type == "on_chain_start":
                    name = event.get("name", "")
                    if name in _VISIBLE_NODES:
                        print(f"[Stream] 节点进场: {name}")
                        yield f"data: {json.dumps({'type': 'node_start', 'node': name, 'display_name': NODE_NAME_MAP.get(name, name)})}\n\n"

                # ── 工具调用开始 ──────────────────────────────────────
                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "")
                    tool_summary = tool_reg._user_tool_summaries.get(x_auth_token, {}).get(tool_name, {})
                    tool_alias = tool_summary.get("tool_alias", tool_name)
                    tool_node = ev_node or current_node
                    print(f"[Stream] 工具调用开始: {tool_name} | node={tool_node} | step={active_step_id}")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name, 'tool_alias': tool_alias, 'node': tool_node, 'step_id': active_step_id, 'input': event.get('data', {}).get('input', {})}, ensure_ascii=False)}\n\n"

                # ── 工具调用结束 ──────────────────────────────────────
                elif event_type == "on_tool_end":
                    tool_node = ev_node or current_node
                    tool_name = event["name"]
                    output = event["data"].get("output")
                    output_str = str(output) if output is not None else ""
                    tool_summary = tool_reg._user_tool_summaries.get(x_auth_token, {}).get(tool_name, {})
                    tool_alias = tool_summary.get("tool_alias", tool_name)
                    print(f"[Stream] 工具调用结束: {tool_name} | node={tool_node} | step={active_step_id}")
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': tool_name, 'tool_alias': tool_alias, 'node': tool_node, 'step_id': active_step_id, 'output': output_str}, ensure_ascii=False)}\n\n"

                # ── 自定义事件（agent_start / agent_end）─────────────
                elif event_type == "on_custom_event":
                    ev_name = event["name"]
                    if ev_name == "agent_start":
                        agent_name = event["data"]["agent"]
                        agent_alias = event["data"].get("alias", agent_name)
                        step_id = event["data"].get("step_id", "")
                        active_step_id = step_id
                        print(f"[Stream] Agent 进场: {agent_name} ({agent_alias}) step={step_id}")
                        yield f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name, 'agent_alias': agent_alias, 'step_id': step_id}, ensure_ascii=False)}\n\n"
                    elif ev_name == "agent_end":
                        agent_name = event["data"]["agent"]
                        step_id = event["data"].get("step_id", "")
                        success = event["data"].get("success", True)
                        if active_step_id == step_id:
                            active_step_id = None
                        print(f"[Stream] Agent 结束: {agent_name} step={step_id} success={success}")
                        yield f"data: {json.dumps({'type': 'agent_end', 'agent': agent_name, 'step_id': step_id, 'success': success}, ensure_ascii=False)}\n\n"

                # ── 模型流式 token ────────────────────────────────────
                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if not chunk:
                        continue

                    content = ""
                    reasoning = ""

                    if hasattr(chunk, "additional_kwargs"):
                        reasoning = chunk.additional_kwargs.get("reasoning_content", "")
                    if not reasoning and hasattr(chunk, "reasoning"):
                        reasoning = getattr(chunk, "reasoning", "") or ""

                    if hasattr(chunk, "content"):
                        content = chunk.content or ""
                    elif isinstance(chunk, dict):
                        content = chunk.get("content", "")

                    if not content and not reasoning:
                        continue

                    node_name = ev_node or current_node

                    is_thought = bool(reasoning)
                    is_json = False

                    if node_name in _JSON_NODES:
                        is_thought = True
                        is_json = True
                    elif node_name in _THOUGHT_NODES:
                        if content:
                            is_thought = True

                    yield f"data: {json.dumps({'type': 'token', 'content': content, 'reasoning': reasoning, 'node': node_name, 'is_thought': is_thought, 'is_json': is_json}, ensure_ascii=False)}\n\n"

                # ── 节点结束 ──────────────────────────────────────────
                elif event_type == "on_chain_end":
                    name = event.get("name", "")
                    if name in _VISIBLE_NODES:
                        output = event.get("data", {}).get("output")
                        yield f"data: {json.dumps({'type': 'node_result', 'node': name, 'output': str(output)}, ensure_ascii=False)}\n\n"

                        if name == "intent_recognition" and output is not None:
                            try:
                                update = getattr(output, "update", {}) or {}
                                intent = update.get("intent")
                                if intent:
                                    intent_type = getattr(intent, "intent_type", None)
                                    confidence = getattr(intent, "confidence", None)
                                    entities = getattr(intent, "entities", {})
                                    parts = [f"意图类型：**{intent_type}**（置信度 {confidence:.0%}）"]
                                    if entities:
                                        ent_str = "、".join(f"{k}={v}" for k, v in entities.items())
                                        parts.append(f"提取实体：{ent_str}")
                                    clarify = getattr(intent, "clarification_needed", False)
                                    if clarify:
                                        q = getattr(intent, "clarification_question", "")
                                        parts.append(f"需要澄清：{q}")
                                    thinking_text = "\n".join(parts)
                                    yield f"data: {json.dumps({'type': 'node_thinking', 'node': name, 'thinking': thinking_text}, ensure_ascii=False)}\n\n"
                            except Exception as ex:
                                print(f"[Stream] 提取 intent_recognition 思考内容失败: {ex}")

                        elif name == "planner" and output is not None:
                            try:
                                update = getattr(output, "update", {}) or {}
                                plan = update.get("plan", [])
                                reasoning = update.get("plan_reasoning", "")
                                parts = []
                                if reasoning:
                                    parts.append(f"**规划思路**\n{reasoning}")
                                if plan:
                                    steps_desc = "\n".join(
                                        f"**步骤 {i+1}**：{getattr(s, 'description', str(s))}（由 {getattr(s, 'assigned_agent', '?')} 执行）"
                                        for i, s in enumerate(plan)
                                    )
                                    parts.append(f"**执行步骤**\n{steps_desc}")
                                if parts:
                                    yield f"data: {json.dumps({'type': 'node_thinking', 'node': name, 'thinking': chr(10).join(parts)}, ensure_ascii=False)}\n\n"
                            except Exception as ex:
                                print(f"[Stream] 提取 planner 思考内容失败: {ex}")

            # ── 流结束：读取最终快照 ───────────────────────────────────
            snapshot = await workflow.aget_state(config)
            final_message = ""
            require_review = False
            status = "completed"

            if snapshot and snapshot.values:
                msgs = snapshot.values.get("messages", [])
                if msgs:
                    final_message = msgs[-1].content if hasattr(msgs[-1], "content") else str(msgs[-1])
                if snapshot.next and "review" in snapshot.next:
                    require_review = True
                    status = "pending_review"
                    # final_message 此时已是 dispatcher 生成的对话式审核提示，无需覆盖
                    if not final_message:
                        final_message = "需要您确认后才能继续。请回复「通过」批准，或描述修改意见。"

            if require_review:
                _active_workflows[task_id] = {
                    "workflow": workflow,
                    "config": config,
                    "state": snapshot.values,
                    "trace_id": trace_id,
                }

            yield f"data: {json.dumps({'type': 'result', 'task_id': task_id, 'status': status, 'message': final_message, 'require_review': require_review}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"[Stream] 异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
        }
    )


@router.get("/pending_reviews", response_model=PendingReviewsResponse)
async def get_pending_reviews():
    """
    功能: 获取所有待审核的任务列表
    参数: 无
    返回: 待审核任务列表
    """
    pending_reviews = []
    
    for task_id, workflow_data in _active_workflows.items():
        state = workflow_data.get("state", {})
        trace_id = workflow_data.get("trace_id", "")
        
        # 从状态中提取相关信息
        query = ""
        current_step = ""
        tools_called = []
        
        # 遍历状态获取信息
        for node_name, node_state in state.items():
            if isinstance(node_state, dict):
                if "query" in node_state:
                    query = node_state["query"]
                if "plan" in node_state and node_state["plan"]:
                    plan = node_state["plan"]
                    current_index = node_state.get("current_step_index", 0)
                    if current_index < len(plan):
                        current_step = plan[current_index].description
                if "step_results" in node_state:
                    for result in node_state["step_results"]:
                        tools_called.extend(result.tools_called)
        
        pending_reviews.append(PendingReview(
            task_id=task_id,
            trace_id=trace_id,
            query=query,
            current_step=current_step,
            tools_called=tools_called,
            context="待审核",
        ))
    
    return PendingReviewsResponse(
        count=len(pending_reviews),
        reviews=pending_reviews,
    )


@router.post("/review/{task_id}", response_model=ReviewResponse)
async def submit_review(task_id: str, request: ReviewRequest):
    """
    功能: 提交人工审核结果
    参数:
        task_id - 任务ID
        request - 审核动作和反馈
    返回: 审核结果和后续状态
    
    动作:
    - approve: 审核通过，继续执行
    - reject: 审核驳回，需要提供反馈
    """
    # 检查任务是否存在
    if task_id not in _active_workflows:
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在或已完成")
    
    workflow_data = _active_workflows[task_id]
    workflow = workflow_data["workflow"]
    config = workflow_data["config"]
    trace_id = workflow_data.get("trace_id", "")
    
    # 验证请求
    if request.action.lower() not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="action 必须是 'approve' 或 'reject'")
    
    if request.action.lower() == "reject" and not request.feedback:
        raise HTTPException(status_code=400, detail="驳回时必须提供 feedback")
    
    try:
        from langgraph.types import Command as LGCommand

        # 用 Command(resume=...) 恢复图执行，将审核结果传入 interrupt() 的返回值
        resume_input = LGCommand(resume={"action": request.action, "feedback": request.feedback or ""})

        # 恢复工作流执行
        result = None
        final_message = ""
        require_review = False

        async for event in workflow.astream(resume_input, config):
            result = event
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    if node_output.get("require_review"):
                        require_review = True
                    messages = node_output.get("messages", [])
                    if messages:
                        final_message = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        
        # 如果还需要审核，更新状态
        if require_review:
            _active_workflows[task_id]["state"] = result
            status = "pending_review"
        else:
            # 任务完成，移除记录
            del _active_workflows[task_id]
            status = "completed"
        
        return ReviewResponse(
            task_id=task_id,
            trace_id=trace_id,
            status=status,
            message=final_message or f"审核{request.action}完成",
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理审核失败: {str(e)}")


# ========================================
# 健康检查端点
# ========================================

@router.get("/health")
async def health_check():
    """
    功能: 健康检查端点
    """
    return {
        "status": "healthy",
        "active_workflows": len(_active_workflows),
    }
