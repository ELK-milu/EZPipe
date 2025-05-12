import asyncio
import json
import threading
import logging
import time
import re
from typing import Optional, Any, Dict, List
from concurrent.futures import ThreadPoolExecutor
import hashlib

import requests
import numpy as np

from modules.Modules.BaseModule import BaseModule
from .LiveTalkingPost import PostChat, session,url
from modules.utils.logger import get_logger

class LiveTalking_Module(BaseModule):
    def __init__(self):
        super().__init__()
        self.ENDSIGN = "ENDTALKING"
        self.cache = {}  # 简单的缓存系统
        self.cache_max_size = 100  # 最大缓存条目数
        self.thread_pool = ThreadPoolExecutor(max_workers=4)  # 创建线程池
        self.min_batch_length = 8  # 短于此长度的文本会被合并处理
        self.max_batch_length = 100  # 最大批处理文本长度

    def StartUp(self):
        if self.session is None:
            self.session = session
        # 预热TTS引擎
        try:
            asyncio.run(self.HeartBeat(""))
        except Exception as e:
            self.logger.error(f"引擎预热失败: {e}")

    async def HeartBeat(self, user: str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                self.session.head(url, timeout=5)
                return {
                    "status": "success",
                }
            except Exception as e:
                self.logger.error(f"心跳失败: {e}")
                return {
                    "status": "failed",
                    "error": str(e),
                }
        else:
            self.session = session
            await self.HeartBeat(user)

    """语音合成模块（输入类型：str，输出类型：bytes）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: str, response_func, next_func) -> bytes:
        """
        处理文本到语音的转换任务
        Args:
            streamly: 是否流式输出
            user: 用户标识
            input_data: 输入文本
            response_func: 输出回调函数
            next_func: 下一个模块的回调函数
        Returns:
            bytes: 音频数据
        """
        # 检查input_data是否为None
        jsonInfo = self.pipeline.use_request[user]
        if input_data is None:
            # 预启动加载模型
            self.logger.warning(f"输入数据为None，无法处理")
            return b''

        # 处理当前输入的文本
        return self.process_single_text(streamly = streamly,
                                        interrupt = jsonInfo["LiveTalking"]["interrupt"],
                                        type = jsonInfo["LiveTalking"]["type"],
                                        user = user,
                                        sessionid = jsonInfo["LiveTalking"]["sessionid"],
                                        reftext = jsonInfo["LiveTalking"]["reftext"],
                                        reffile = jsonInfo["LiveTalking"]["reffile"],
                                        input_data = input_data,
                                        response_func = response_func,
                                        next_func = next_func)

    def process_single_text(self, streamly: bool,type:str,interrupt:bool,reftext:str,reffile:str,user: str,sessionid:int, input_data: str, response_func, next_func) -> bytes:
        """处理单条文本"""
        start_time = time.time()
        self.logger.info(f"开始为用户 {user} 处理文本: {input_data}")

        if self.session is None:
            self.session = session
        try:
            # 发送文本到LiveTalking服务
            chat_response = PostChat(interrupt=interrupt,type = type, sessionid=sessionid, text=input_data,reftext=reftext,reffile=reffile).GetResponse()

            if not chat_response.ok:
                raise Exception(f"合成失败，状态码: {chat_response.status_code}")

            self.logger.info(f"响应状态码: {chat_response.status_code}")
        except Exception as e:
            error_msg = f"错误: {str(e)}"
            self.logger.error(error_msg)
            # 达到最大重试次数，通知调用者出现错误
            response_func(streamly, user, f"ERROR: {str(e)}".encode())
        finally:
            response_func(streamly, user, self.ENDSIGN)
            next_func(streamly, user, self.ENDSIGN)
            return b''
