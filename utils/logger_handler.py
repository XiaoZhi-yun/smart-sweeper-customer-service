import logging  # Python 标准日志库
from utils.path_tool import get_abs_path  # 相对路径转绝对路径
import os  # 文件操作
from datetime import datetime  # 获取当前日期时间

# 日志保存的根目录
LOG_ROOT = get_abs_path("logs")

# 确保日志的目录存在（不存在就创建）
# exist_ok=True 表示目录已存在时不报错
os.makedirs(LOG_ROOT, exist_ok=True)

# 日志格式：时间 - logger名 - 级别 - 文件名:行号 - 消息
# 示例: 2025-01-15 10:30:00 - agent - INFO - app.py:42 - 正在处理用户请求
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

def get_logger(
        name: str = "agent",           # logger 名称，用于区分不同模块的日志
        console_level: int = logging.INFO,   # 控制台输出级别
        file_level: int = logging.DEBUG,     # 文件输出级别
        log_file=None,                 # 自定义日志文件路径，为 None 时自动生成
) -> logging.Logger:
    """
    创建并配置一个 logger。
    
    功能特性：
    - 同时输出到控制台和文件，方便开发调试和问题排查
    - 控制台默认 INFO 级别：只显示重要日志
    - 文件默认 DEBUG 级别：记录所有细节日志
    - 同一天的日志写入同一个文件，便于按日期归档
    
    :param name: logger 名称
    :param console_level: 控制台日志级别
    :param file_level: 文件日志级别
    :param log_file: 自定义日志文件路径
    :return: 配置好的 Logger 实例
    """
    log = logging.getLogger(name)
    # logger 本身设为最低级别 DEBUG，让各个 handler 自己决定输出什么级别
    # 这样做的好处是可以灵活控制不同输出的日志级别
    log.setLevel(logging.DEBUG)

    # 避免重复添加 Handler（否则日志会打印多遍）
    # 这在模块被多次导入时很常见
    if log.handlers:
        return log

    # 1. 控制台 Handler：把日志输出到终端
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    log.addHandler(console_handler)

    # 2. 文件 Handler：把日志写入文件
    if not log_file:
        # 以当天日期命名日志文件，如 agent_20250115.log
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)
    log.addHandler(file_handler)

    return log


# 快捷获取日志器：其他模块直接 `from utils.logger_handler import logger` 即可
# 使用默认配置创建全局 logger
logger = get_logger()


if __name__ == '__main__':
    # 本地测试入口：运行此文件可测试日志功能
    logger.info("信息日志")
    logger.error("错误日志")
    logger.warning("警告日志")
    logger.debug("调试日志")