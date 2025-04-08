import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

# 创建日志目录
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

def setup_root_logger():
    """设置根logger，只配置一次"""
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        root_logger.setLevel(logging.INFO)

def get_logger(name: str) -> logging.Logger:
    """
    获取一个logger实例，如果已经存在则返回现有的，否则创建新的
    """
    logger = logging.getLogger(name)
    # 防止日志传播到根logger，避免重复打印
    logger.propagate = False
    
    # 如果logger已经有处理器，直接返回
    if logger.handlers:
        return logger
        
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加处理器到logger
    logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)
    
    return logger

# 初始化根logger
setup_root_logger()

# 配置根日志记录器
def setup_logger(name="LCBot", level=logging.INFO):
    """
    设置并返回一个配置好的日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        
    Returns:
        logging.Logger: 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器 - 按模块分类
    module_name = name.split('.')[-1]
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{module_name}.log"),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 防止日志传播到根logger，避免重复打印
    logger.propagate = False
    
    return logger

# 获取模块日志记录器
def get_logger(module_name):
    """
    获取指定模块的日志记录器
    
    Args:
        module_name: 模块名称
        
    Returns:
        logging.Logger: 模块的日志记录器
    """
    return setup_logger(f"LCBot.{module_name}")

# 创建默认日志记录器
default_logger = setup_logger("LCBot") 