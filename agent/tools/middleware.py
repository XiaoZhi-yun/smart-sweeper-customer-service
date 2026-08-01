from typing import Callable  # 类型提示：表示可调用对象
from utils.prompt_loader import load_system_prompts, load_report_prompts  # 加载两套提示词
from langchain.agents import AgentState  # Agent 的全局状态类型
from langchain.agents.middleware import wrap_tool_call, before_model, dynamic_prompt, ModelRequest  # 三种中间件装饰器
from langchain.tools.tool_node import ToolCallRequest  # 工具调用请求封装
from langchain_core.messages import ToolMessage, AIMessage  # 工具执行结果消息、AI模型输出消息
from langgraph.runtime import Runtime  # 运行时对象，可跨步骤共享 context
from langgraph.types import Command  # 命令类型，用于中断或引导 Agent
from utils.logger_handler import logger  # 全局日志器

# 报告场景的关键词列表
# 用于在 fill_context_for_report 未被模型调用时做意图回退检测
REPORT_KEYWORDS = ["报告", "使用记录", "使用情况", "统计", "报表", "查一下我的", "生成我的"]


# @wrap_tool_call 装饰器：
# 这是一个中间件装饰器，用于"包裹"工具的调用过程。
# 当 Agent 要调用任何工具时，会先经过这个中间件，再执行真正的工具函数。
# 类似 Web 框架中的请求拦截器。
@wrap_tool_call
def monitor_tool(
        request: ToolCallRequest,                                        # 请求封装：含工具名、入参、runtime 等上下文信息
        handler: Callable[[ToolCallRequest], ToolMessage | Command],     # 真正执行工具的函数（由框架自动传入）
) -> ToolMessage | Command:
    """
    工具监控中间件：
    1. 在工具执行前记录调用日志
    2. 在工具执行后记录成功日志
    3. 特殊处理 fill_context_for_report 工具，设置报告模式标记
    4. 异常时记录错误日志并抛出
    """
    # 记录工具调用信息，便于调试和审计
    logger.info(f"[tool monitor]执行工具：{request.tool_call['name']}")
    logger.info(f"[tool monitor]传入参数：{request.tool_call['args']}")

    try:
        # handler 是框架传入的"下一个处理器"，调用它才会真正执行工具函数
        result = handler(request)
        logger.info(f"[tool monitor]工具{request.tool_call['name']}调用成功")

        # 关键逻辑：fill_context_for_report 是一个"哨兵工具"
        # 模型只要调用了它，就说明用户确实想生成报告
        # 此时把 runtime.context['report'] 置为 True，供下一步 dynamic_prompt 读取
        # 这是中间件间通过 runtime.context 进行通信的机制
        if request.tool_call['name'] == "fill_context_for_report":
            request.runtime.context["report"] = True  # 设置标记
            logger.info("[tool monitor]fill_context_for_report 触发报告模式")

        return result  # 返回工具执行结果
    except Exception as e:
        # 工具执行失败时记录错误日志
        logger.error(f"工具{request.tool_call['name']}调用失败，原因：{str(e)}")
        raise e  # 重新抛出异常，让框架处理


# @before_model 装饰器：
# 这是一个中间件装饰器，在每次 LLM（大语言模型）调用前执行。
# 可以在这里做日志记录、参数修改、上下文注入等操作。
@before_model
def log_before_model(
        state: AgentState,   # Agent 全局状态，包含所有历史消息、工具结果等
        runtime: Runtime,    # 运行时对象，可跨步骤共享 context 数据
):
    """
    模型前置中间件：
    1. 记录即将调用模型时的消息数量
    2. 记录最后一条消息的内容（DEBUG 级别）
    3. 统计上一轮模型调用的 Token 消耗
    """
    msg_count = len(state['messages'])  # 当前对话历史的消息总数
    logger.info(f"[log_before_model]即将调用模型，带有{msg_count}条消息。")

    # 获取最后一条消息，通常是上一轮模型的输出或工具的返回结果
    last_msg = state['messages'][-1]
    logger.debug(f"[log_before_model]{type(last_msg).__name__} | {last_msg.content.strip()}")

    # Token 统计：向前遍历找到最近的 AIMessage，从其 usage_metadata 提取消耗数据
    # 不能只看 last_msg，因为 last_msg 往往是 HumanMessage 或 ToolMessage
    # 注意：阿里通义把 token 数据放在 response_metadata['token_usage'] 中，
    # usage_metadata 属性存在但为 None，需要从 response_metadata 取
    try:
        for msg in reversed(state['messages']):
            if isinstance(msg, AIMessage):
                usage = None
                # 优先取 usage_metadata（通用标准）
                if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                    usage = msg.usage_metadata
                # 回退取 response_metadata['token_usage']（阿里通义特有）
                elif hasattr(msg, 'response_metadata') and msg.response_metadata:
                    usage = msg.response_metadata.get('token_usage')
                
                if usage:
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    total = input_tokens + output_tokens
                    logger.info(f"[token usage]模型消耗 - 输入: {input_tokens}, 输出: {output_tokens}, 合计: {total}")
                break
    except Exception:
        pass

    return None  # 返回 None 表示不修改任何数据


# @dynamic_prompt 装饰器：
# 这是一个中间件装饰器，在每次模型调用前动态决定使用哪个 system prompt。
# 可以根据上下文、用户身份、场景等因素切换不同的提示词。
@dynamic_prompt
def report_prompt_switch(request: ModelRequest):
    """
    动态提示词中间件：三级检测决定是否切换到报告生成模式。
    
    检测优先级（从高到低）：
    - 一级：runtime.context 中的 report 标记（最可靠）
      来源1：app.py 在 execute_stream 时传入的 is_report 参数
      来源2：monitor_tool 中间件检测到 fill_context_for_report 工具调用
    - 二级：关键词回退检测（防止标记遗漏的兜底方案）
      扫描用户最新消息是否包含报告相关关键词
    
    返回值：
    - 报告模式：返回 load_report_prompts() 加载的报告专用提示词
    - 普通模式：返回 load_system_prompts() 加载的通用系统提示词
    """
    # 一级检测：从 runtime.context 读取 report 标记
    # 这个标记可能来自 app.py 的 is_report 参数，或 monitor_tool 的设置
    is_report = request.runtime.context.get("report", False)

    # 二级检测：关键词回退检测
    # 如果一级没有检测到，尝试从用户消息内容判断
    if not is_report:
        try:
            last_user_msg = ""
            if hasattr(request, 'messages'):
                # 从最新往回遍历消息列表，找到最近的一条 user 消息
                # 因为最后一条可能是 assistant 消息或工具消息
                for msg in reversed(request.messages):
                    if hasattr(msg, 'role') and msg.role == 'user':
                        last_user_msg = msg.content
                        break
            # 检查用户消息是否包含任意一个报告关键词
            if any(kw in last_user_msg for kw in REPORT_KEYWORDS):
                logger.info(f"[report_prompt_switch]关键词匹配触发报告模式: {last_user_msg}")
                is_report = True
        except Exception:
            pass  # 关键词检测失败不影响主流程

    # 根据检测结果返回不同的系统提示词
    if is_report:
        return load_report_prompts()   # 报告生成专用提示词：更注重数据统计和格式
    return load_system_prompts()       # 通用系统提示词：面向日常对话场景