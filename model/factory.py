from abc import ABC, abstractmethod  # 用于定义抽象基类 + 抽象方法
from typing import Optional  # 可选类型提示
from langchain_core.embeddings import Embeddings  # 文本向量嵌入的基类
from langchain_community.chat_models.tongyi import BaseChatModel  # 通义对话模型基类
from langchain_community.embeddings import DashScopeEmbeddings  # 阿里 DashScope 的嵌入模型
from langchain_community.chat_models.tongyi import ChatTongyi  # 阿里通义对话模型
from utils.config_handler import rag_conf  # RAG 相关配置


class BaseModelFactory(ABC):
    """
    抽象工厂基类：
    使用工厂模式统一模型创建接口。
    这样做的好处是：
    - 未来切换模型供应商（如从阿里切到百度）只需修改工厂类
    - 符合开闭原则：新增模型类型时只需添加新的工厂子类
    """

    @abstractmethod  # 抽象方法，强制子类必须实现，否则会报错
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        """
        子类必须实现的方法：返回一个模型实例。
        
        :return: 嵌入模型(Embeddings)或聊天模型(BaseChatModel)
        :return_type: Optional[Embeddings | BaseChatModel]
        """
        pass


class ChatModelFactory(BaseModelFactory):
    """
    聊天模型工厂：生产阿里通义 ChatTongyi 实例。
    用于对话生成、Agent 推理等需要生成自然语言文本的场景。
    """

    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        # rag_conf 从 rag.yml 读来，chat_model_name 配置具体模型版本
        # 如 "qwen-plus"、"qwen-max" 等
        return ChatTongyi(model=rag_conf["chat_model_name"])
# 修改后
# return ChatTongyi(model=rag_conf["chat_model_name"], api_key=rag_conf["api_key"])

class EmbeddingsFactory(BaseModelFactory):
    """
    嵌入模型工厂：生产阿里 DashScopeEmbeddings 实例。
    用于把文本转换为向量，供向量数据库存储和检索。
    注意：嵌入模型和对话模型是不同的模型，前者输出向量，后者输出文本。
    """

    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        # embedding_model_name 是向量化用的模型，和对话模型是不同的
        # 如 "text-embedding-v2"，专门用于文本向量化
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])
# 修改后
# return DashScopeEmbeddings(model=rag_conf["embedding_model_name"], api_key=rag_conf["api_key"])

# 模块级单例：import 时就创建好，全局共享，避免重复初始化
# 这是一种简单的单例实现方式，适合资源密集型对象
# 其他模块通过 from model.factory import chat_model, embed_model 直接使用
chat_model = ChatModelFactory().generator()
embed_model = EmbeddingsFactory().generator()