"""LLM 实例工厂。

统一管理所有节点的 ChatOpenAI 实例创建，消除各节点散落的重复配置。
连接参数（model、api_key、base_url）从全局 Settings 读取，
各工厂方法只暴露与业务场景相关的差异参数。

业务场景分类：
- deterministic: 需要高确定性的场景（意图识别、Agent 选择、关键词分类）
- creative:      需要创造性的场景（规划、对话、汇总、执行）
- extraction:    信息提取场景（结论提取等），确定性最高且限制输出长度

各节点后续迁移时只需:
    from ...llm_factory import create_deterministic_llm
替代原来的 ChatOpenAI(...) 即可。
"""

from langchain_openai import ChatOpenAI

from .config import get_settings


def create_deterministic_llm(
    temperature: float = 0.1,
    streaming: bool = True,
    **kwargs,
) -> ChatOpenAI:
    """创建高确定性 LLM 实例。

    适用场景：意图识别、Dispatcher Agent 选择等需要稳定输出的节点。
    temperature 默认 0.1，保证输出一致性的同时留少量灵活度。

    Args:
        temperature: 采样温度，默认 0.1。
        streaming: 是否启用流式输出，默认 True。
        **kwargs: 透传给 ChatOpenAI 的额外参数。
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=temperature,
        streaming=streaming,
        **kwargs,
    )


def create_creative_llm(
    streaming: bool = True,
    **kwargs,
) -> ChatOpenAI:
    """创建创造性 LLM 实例。

    适用场景：Planner 规划、Normal 对话、Responder 汇总、Executor 执行。
    temperature 使用全局配置 settings.llm_temperature。

    Args:
        streaming: 是否启用流式输出，默认 True。
        **kwargs: 透传给 ChatOpenAI 的额外参数。
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=settings.llm_temperature,
        streaming=streaming,
        **kwargs,
    )


def create_extraction_llm(
    max_tokens: int = 600,
    **kwargs,
) -> ChatOpenAI:
    """创建信息提取 LLM 实例。

    适用场景：结论提取、关键词分类等需要极确定性且限制输出长度的场景。
    temperature 固定 0.0，streaming 关闭。

    Args:
        max_tokens: 最大输出 token 数，默认 600。
        **kwargs: 透传给 ChatOpenAI 的额外参数。
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=0.0,
        max_tokens=max_tokens,
        **kwargs,
    )
