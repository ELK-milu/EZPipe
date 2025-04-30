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

from ..BaseModule import BaseModule
from .SovitsPost import PostChat, session
from modules.utils.logger import get_logger

class GPTSoVit_TTS_Module(BaseModule):
    def __init__(self):
        super().__init__()
        self.thread_pool = ThreadPoolExecutor(max_workers=4)  # 创建线程池
        self.min_batch_length = 8  # 短于此长度的文本会被合并处理
        self.max_batch_length = 100  # 最大批处理文本长度

    def StartUp(self):
        if self.session is None:
            self.session = session
        # 预热TTS引擎
        try:
            asyncio.run(self.HeartBeat(""))
            # 预加载常用短语
            common_phrases = ["你好", "谢谢", "我明白了", "请继续"]
            for phrase in common_phrases:
                self.preload_text(phrase)
            self.logger.info("[TTS] 引擎预热完成")
        except Exception as e:
            self.logger.error(f"[TTS] 引擎预热失败: {e}")

    def preload_text(self, text):
        """预加载常用文本到缓存"""
        try:
            if not text or len(text) < 2:
                return
            response = PostChat(streamly=False, user="system", text=text).GetResponse()
        except Exception as e:
            self.logger.error(f"[TTS] 预加载失败: {e}")

    def _get_cache_key(self, text):
        """生成缓存键"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    async def HeartBeat(self, user: str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                self.session.head("http://127.0.0.1:8090/", timeout=5)
                return {
                    "status": "success",
                }
            except Exception as e:
                self.logger.error(f"[TTS] 心跳失败: {e}")
                return {
                    "status": "failed",
                    "error": str(e),
                }
        else:
            self.session = session
            await self.HeartBeat(user)

    def should_batch_texts(self, texts):
        """判断文本是否应该合并处理"""
        # 按标点符号拆分句子
        if not texts or len(texts) <= 1:
            return False
            
        # 如果所有文本都很短，应该批处理
        return all(len(text) < self.min_batch_length for text in texts)
        
    def batch_process_texts(self, texts):
        """合并短文本进行处理"""
        batched_texts = []
        current_batch = ""
        
        for text in texts:
            # 如果添加当前文本会超出最大长度，先保存当前批次
            if len(current_batch) + len(text) > self.max_batch_length:
                if current_batch:
                    batched_texts.append(current_batch)
                current_batch = text
            else:
                if current_batch:
                    current_batch += "，" + text
                else:
                    current_batch = text
                    
        # 添加最后一个批次
        if current_batch:
            batched_texts.append(current_batch)
            
        return batched_texts

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
        if input_data is None:
            # 预启动加载模型
            self.logger.warning(f"[TTS] 输入数据为None，无法处理")
            return b''

        data = self.pipeline.use_request[user]

        tempStreamly = data["TTS"]["streamly"]

        # 处理当前输入的文本
        return self.process_single_text(tempStreamly, user, input_data, response_func, next_func)

    def process_single_text(self, streamly: bool, user: str, input_data: str, response_func, next_func) -> bytes:
        """处理单条文本"""
        max_retries = 3
        retry_count = 0
        start_time = time.time()

        self.logger.info(f"[TTS] 开始为用户 {user} 处理文本: {input_data[:20]}")
        
        if self.session is None:
            self.session = session

            
        while retry_count <= max_retries:
            try:
                # 发送文本到TTS服务
                chat_response = PostChat(streamly=False, user=user, text=input_data).GetResponse()
                
                if not chat_response.ok:
                    raise Exception(f"合成失败，状态码: {chat_response.status_code}")

                self.logger.info(f"[TTS] 响应状态码: {chat_response.status_code}")
                
                # 循环处理响应中的数据块
                for chunk in chat_response.iter_content(chunk_size=None):
                    if self.stop_events[user].is_set():
                        break

                    if not chunk:  # 跳过空块
                        self.logger.warning("[TTS] 收到空数据块")
                        continue
                        
                    # 检查是否应该停止处理
                    if user in self.stop_events and self.stop_events[user].is_set():
                        self.logger.info(f"[TTS] 用户 {user} 已请求停止处理")
                        break

                    # 处理数据块
                    chunk_size = len(chunk)
                    self.logger.info(f"[TTS] 发送数据块 给用户 {user} ({chunk_size} 字节)")
                    self.logger.info(f"[TTS] 用户 {user} 的文本: {input_data}转语音处理完毕")
                    
                    # 调用回调函数输出数据块
                    response_func(streamly, user, chunk)
                    
                    # 如果有下一个模块，则传递数据
                    if self.next_model:
                        next_func(streamly, user, chunk)
                
                # 记录完整响应时间
                elapsed = time.time() - start_time
                self.logger.info(f"[TTS] 完整响应耗时: {elapsed:.3f}秒")
                return b''  # 返回空字节作为完成标记
                
            except Exception as e:
                retry_count += 1
                error_msg = f"[TTS] 错误: {str(e)}"
                self.logger.error(error_msg)
                
                if retry_count <= max_retries:
                    self.logger.warning(f"[TTS] 处理失败，正在重试 ({retry_count}/{max_retries})")
                    # 短暂等待后重试
                    time.sleep(0.1)
                else:
                    # 达到最大重试次数，通知调用者出现错误
                    self.logger.error(f"[TTS] 达到最大重试次数 ({max_retries})，放弃处理")
                    response_func(streamly, user, f"ERROR: {str(e)}".encode())
                    next_func(streamly, user, self.ENDSIGN)
                    return b''  # 返回空字节作为完成标记

    def ProcessAudio(self, audio_data):
        try:
            # 直接处理音频数据，不进行额外的格式转换
            if isinstance(audio_data, bytes):
                audio_data = np.frombuffer(audio_data, dtype=np.int16)
            
            # 使用更高效的音频处理方式
            audio_data = audio_data.astype(np.float32) / 32768.0
            
            # 减少音频处理步骤
            if len(audio_data) > 0:
                # 直接返回处理后的音频数据
                return audio_data.tobytes()
            
            return None
            
        except Exception as e:
            self.logger.error(f"音频处理失败: {str(e)}")
            return None
