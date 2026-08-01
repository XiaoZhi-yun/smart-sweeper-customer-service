"""
配置加载模块：
读取各个 yml 配置文件，并暴露为全局变量，供其他模块直接 import 使用。

设计思路：
- 统一管理所有配置文件的加载
- 模块加载时立即读取配置，其他模块 import 时可直接使用
- 避免在各个模块中重复写文件读取逻辑
"""
import yaml  # YAML 解析库
from utils.path_tool import get_abs_path  # 相对路径转绝对路径

def _load_yaml(config_path: str, encoding: str = "utf-8") -> dict:
    """
    通用 yaml 加载方法。
    使用 safe_load 而不是 load，更安全，防止恶意代码执行。
    
    :param config_path: yaml 文件的绝对路径
    :param encoding: 文件编码，默认 utf-8
    :return: 解析后的字典
    """
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.safe_load(f)


def load_rag_config(config_path: str = get_abs_path("config/rag.yml"), encoding: str = "utf-8"):
    """
    加载 RAG（检索增强生成）相关配置。
    包含：聊天模型名称、嵌入模型名称等。
    """
    return _load_yaml(config_path, encoding)


def load_chroma_config(config_path: str = get_abs_path("config/chroma.yml"), encoding: str = "utf-8"):
    """
    加载 Chroma 向量库相关配置。
    包含：集合名、数据目录、分片参数、检索参数等。
    """
    return _load_yaml(config_path, encoding)


def load_prompts_config(config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"):
    """
    加载提示词路径配置。
    包含：系统提示词、RAG 提示词、报告提示词的文件路径。
    """
    return _load_yaml(config_path, encoding)


def load_agent_config(config_path: str = get_abs_path("config/agent.yml"), encoding: str = "utf-8"):
    """
    加载 Agent 相关配置。
    包含：外部数据文件路径等。
    """
    return _load_yaml(config_path, encoding)


# 模块加载时就把所有配置读好，其他模块直接用 xxx_conf 即可
# 这种做法的好处是：配置文件只在程序启动时读取一次，后续使用都是内存读取
rag_conf = load_rag_config()      # RAG 相关配置
chroma_conf = load_chroma_config()  # Chroma 向量库配置
prompts_conf = load_prompts_config()  # 提示词路径配置
agent_conf = load_agent_config()    # Agent 相关配置

if __name__ == '__main__':
    # 本地调试入口：运行此文件可测试配置加载
    print(rag_conf["chat_model_name"])