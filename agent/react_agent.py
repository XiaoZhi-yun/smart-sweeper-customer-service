from typing import TypedDict  # 用于定义具有固定键和类型的字典结构

from langchain.agents import create_agent  # LangChain 新版统一创建 Agent 的工厂函数
from model.factory import chat_model  # 从工厂获取聊天模型单例
from utils.prompt_loader import load_system_prompts  # 加载系统提示词
from utils.logger_handler import logger  # 全局日志器
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch


class _AgentInput(TypedDict):
    """
    Agent 输入的类型定义，符合 LangChain Runnable 对 InputT 的泛型约束。
    使用 TypedDict 而不是普通 dict，可以获得更好的类型提示和 IDE 检查。
    messages 是消息列表，每条消息是 {"role": "user/assistant", "content": "..."} 格式。
    """
    messages: list[dict[str, str]]


class _AgentContext(TypedDict, total=False):
    """
    Agent 运行时上下文的类型定义。
    total=False 表示所有字段都是可选的，可以只传部分字段。
    report: 是否为报告模式，供中间件读取以决定使用哪套提示词。
    """
    report: bool


class ReactAgent:
    """
    ReAct（Reason + Act）智能体：
    核心思想是 "先思考后行动"：
    - Reason：模型先思考应该做什么（分析用户意图，决定调用哪个工具）
    - Act：调用工具去执行（获取天气、检索知识库、查询数据等）
    - Observe：观察工具返回的结果
    - 循环：根据结果再次推理，直至得出最终答案

    本实现支持：
    - 多轮对话：通过 history 参数传递历史消息
    - 历史压缩：对话过长时自动摘要旧消息，防止超出 token 限制
    - 报告模式：检测到报告意图时切换专用提示词
    - 异常兜底：任何异常都有友好的错误信息返回
    """

    def __init__(self):
        """
        初始化 ReAct Agent。
        组装模型、系统提示词、工具列表和中间件，构建完整的 Agent 执行管线。
        """
        self.model = chat_model  # 保存模型引用，历史压缩时会用到

        # create_agent 是 LangChain 新版统一创建 Agent 的入口
        # 它内部会自动构建 ReAct 循环：模型推理 -> 工具调用 -> 结果观察 -> 再次推理
        # 这是一个状态机循环，直到模型认为可以直接回答而不需要工具时结束
        self.agent = create_agent(
            model=chat_model,                                  # 使用的大模型（阿里通义）
            system_prompt=load_system_prompts(),              # 系统提示词：定义 AI 的人设和行为规则
            tools=[                                           # 工具列表：模型可以自主选择调用的能力
                rag_summarize,                               # RAG 检索工具
                get_weather,                                 # 天气查询工具
                get_user_location,                           # 用户定位工具
                get_user_id,                                 # 用户 ID 获取工具
                get_current_month,                           # 当前月份获取工具
                fetch_external_data,                         # 外部数据查询工具
                fill_context_for_report,                     # 报告模式触发哨兵工具
            ],
            middleware=[                                      # 中间件列表：在 Agent 执行过程中织入逻辑
                monitor_tool,                                # 工具监控：记录工具调用日志、检测报告模式
                log_before_model,                            # 模型前置：记录消息数量、Token 消耗
                report_prompt_switch,                        # 动态提示词：根据上下文切换系统提示词
            ],
        )

    def execute_stream(self, query: str, history: list[dict] | None = None, is_report: bool = False):
        """
        流式执行用户 query，是整个系统的核心方法。
        通过生成器逐段产出模型的回答，实现"打字机"效果。

        :param query: 用户当前输入的问题
        :param history: 历史对话消息列表，格式 [{"role": "user/assistant", "content": "..."}]
                       传 None 表示新对话
        :param is_report: 是否为报告生成场景，中间件会据此切换提示词
        """
        # 1. 构建消息列表：把历史消息复制过来，再追加当前用户 query
        messages = list(history or [])  # 如果 history 为 None 则使用空列表
        messages.append({"role": "user", "content": query})

        # 2. 历史压缩：消息过多时用模型摘要旧消息，防止超出 token 限制
        messages = self._maybe_compress(messages)

        # 3. 组装输入数据和上下文标记
        # input_data 是传给 Agent 的主数据，context_data 是运行时上下文
        input_data: _AgentInput = {"messages": messages}
        context_data: _AgentContext = {"report": is_report}

        # 4. 流式执行，异常兜底
        try:
            # stream_mode="values" 表示每一步都把完整的 messages 快照 yield 出来
            # 另一种模式 stream_mode="messages" 是 token 级别的，更细但信息量少
            # context 参数会被中间件读取，用于动态调整行为
            for step in self.agent.stream(input_data, stream_mode="values", context=context_data):  # type: ignore[arg-type]
                # step 是 Agent 每一步的完整状态快照
                step_msgs = step.get("messages", [])  # 获取当前步骤的所有消息
                if not step_msgs:
                    continue  # 没有消息则跳过
                # 取最后一条消息（即本轮模型最新的输出）
                latest_message = step_msgs[-1]
                if latest_message.content:  # 模型有输出内容
                    # 去除首尾空白并追加换行，yield 出去给前端
                    yield latest_message.content.strip() + "\n"
        except Exception as e:
            # 捕获所有异常，记录日志并返回友好的错误信息
            logger.error(f"Agent 执行异常: {e}", exc_info=True)  # exc_info=True 记录完整堆栈
            yield f"抱歉，服务出现异常：{str(e)}"

    def _maybe_compress(self, messages: list[dict], threshold: int = 12, keep_recent: int = 8) -> list[dict]:
        """
        历史消息压缩：当对话轮次过多时，用模型生成摘要压缩旧消息。
        这样做的目的是减少 token 消耗，避免超出模型的上下文窗口限制。

        策略：
        - 超过 threshold 条消息时触发压缩
        - 只压缩旧消息，保留最近 keep_recent 条消息不压缩
        - 压缩后用一条摘要消息替代所有旧消息

        :param messages: 完整的消息列表
        :param threshold: 触发压缩的消息数量阈值，默认 12 条
        :param keep_recent: 压缩后保留最近 N 条消息，默认 8 条
        :return: 压缩后的消息列表（可能长度不变或变短）
        """
        # 消息数量在阈值以内，直接返回原列表
        if len(messages) <= threshold:
            return messages

        # 分割消息：旧消息做摘要，最近的保留原样
        # messages[:-keep_recent] 取除了最后 keep_recent 条之外的所有消息
        # messages[-keep_recent:] 取最后 keep_recent 条消息
        old = messages[:-keep_recent]
        recent = messages[-keep_recent:]

        try:
            # 把旧消息拼成一段 transcript，让模型生成摘要
            # 格式: "user: 你好\nassistant: 你好！有什么可以帮你的？\n..."
            transcript = "\n".join(f"{m['role']}: {m['content']}" for m in old)
            # 调用模型生成摘要
            summary = self.model.invoke(
                f"请将以下对话历史总结为一段简洁的摘要，保留关键信息：\n{transcript}"
            ).content
            logger.info(f"[历史压缩]{len(old)}条旧消息压缩为摘要，保留最近{len(recent)}条")
            # 用一条摘要消息替代旧消息，和最近消息拼接返回
            # 摘要消息以"【历史摘要】"开头，方便后续识别
            return [{"role": "user", "content": f"【历史摘要】{summary}"}] + recent
        except Exception as e:
            # 压缩失败（如模型调用超时），退化为直接截断
            # 这样做虽然丢失了一些上下文，但保证了对话不中断
            logger.warning(f"[历史压缩]失败，直接截断旧消息: {e}")
            return recent


if __name__ == '__main__':
    # 本地测试入口：直接运行此文件可测试 Agent 输出
    agent = ReactAgent()
    for chunk in agent.execute_stream("给我生成我的使用报告", is_report=True):
        print(chunk, end="", flush=True)