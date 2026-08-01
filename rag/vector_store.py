from langchain_chroma import Chroma  # Chroma 向量数据库的 LangChain 封装
from langchain_core.documents import Document  # LangChain 的文档对象，包含文本内容和元数据
from utils.config_handler import chroma_conf  # Chroma 相关配置
from model.factory import embed_model  # 嵌入模型，用于文本转向量
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 递归字符文本分片器
from utils.path_tool import get_abs_path  # 相对路径转绝对路径
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex  # 文件处理工具
from utils.logger_handler import logger  # 全局日志器
import os  # 文件操作


class VectorStoreService:
    """
    向量库服务：
    1. 初始化 Chroma 向量数据库连接
    2. 加载知识文档、文本分片、存入向量库
    3. 提供检索器供 RAG 服务使用
    
    这是 RAG（检索增强生成）的核心基础设施。
    """

    def __init__(self):
        """
        初始化向量库服务。
        创建 Chroma 实例（向量数据库）和文本分片器。
        """
        # Chroma 是嵌入式向量数据库，数据直接存在本地 sqlite 文件里
        # 不需要独立的数据库服务，适合单机应用
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],       # 集合名（类似数据库的表名）
            embedding_function=embed_model,                        # 把文本转向量的嵌入模型
            persist_directory=chroma_conf["persist_directory"],    # 向量数据持久化目录
        )

        # 递归分片器：按段落/行/字符逐级尝试切分，尽量保持语义完整
        # 例如优先按段落切，如果段落太长再按行切，以此类推
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],        # 每段最大字符数
            chunk_overlap=chroma_conf["chunk_overlap"],   # 相邻段的重叠字符数，保证上下文连贯
            separators=chroma_conf["separators"],        # 优先尝试的分隔符
            length_function=len,                          # 计算文本长度的函数
        )

    def get_retriever(self):
        """
        获取向量检索器。
        k 表示一次返回 top-k 个最相关文档，k 越大召回越多但精度可能下降。
        """
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    @staticmethod
    def _check_md5_hex(md5_for_check: str) -> bool:
        """
        检查文件 MD5 是否已在记录文件中（即是否已处理过）。
        用于避免重复加载相同内容的文件。
        
        :param md5_for_check: 文件的 MD5 十六进制字符串
        :return: True 表示已处理过，False 表示未处理
        """
        md5_store_path = get_abs_path(chroma_conf["md5_hex_store"])
        # 如果记录文件不存在，说明是首次运行，创建空文件
        if not os.path.exists(md5_store_path):
            open(md5_store_path, "w", encoding="utf-8").close()
            return False

        # 逐行读取记录文件，检查是否包含目标 MD5
        with open(md5_store_path, "r", encoding="utf-8") as f:
            for line in f.readlines():
                if line.strip() == md5_for_check:
                    return True  # 已处理过，无需重复加载
        return False

    @staticmethod
    def _save_md5_hex(md5_for_check: str):
        """
        把处理过的文件 MD5 追加写入记录文件。
        下次启动时可以跳过这些文件。
        
        :param md5_for_check: 文件的 MD5 十六进制字符串
        """
        with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
            f.write(md5_for_check + "\n")

    @staticmethod
    def _get_file_documents(read_path: str) -> list[Document]:
        """
        根据文件后缀选择合适的 loader 读取为 Document 列表。
        支持 .txt 和 .pdf 两种格式。
        
        :param read_path: 文件的绝对路径
        :return: LangChain Document 对象列表
        """
        if read_path.endswith(".txt"):
            return txt_loader(read_path)   # 纯文本加载器
        if read_path.endswith(".pdf"):
            return pdf_loader(read_path)  # PDF 加载器
        return []  # 不支持的格式返回空列表

    def load_document(self):
        """
        从数据文件夹读取所有知识文件，切分后存入向量库。
        处理流程：
        1. 列出所有允许类型的文件
        2. 计算 MD5 判断是否需要加载
        3. 读取文件内容
        4. 文本分片
        5. 写入向量库
        6. 记录 MD5
        """
        # 1. 列出数据目录下所有允许类型的文件
        allowed_files_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            # 2. 计算文件 MD5，用于判断是否需要重新加载
            # 文件内容有变化才需要重新加载，否则跳过
            md5_hex = get_file_md5_hex(path)
            if not md5_hex:
                logger.warning(f"[加载知识库]{path}MD5计算失败，跳过")
                continue

            # 3. MD5 去重：已存在知识库则跳过
            if self._check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                continue

            try:
                # 4. 读取文件内容为 LangChain Document 对象
                documents: list[Document] = self._get_file_documents(path)
                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                # 5. 文本分片：把长文档切成小块，便于向量化和检索
                split_document: list[Document] = self.spliter.split_documents(documents)
                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue

                # 6. 写入向量库 + 记录 MD5
                self.vector_store.add_documents(split_document)
                self._save_md5_hex(md5_hex)
                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # 加载失败不阻塞其他文件的加载
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)


# 懒加载单例模式：
# 不在模块加载时立即创建 VectorStoreService，而是延迟到第一次调用 get_vector_store() 时
# 这样做的好处是如果程序没有用到向量库，可以节省启动时间
_vector_store_instance: VectorStoreService | None = None


def get_vector_store() -> VectorStoreService:
    """
    获取 VectorStoreService 单例。
    整个进程共享一个 Chroma 连接，避免重复创建。
    """
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreService()
    return _vector_store_instance


if __name__ == '__main__':
    # 本地测试入口：加载知识库并测试检索
    vs = get_vector_store()
    vs.load_document()
    retriever = vs.get_retriever()
    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-" * 20)