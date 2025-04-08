import asyncio
import json
import threading
import logging
import time
from typing import Optional, Any

from fastapi import requests
import numpy as np

from ..BaseModule import BaseModule
from .SovitsPost import PostChat,session
from modules.utils.logger import get_logger

# 获取logger实例
logger = get_logger(__name__)

class GPTSoVit_TTS_Module(BaseModule):

    def StartUp(self):
        if self.session is None:
            self.session = session
        asyncio.run(self.HeartBeat(""))
    async def HeartBeat(self,user:str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                self.session.head("http://127.0.0.1:8090/", timeout=10)
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

    def HandleInput(self, request: Any) -> bytes:
        return request.Input

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
            PostChat(streamly=False, user=user, text=input_data)
            self.logger.warning(f"[TTS] 输入数据为None，无法处理")
            return b''

        max_retries = 3
        retry_count = 0

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
                
                # 用于统计处理的数据块
                chunk_count = 0
                total_bytes = 0
                
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
                    total_bytes += chunk_size
                    self.logger.info(f"[TTS] 发送数据块 #{chunk_count} 给用户 {user} ({chunk_size} 字节)")
                    self.logger.info(f"[TTS] 用户 {user} 的文本: {input_data}转语音处理完毕")
                    # 调用回调函数输出数据块
                    response_func(streamly, user, chunk)
                    
                    # 如果有下一个模块，则传递数据
                    if self.next_model:
                        next_func(streamly, user, chunk)
                        
                    chunk_count += 1
                    
                # 输出统计信息
                self.logger.info(f"[TTS] 共发送 {chunk_count} 个数据块，总计 {total_bytes} 字节")

                return b''  # 返回空字节作为完成标记
                
            except Exception as e:
                retry_count += 1
                error_msg = f"[TTS] 错误: {str(e)}"
                self.logger.error(error_msg)
                
                if retry_count <= max_retries:
                    self.logger.warning(f"[TTS] 处理失败，正在重试 ({retry_count}/{max_retries})")
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
