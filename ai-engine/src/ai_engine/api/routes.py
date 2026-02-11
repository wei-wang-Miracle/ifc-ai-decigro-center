"""
FastAPI 路由定义
提供工作流 API 接口
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio

# from ..graph import create_workflow_graph, create_initial_state, AgentState
# from ..graph.nodes.review import handle_review_decision


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
# API 端点
# ========================================

@router.post("/chat", response_model=ChatResponse)
async def start_workflow(request: ChatRequest, x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")):
    """
    功能: 发起新的工作流任务
    参数: request - 包含用户查询、用户ID、会话ID、可选任务ID
    返回: 任务ID、链路追踪ID和执行状态
    
    流程:
    1. 生成 trace_id（每次请求必生成）
    2. 检查是否复用已有 task_id 或生成新 task_id
    3. 创建工作流实例并初始化状态
    4. 运行工作流直到完成或需要审核
    5. 返回结果
    """
    try:
        from ..graph import create_workflow_graph, create_initial_state
        
        # 每次请求生成新的 trace_id（链路追踪）
        trace_id = f"trace_{uuid.uuid4().hex[:16]}"
        
        # 任务 ID 逻辑：如果前端传入且上一任务未完成则复用，否则生成新的
        task_id = request.task_id or f"task_{uuid.uuid4().hex[:12]}"
        
        # 创建工作流
        workflow = create_workflow_graph()
        
        # 初始化状态
        initial_state = create_initial_state(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            task_id=task_id,
            trace_id=trace_id,
            token=x_auth_token,  # 传递 Token
        )
        
        # 配置（LangGraph 内部仍使用 thread_id 概念，但对外隐藏）
        internal_thread_id = f"{request.session_id}_{task_id}"
        config = {"configurable": {"thread_id": internal_thread_id}}
        
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


# 节点名称友好映射
NODE_NAME_MAP = {
    "intent_recognition": "意图识别",
    "planner": "计划制定",
    "executor": "任务执行",
    "responder": "结果汇总",
    "review": "人工审核",
    "feedback": "反馈处理",
}

@router.post("/chat/stream")
async def start_workflow_stream(request: ChatRequest, x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")):
    """
    功能: 发起新的工作流任务 (流式响应)
    参数: request - 包含用户查询
    返回: SSE 流
    """
    from ..graph import create_workflow_graph, create_initial_state

    # 生成 ID
    trace_id = f"trace_{uuid.uuid4().hex[:16]}"
    task_id = request.task_id or f"task_{uuid.uuid4().hex[:12]}"
    
    # 创建工作流
    workflow = create_workflow_graph()
    
    # 初始化状态
    initial_state = create_initial_state(
        query=request.query,
        user_id=request.user_id,
        session_id=request.session_id,
        task_id=task_id,
        trace_id=trace_id,
        token=x_auth_token,
    )
    
    internal_thread_id = f"{request.session_id}_{task_id}"
    config = {"configurable": {"thread_id": internal_thread_id}}

    async def event_generator():
        print(f"[Stream] 开始事件生成: thread_id={internal_thread_id}, query={request.query[:20]}...")
        # 发送 2KB 空格填充，强制代理刷新缓冲区
        yield ":" + " " * 2048 + "\n\n"
        try:
            # 发送初始信息
            yield f"data: {json.dumps({'type': 'meta', 'task_id': task_id, 'trace_id': trace_id})}\n\n"
            
            # 使用 astream_events v2 获取详细事件
            # v2 支持 on_custom_event（Agent 进场等自定义事件），v1 不支持
            current_node = None
            async for event in workflow.astream_events(initial_state, config, version="v2"):
                event_type = event["event"]
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")
                if node_name:
                    current_node = node_name
                
                # 调试日志（上线后可注释）
                if event_type in ["on_custom_event", "on_tool_start", "on_tool_end"]:
                    print(f"[Stream] Event: {event_type}, Name: {event.get('name')}, Data: {str(event.get('data', ''))[:200]}")
                
                if event_type in ["on_node_start", "on_chain_start"]:
                    # 识别节点进入 (astream_events v1 中 node 可能是 chain 也可能是 node)
                    name = event.get("name")
                    # 兼容不同版本的节点名称
                    if name and any(k in name for k in ["planner", "executor", "intent_recognition", "review", "feedback", "responder"]):
                        # 提取核心名称
                        clean_name = name
                        for k in ["planner", "executor", "intent_recognition", "review", "feedback", "responder"]:
                            if k in name:
                                clean_name = k
                                break
                        print(f"[Stream] 节点进场: {clean_name} (原始: {name})")
                        display_name = NODE_NAME_MAP.get(clean_name, clean_name)
                        yield f"data: {json.dumps({'type': 'node_start', 'node': clean_name, 'display_name': display_name})}\n\n"
                        
                elif event_type == "on_tool_start":
                    # 工具调用开始
                    tool_name = event.get("name")
                    from ..registry import get_tool_registry
                    tool_reg = get_tool_registry()
                    # 尝试从摘要中获取别名
                    tool_summary = tool_reg._user_tool_summaries.get(x_auth_token, {}).get(tool_name, {})
                    tool_alias = tool_summary.get("tool_alias", tool_name)
                    
                    print(f"[Stream] 工具调用: {tool_name} (别名: {tool_alias})")
                    yield f"data: {json.dumps({
                        'type': 'tool_start', 
                        'tool': tool_name, 
                        'tool_alias': tool_alias,
                        'input': event.get('data', {}).get('input', {})
                    }, ensure_ascii=False)}\n\n"
                    
                elif event_type == "on_tool_end":
                    # 工具调用结束
                    yield f"data: {json.dumps({
                        'type': 'tool_end', 
                        'tool': event['name'], 
                        'output': str(event['data'].get('output'))
                    }, ensure_ascii=False)}\n\n"
                
                elif event_type == "on_chat_model_start":
                     yield f"data: {json.dumps({'type': 'thinking', 'content': '正在思考...'}, ensure_ascii=False)}\n\n"
                
                elif event_type == "on_custom_event":
                    if event["name"] == "agent_start":
                         agent_name = event['data']['agent']
                         agent_alias = event['data'].get('alias', agent_name)
                         print(f"[Stream] Agent进场: {agent_name} (别名: {agent_alias})")
                         yield f"data: {json.dumps({
                            'type': 'agent_start', 
                            'agent': agent_name,
                            'agent_alias': agent_alias
                        }, ensure_ascii=False)}\n\n"

                elif event_type == "on_chat_model_stream":
                    # 获取流式 chunk
                    chunk = event.get("data", {}).get("chunk")
                    if chunk:
                        content = ""
                        reasoning = ""
                        
                        # 1. 提取推理内容 (Reasoning)
                        # 兼容 Moonshot/DeepSeek 等厂商。LangChain OpenAI 会将其放在 additional_kwargs
                        if hasattr(chunk, "additional_kwargs"):
                            reasoning = chunk.additional_kwargs.get("reasoning_content", "")
                        
                        # 特殊版本或某些封装可能直接放在 reasoning 字段
                        if not reasoning and hasattr(chunk, "reasoning"):
                            reasoning = getattr(chunk, "reasoning", "")
                        
                        # 2. 提取文本内容 (Content)
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        elif isinstance(chunk, dict):
                            content = chunk.get("content", "")
                        
                        if content or reasoning:
                            # 识别当前节点及其属性
                            node_name = event.get("metadata", {}).get("langgraph_node") or current_node
                            
                            is_thought = False
                            is_json = False
                            
                            # 逻辑 A: 任何显式的『推理流』字段都属于思考过程
                            if reasoning:
                                is_thought = True
                            
                            # 逻辑 B: 根据节点名处理 content
                            if node_name == "responder":
                                # 汇总节点：reasoning 属于思考，content 属于最终结果
                                if content:
                                    is_thought = False
                            elif node_name in ["intent_recognition", "planner", "dispatcher"]:
                                # 中间解析/调度节点：产生的结构化数据标记为 is_json 隐藏
                                # dispatcher 输出的是 Agent 名称选择结果，也不应展示
                                if content:
                                    is_thought = True
                                    is_json = True
                            elif node_name == "executor":
                                # 执行器节点：Agent 的 Monologue 属于思考过程
                                if content:
                                    is_thought = True
                            else:
                                # 默认逻辑：如果没有明确节点名，尝试根据是否有 content 来区分
                                # 参考 Kimi 示例：如果没有 content 只有 reasoning，则是思考中
                                if reasoning and not content:
                                    is_thought = True
                                
                            yield f"data: {json.dumps({
                                'type': 'token', 
                                'content': content,
                                'reasoning': reasoning,
                                'node': node_name,
                                'is_thought': is_thought,
                                'is_json': is_json
                            }, ensure_ascii=False)}\n\n"
                
                elif event_type == "on_node_end":
                    # 节点执行结束，发送结果用于调试（标记为 node_result，前端依需展示）
                    node_name = event.get("name")
                    if node_name:
                        output = event.get("data", {}).get("output")
                        yield f"data: {json.dumps({
                            'type': 'node_result',
                            'node': node_name,
                            'output': str(output) # 可能是 JSON 字符串
                        }, ensure_ascii=False)}\n\n"
            
            # 流程结束，获取最终状态
            # 注意: astream_events 不直接返回最终 state，我们需要重新获取或通过 storage 获取
            # 这里简化处理：如果在 _active_workflows 中有记录（需要审核），则返回 pending
            # 否则假设成功。更严谨的做法是 checkpointer.get(config)
            
            # 检查是否需要审核 (从 memory 中检查 active workflows)
            # 由于是 async generator，我们难以直接拿到 workflow.invoke 的返回值
            # 但我们可以通过 checkpointer 读取最新状态
            # 暂时简化：发送完成信号 (前端刷新或结束 loading)
            
            # 获取最终快照
            snapshot = workflow.get_state(config)
            final_message = ""
            require_review = False
            status = "completed"
            
            if snapshot and snapshot.values:
                 # 获取最后的消息
                 steps = snapshot.values.get("step_results", [])
                 msgs = snapshot.values.get("messages", [])
                 if msgs:
                     final_message = msgs[-1].content if hasattr(msgs[-1], 'content') else str(msgs[-1])
                 
                 # 检查 review 状态
                 # 如果我们在 plan_task_execute_node 返回了 require_review=True，它会体现在 messages 或 state 中
                 # 但 snapshot.next 可能会指示下一步是 'review'
                 if snapshot.next and "review" in snapshot.next:
                     require_review = True
                     status = "pending_review"
                     final_message = "任务需要人工审核"
            
            # 如果需要审核，保存状态
            if require_review:
                _active_workflows[task_id] = {
                    "workflow": workflow,
                    "config": config,
                    "state": snapshot.values, # 保存 state values
                    "trace_id": trace_id,
                }

            yield f"data: {json.dumps({
                'type': 'result', 
                'task_id': task_id,
                'status': status,
                'message': final_message,
                'require_review': require_review
            }, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓存
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
        from ..graph.nodes.review import handle_review_decision
        
        # 构建更新状态
        update_state = handle_review_decision(
            state=workflow_data.get("state", {}),
            action=request.action,
            feedback=request.feedback or "",
        )
        
        # 恢复工作流执行
        result = None
        final_message = ""
        require_review = False
        
        async for event in workflow.astream(update_state, config):
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
