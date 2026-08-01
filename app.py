import time  # 用于模拟打字机效果的延迟

import streamlit as st  # Streamlit 框架，用于快速搭建 Web UI
from agent.react_agent import ReactAgent  # 导入核心 ReAct 智能体类

# 报告场景关键词列表：用户输入包含任意一个关键词时，自动切换到报告生成模式
REPORT_KEYWORDS = ["报告", "使用记录", "使用情况", "统计", "报表", "查一下我的", "生成我的"]

# ---------- 页面初始化 ----------
st.title("智扫通机器人智能客服")  # 设置页面标题
st.divider()  # 画一条分割线美化界面

# session_state 是 Streamlit 的会话级存储机制
# 它可以在页面刷新后保留数据，类似于前端的 localStorage
# 每个用户浏览器有独立的 session_state
if "agent" not in st.session_state:
    # 首次访问时创建 Agent 实例，后续复用同一个实例
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    # 初始化消息历史列表，用于存储整个对话过程
    # 每条消息格式: {"role": "user/assistant", "content": "消息内容"}
    st.session_state["message"] = []

# ---------- 渲染历史消息 ----------
# 重新加载页面时，把历史消息重新渲染出来，保持对话上下文的连续性
for message in st.session_state["message"]:
    # 根据 role 分别渲染用户消息或助手消息
    st.chat_message(message["role"]).write(message["content"])

# ---------- 用户输入框 ----------
# chat_input 是 Streamlit 的聊天气泡输入框，支持回车发送
prompt = st.chat_input()

if prompt:
    # 1. 先把用户消息显示出来并记录到历史
    # st.chat_message("user") 创建用户消息气泡
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    # 2. 关键词检测：判断用户输入是否包含报告相关关键词
    # any() 只要有一个关键词匹配就返回 True
    is_report = any(kw in prompt for kw in REPORT_KEYWORDS)

    # 3. 取历史消息（不含当前这条）
    # 因为 execute_stream 内部会自动 append 当前 query
    # [:-1] 表示取除了最后一个元素外的所有元素
    conversation_history = list(st.session_state["message"][:-1])

    # 4. 调用 Agent 流式执行，拿到生成器
    response_messages = []  # 用于缓存所有响应片段，最后拼接成完整回答
    with st.spinner("智能客服思考中..."):  # 显示加载动画
        res_stream = st.session_state["agent"].execute_stream(
            query=prompt,
            history=conversation_history,
            is_report=is_report,
        )

        # 5. 定义 capture 函数：逐字吐出模拟打字机效果，同时缓存完整回答
        # generator: Agent 返回的流式生成器
        # cache_list: 用于累积存储所有响应片段的列表
        def capture(generator, cache_list):
            for chunk in generator:  # 遍历生成器产出的每个文本块
                cache_list.append(chunk)  # 把文本块加入缓存列表
                for char in chunk:  # 逐字符 yield，实现打字机效果
                    time.sleep(0.01)  # 10ms 延迟控制打字速度
                    yield char  # 逐字符产出给 Streamlit 渲染

        # 6. write_stream 接收生成器并实时渲染到界面
        # capture() 返回的是生成器，直接传入即可，不需要 lambda 包裹
        st.chat_message("assistant").write_stream(capture(res_stream, response_messages))

        # 7. 拼接完整回答存入历史
        # 如果响应列表为空（如异常情况），使用兜底文案
        full_response = "".join(response_messages) if response_messages else "抱歉，我暂时没有回答上来，请再试一次。"
        st.session_state["message"].append({"role": "assistant", "content": full_response})

        # 8. rerun 让页面重新渲染，把新消息显示出来
        # 因为 Streamlit 是单页面应用，需要 rerun 才能更新界面
        st.rerun()