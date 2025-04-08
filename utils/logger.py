import logging
import time
import functools
import os
import sys
from logging.handlers import RotatingFileHandler

# 创建日志目录
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

# 配置日志格式
log_format = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建日志处理器
file_handler = RotatingFileHandler(
    os.path.join(log_dir, "pipeline.log"),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'  # 使用UTF-8编码
)
file_handler.setFormatter(log_format)

# 创建控制台处理器，使用UTF-8编码
console_handler = logging.StreamHandler(sys.stdout)  # 明确指定使用stdout
console_handler.setFormatter(log_format)

# 设置根日志记录器，防止日志传播
logging.getLogger().setLevel(logging.WARNING)

# 创建日志记录器
def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加处理器
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    # 防止日志传播到根日志记录器
    logger.propagate = False
    
    return logger

# 性能跟踪装饰器
def track_time(logger=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 如果没有提供logger，使用函数所在模块的logger
            if logger is None:
                module_logger = get_logger(func.__module__)
                module_logger.info(f"函数 {func.__name__} 执行耗时: {elapsed_time:.2f}ms")
            else:
                logger.info(f"函数 {func.__name__} 执行耗时: {elapsed_time:.2f}ms")
                
            return result
        return wrapper
    return decorator

# 模块性能跟踪装饰器
def track_module_time(module_name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(module_name)
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            elapsed_time = (end_time - start_time) * 1000  # 转换为毫秒
            logger.info(f"模块 {module_name} 执行耗时: {elapsed_time:.2f}ms")
            return result
        return wrapper
    return decorator 