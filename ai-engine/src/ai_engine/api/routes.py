"""
FastAPI 路由定义
提供工作流 API 接口
"""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel, Field

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
        
        for event in workflow.stream(initial_state, config):
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
        
        for event in workflow.stream(update_state, config):
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
