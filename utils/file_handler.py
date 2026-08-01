import os  # 文件操作
import hashlib  # 哈希算法库，用于计算 MD5
from utils.logger_handler import logger  # 全局日志器
from langchain_core.documents import Document  # LangChain 的文档对象
from langchain_community.document_loaders import PyPDFLoader, TextLoader  # 官方提供的 PDF / TXT 加载器


def get_file_md5_hex(filepath: str):
    """
    计算文件 MD5 值（十六进制字符串），用于文件去重。
    MD5 可以唯一标识文件内容，相同内容的文件会有相同的 MD5 值。
    
    :param filepath: 文件的绝对路径
    :return: MD5 十六进制字符串，失败时返回 None
    """
    #
    #检查路径是否存在，非0为1
    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在")
        return
    #判断存在的路径是否是文件
    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]路径{filepath}不是文件")
        return

    # 创建 MD5 哈希对象
    md5_obj = hashlib.md5()

    # 采用分片读取策略，避免大文件一次性读入导致内存爆掉
    chunk_size = 4096  # 4KB 分片
    try:
        with open(filepath, "rb") as f:  # 必须以二进制模式读取
            # 海象运算符（:=）写法：边读边赋值，循环直到读完
            # 这是 Python 3.8+ 的语法，让代码更简洁
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)  # 把分片数据加入哈希计算
            md5_hex = md5_obj.hexdigest()  # 拿到十六进制字符串，如 "d41d8cd98f00b204e9800998ecf8427e"
            return md5_hex
    except Exception as e:
        logger.error(f"计算文件{filepath}md5失败，{str(e)}")
        return None


def listdir_with_allowed_type(path: str, allowed_types: tuple[str]):
    """
    列出文件夹内所有指定后缀的文件。
    
    :param path: 文件夹路径
    :param allowed_types: 允许的文件后缀元组，如 ('.txt', '.pdf')
    :return: 文件绝对路径的元组
    """
    files = []

    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]{path}不是文件夹")
        return ()

    # 遍历文件夹中的所有文件
    for f in os.listdir(path):
        # endswith 支持多后缀参数，只要匹配其中一个就返回 True
        if f.endswith(allowed_types):
            files.append(os.path.join(path, f))  # 拼接完整路径

    return tuple(files)


def pdf_loader(filepath: str, passwd=None) -> list[Document]:
    """
    把 PDF 文件加载成 LangChain Document 列表。
    Document 包含文本内容和元数据（如页码等）。
    
    :param filepath: PDF 文件路径
    :param passwd: PDF 密码（如果是加密的 PDF）
    :return: Document 对象列表
    """
    return PyPDFLoader(filepath, passwd).load()


def txt_loader(filepath: str) -> list[Document]:
    """
    把 TXT 文件加载成 LangChain Document 列表。
    
    :param filepath: TXT 文件路径
    :return: Document 对象列表
    """
    return TextLoader(filepath, encoding="utf-8").load()