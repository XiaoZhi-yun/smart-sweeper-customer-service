"""
路径工具模块：
为整个工程提供统一的绝对路径工具，避免硬编码相对路径带来的路径问题。

为什么需要这个模块？
- 当项目被不同的方式启动（如命令行、IDE、服务等），工作目录可能不同
- 使用相对路径（如 "config/xxx.yml"）可能找不到文件
- 通过 __file__ 推算项目根目录，可以确保无论从哪里启动都能正确定位文件
"""
import os  # 操作系统接口


def get_project_root() -> str:
    """
    获取工程根目录（即 AgentProject 文件夹）。
    
    实现原理：
    传入当前路径，返回当前路径的根目录
    1. __file__ 是当前文件的路径（可能是相对路径）
    2. abspath(__file__) 转为绝对路径
    3. dirname 取所在目录（即 utils 文件夹）
    4. 再 dirname 取上一级（即 AgentProject 根目录）
    
    :return: 项目根目录的绝对路径
    """
    current_file = os.path.abspath(__file__)      # 当前文件的绝对路径，如 D:\Project\AgentProject\utils\path_tool.py
    current_dir = os.path.dirname(current_file)   # 当前文件所在文件夹，如 D:\Project\AgentProject\utils
    project_root = os.path.dirname(current_dir)   # 再往上一级就是工程根目录，如 D:\Project\AgentProject
    return project_root


def get_abs_path(relative_path: str) -> str:
    """
    把相对路径拼接到工程根目录上，得到绝对路径。
    
    使用示例：
    -传入相对路径，最终返回绝对路径
    - get_abs_path("config/rag.yml") -> "D:\Project\AgentProject\config\rag.yml"
    - get_abs_path("data/knowledge.txt") -> "D:\Project\AgentProject\data\knowledge.txt"
    
    :param relative_path: 相对路径，如 "config/rag.yml"
    :return: 拼接后的绝对路径
    """
    project_root = get_project_root()
    return os.path.join(project_root, relative_path)


if __name__ == '__main__':
    # 本地调试入口：运行此文件可测试路径功能
    print(get_abs_path("config/config.txt"))