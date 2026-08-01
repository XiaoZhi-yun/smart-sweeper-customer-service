from utils.config_handler import prompts_conf  # 提示词路径配置（prompts.yml）
from utils.path_tool import get_abs_path  # 相对路径 -> 绝对路径
from utils.logger_handler import logger  # 全局日志器


def _read_prompt_by_key(key: str, error_prefix: str) -> str:
    """
    通用的提示词文件读取方法。
    消除三个 load_xxx_prompts 函数的重复代码，使用了模板方法模式。
    
    :param key: prompts.yml 中的配置 key，用于查找对应的文件路径
    :param error_prefix: 日志前缀，用于区分是哪个函数报错
    :return: 提示词文件的完整内容字符串
    """
    # Step 1: 从配置中获取提示词文件的相对路径
    try:
        prompt_path = get_abs_path(prompts_conf[key])
    except KeyError as e:
        # 配置中没有对应的 key
        logger.error(f"[{error_prefix}]在yaml配置项中没有{key}配置项")
        raise e

    # Step 2: 读取提示词文件内容
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        # 文件读取失败（如文件不存在、编码错误等）
        logger.error(f"[{error_prefix}]解析提示词出错，{str(e)}")
        raise e     #把异常原封不动地重新抛出，让上层调用者也能感知到失败


def load_system_prompts():
    """
    加载系统提示词（Agent 的人设 / 行为规则）。
    定义 AI 的角色、语气、回答风格等。
    """
    return _read_prompt_by_key("main_prompt_path", "load_system_prompts")


def load_rag_prompts():
    """
    加载 RAG 专用提示词。
    告诉模型如何结合参考资料回答问题，如"请根据参考资料回答，不要编造信息"。
    """
    return _read_prompt_by_key("rag_summarize_prompt_path", "load_rag_prompts")


def load_report_prompts():
    """
    加载报告生成专用提示词。
    用于报告模式下，指导模型如何生成结构化的使用报告。
    """
    return _read_prompt_by_key("report_prompt_path", "load_report_prompts")


if __name__ == '__main__':
    # 本地调试入口：运行此文件可测试提示词加载
    print(load_report_prompts())