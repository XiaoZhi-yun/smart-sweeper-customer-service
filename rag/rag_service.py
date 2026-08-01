from langchain_core.documents import Document  # LangChain 的文档对象
from langchain_core.output_parsers import StrOutputParser  # 字符串输出解析器
from langchain_core.runnables import RunnableLambda  # 把普通函数包装成 Runnable
from rag.vector_store import get_vector_store  # 获取向量库单例
from utils.prompt_loader import load_rag_prompts  # 加载 RAG 专用提示词
from langchain_core.prompts import PromptTemplate  # 提示词模板
from model.factory import chat_model  # 聊天模型
from utils.logger_handler import logger  # 全局日志器


def log_prompt(prompt):
    """
    调试用函数：把拼装好的完整 prompt 以 DEBUG 级别输出。
    方便开发者看到最终送给模型的完整提示词是什么样的。
    """
    logger.debug(f"[RAG prompt]\n{prompt.to_string()}")
    return prompt  # 原样返回，不修改 prompt


class RagSummarizeService:
    """
    RAG（Retrieval-Augmented Generation）总结服务：
    检索增强生成的核心实现。
    
    工作流程：
    1. 用户提问
    2. 把问题发到向量库检索相关文档
    3. 把检索到的文档拼装成上下文
    4. 把用户问题和上下文一起交给大模型
    5. 模型结合参考资料生成答案
    6. 返回最终答案
    
    这种方式的好处是：
    - 模型能基于私有知识库回答，而不是只靠训练数据
    - 可以引用最新的、私有的、专业的知识
    """

    def __init__(self):
        """
        初始化 RAG 服务。
        组装检索器、提示词模板、模型和处理链。
        """
        self.vector_store = get_vector_store()          # 复用全局单例，避免重复创建
        self.retriever = self.vector_store.get_retriever()  # 检索器：输入文本，输出相关文档
        self.prompt_text = load_rag_prompts()             # 加载 RAG 专用提示词
        # from_template 把字符串模板编译成 PromptTemplate 对象
        # 模板中的 {input} 和 {context} 是占位符，调用时会被实际值替换
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model                           # 对话模型
        self.chain = self._init_chain()                   # 组装 LangChain 处理链

    def _init_chain(self):
        """
        组装 LangChain LCEL（LangChain Expression Language）链。
        
        LCEL 是 LangChain 的核心组合方式，使用 | 管道符组合：
        每个组件的输出是下一个组件的输入。
        
        处理链流程：
        1. prompt_template: 把用户问题和上下文填入模板，生成完整提示词
        2. log_prompt: 打印提示词用于调试
        3. model: 调用大模型生成回答
        4. StrOutputParser: 把 AIMessage 对象解析为纯字符串
        """
        # RunnableLambda 把普通函数包装成 Runnable 对象，使其能参与链式组合
        chain = self.prompt_template | RunnableLambda(log_prompt) | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str) -> list[Document]:
        """
        根据 query 从向量库检索 top-k 个相关文档。
        
        :param query: 用户的问题
        :return: 相关文档列表，每个文档包含 page_content（内容）和 metadata（元数据）
        """
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        """
        RAG 主流程：检索 -> 拼装上下文 -> 调用链生成回答。
        
        :param query: 用户的问题
        :return: 模型生成的回答文本
        """
        # Step 1: 向量检索 - 根据用户问题从知识库中找到相关文档
        context_docs = self.retriever_docs(query)

        # Step 2: 把检索到的文档拼成一段长文本作为上下文
        # 格式化为带编号的参考资料，方便模型区分和引用
        context = ""
        for i, doc in enumerate(context_docs, 1):  # 从1开始编号
            context += f"【参考资料{i}】: 内容：{doc.page_content} | 元数据：{doc.metadata}\n"

        # Step 3: 调用链，input 是用户问题，context 是拼好的参考资料
        # 模板中的 {input} 会被替换为 query，{context} 会被替换为上面拼好的字符串
        return self.chain.invoke({
            "input": query,
            "context": context,
        })


if __name__ == '__main__':
    # 本地测试入口
    rag = RagSummarizeService()
    print(rag.rag_summarize("小户型适合哪些扫地机器人"))