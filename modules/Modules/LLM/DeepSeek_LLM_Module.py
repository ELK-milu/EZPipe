import json
import re
import threading
import time
import logging
from typing import Optional, Any, Dict

import requests

from ..BaseModule import BaseModule
from .DeepSeekPost import PostChat,session

# 配置logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 防止重复添加处理器
if not logger.handlers:
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # 添加处理器到logger
    logger.addHandler(console_handler)

class DeepSeek_LLM_Module(BaseModule):
// ... existing code ... 