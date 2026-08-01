import os  # 文件路径检查
from datetime import datetime  # 获取当前系统时间
from utils.logger_handler import logger  # 全局日志器
from langchain_core.tools import tool  # LangChain 的工具装饰器，把普通函数转为 Agent 可调用的工具
from rag.rag_service import RagSummarizeService  # RAG 总结服务
import random  # 随机数，用于模拟数据
from utils.config_handler import agent_conf  # Agent 相关配置
from utils.path_tool import get_abs_path  # 相对路径转绝对路径

# 全局 RAG 服务实例，所有工具共享（单例模式）
# 这里在模块加载时就创建，因为 RAG 服务初始化不需要参数
rag = RagSummarizeService()

# 模拟数据池：用户 ID 列表
# 实际项目中应该从数据库或 token 解析中获取真实用户 ID
user_ids = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010"]

# 外部数据缓存：{user_id: {month: {特征, 效率, 耗材, 对比}}}
# 使用全局字典做缓存，避免每次查询都读文件
# 结构是三层嵌套：用户ID -> 月份 -> 各项指标
external_data = {}


# @tool 装饰器的作用：
# 1. 把普通 Python 函数转换为 LangChain Tool 对象
# 2. description 参数是给模型看的"工具说明书"，模型据此决定何时调用此工具
# 3. 函数签名的类型注解会自动成为工具的参数定义
@tool(description="从向量存储中检索参考资料，返回专业知识内容")
def rag_summarize(query: str) -> str:
    """
    RAG 检索工具：
    用户提问 -> 向量库找相关资料 -> 拼装上下文 -> 模型总结 -> 返回答案。
    这是 Retrieval-Augmented Generation 的核心实现。
    """
    return rag.rag_summarize(query)


@tool(description="获取指定城市的天气，返回天气详情字符串")
def get_weather(city: str) -> str:
    """
    天气查询工具：
    目前返回硬编码的模拟数据，方便调试。
    生产环境应对接真实的天气 API（如和风天气、高德天气等）。
    """
    return f"城市{city}天气为晴天，气温26摄氏度，空气湿度50%，南风1级，AQI21，最近6小时降雨概率极低"


@tool(description="获取用户所在城市名称，返回城市名字符串")
def get_user_location() -> str:
    """
    定位工具：
    目前随机返回一个城市。
    实际项目中应该从用户登录信息或 IP 定位获取真实城市。
    """
    return random.choice(["深圳", "合肥", "杭州"])


@tool(description="获取当前用户的ID，返回用户ID字符串")
def get_user_id() -> str:
    """
    用户 ID 工具：
    随机从预设列表中挑一个 ID。
    实际项目中应该从 session 或 token 中解析真实用户 ID。
    """
    return random.choice(user_ids)


@tool(description="获取当前系统月份，格式为YYYY-MM")
def get_current_month() -> str:
    """
    月份工具：返回系统当前年月。
    格式为 YYYY-MM（如 2025-01），保证报告中的时间准确。
    """
    return datetime.now().strftime("%Y-%m")


def _load_external_data():
    """
    从 CSV 文件加载外部使用记录到内存缓存。
    使用懒加载策略：只在第一次需要时加载，之后缓存在内存中。
    CSV 列顺序：用户ID, 特征, 效率, 耗材, 对比, 月份
    """
    if external_data:
        return  # 已加载过则跳过，避免重复读取文件

    # 获取外部数据文件的绝对路径
    external_data_path = get_abs_path(agent_conf["external_data_path"])
    if not os.path.exists(external_data_path):
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    # 读取 CSV 文件
    with open(external_data_path, "r", encoding="utf-8") as f:
        for line in f.readlines()[1:]:  # 跳过首行表头（字段名称行）
            line = line.strip()  # 去除行首尾的空白符和换行符
            if not line:
                continue  # 跳过空行

            # 按逗号分割为数组
            arr: list[str] = line.split(",")
            if len(arr) < 6:
                logger.warning(f"[CSV解析]行列数不足，跳过：{line}")
                continue  # 行列数不足，跳过此行

            # CSV 列顺序: 用户ID(0), 特征(1), 效率(2), 耗材(3), 对比(4), 月份(5)
            # replace('"', "") 去除可能的引号包裹
            user_id = arr[0].replace('"', "")     # 用户ID
            feature = arr[1].replace('"', "")    # 特征值
            efficiency = arr[2].replace('"', "")  # 效率指标
            consumables = arr[3].replace('"', "") # 耗材数据
            comparison = arr[4].replace('"', "")  # 对比数据
            month = arr[5].replace('"', "")       # 月份

            # 初始化嵌套字典结构
            # external_data 结构: {user_id: {month: {指标字典}}}
            if user_id not in external_data:
                external_data[user_id] = {}

            # 存入三层嵌套结构
            external_data[user_id][month] = {
                "特征": feature,
                "效率": efficiency,
                "耗材": consumables,
                "对比": comparison,
            }


@tool(description="根据用户ID和月份查询外部使用记录，未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    """
    外部数据查询工具：
    1. 确保 CSV 数据已加载到内存缓存
    2. 从缓存中查找指定用户、指定月份的记录
    3. 格式化为易读的字符串返回给模型
    """
    _load_external_data()  # 确保数据已加载（首次调用时触发懒加载）

    try:
        # 从三层嵌套字典中取值：用户ID -> 月份 -> 指标
        record = external_data[user_id][month]
        # 把 dict 格式化为 "特征：xxx，效率：xxx，耗材：xxx，对比：xxx" 的字符串
        # 这样模型更容易阅读和理解结构化数据
        return "，".join([f"{k}：{v}" for k, v in record.items()])
    except KeyError:
        # 查不到数据时返回空字符串，模型会据此判断数据不存在
        logger.warning(f"[fetch_external_data]未检索到用户{user_id}在{month}的记录")
        return ""


@tool(description="无入参，调用后触发中间件切换到报告生成模式")
def fill_context_for_report():
    """
    哨兵工具（Sentinel Tool）：
    这个工具本身不做事，它的存在意义是作为一个"信号"。
    
    工作原理：
    1. 模型在规划工具调用时，如果判断用户想要生成报告
    2. 模型会"主动调用"这个无入参的工具
    3. monitor_tool 中间件监听到这个调用
    4. 把 runtime.context['report'] 置为 True
    5. 下一轮 report_prompt_switch 中间件读取到这个标记
    6. 切换到报告生成专用的提示词
    
    这是一种"间接通信"的设计模式，用工具调用作为信号传递机制。
    """
    return "已切换至报告生成模式"