import json
import threading
from typing import Optional, Any

from fastapi import requests

from ..BaseModule import BaseModule
from .SovitsPost import PostChat,session
from utils.logger import get_logger, track_time, track_module_time

# 创建TTS模块日志记录器
logger = get_logger("GPTSoVit_TTS_Module")

class GPTSoVit_TTS_Module(BaseModule):

    def StartUp(self):
        if self.session is None:
            self.session = session
    def HeartBeat(self,user:str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                self.session.head("http://127.0.0.1:8090/", timeout=10)
                return {
                    "status": "success",
                }
            except requests.exceptions.RequestException as e:
                logger.error(f"Heartbeat failed: {e}")
        else:
            self.session = session
            self.HeartBeat(user)

    def HandleInput(self, request: Any) -> bytes:
        return request.Input

    """语音合成模块（输入类型：str，输出类型：bytes）"""
    @track_time(logger)
    def Thread_Task(self, streamly: bool, user: str, input_data: str, response_func,next_func) -> bytes:
        """
        处理文本到语音的转换任务
        Args:
            streamly: 是否流式输出
            user: 用户标识
            input_data: 输入文本
            response_func: 输出回调函数
        Returns:
            bytes: 音频数据
        """
        # 检查input_data是否为None
        if input_data is None:
            logger.warning(f"[TTS] 输入数据为None，无法处理")
            response_func(streamly, user, f"ERROR: 输入数据为None".encode())
            next_func(streamly, user, self.ENDSIGN)
            return b''
            
        logger.info(f"[TTS] 开始为用户 {user} 处理文本: {input_data[:20]}...")
        chat_response = None
        #data = json.loads(input_data)
        #temp_streamly =   data["TTS"]["streamly"]
        if self.session is None:
            self.session = session
        try :
            # 发送文本到TTS服务
            chat_response = PostChat(streamly=False, user=user, text=input_data).GetResponse()
            logger.info(f"[TTS] 响应状态码: {chat_response.status_code}")
            
            # 用于统计处理的数据块
            chunk_count = 0
            total_bytes = 0
            
            # 循环处理响应中的数据块
            for chunk in chat_response.iter_content(chunk_size=None):
                if self.stop_events[user].is_set():
                    break

                if not chunk:  # 跳过空块
                    logger.warning("[TTS] 收到空数据块")
                    continue
                    
                # 检查是否应该停止处理
                if user in self.stop_events and self.stop_events[user].is_set():
                    logger.info(f"[TTS] 用户 {user} 已请求停止处理")
                    break
                    
                # 处理数据块
                chunk_size = len(chunk)
                total_bytes += chunk_size
                logger.debug(f"[TTS] 发送数据块 #{chunk_count} 给用户 {user} ({chunk_size} 字节)")
                
                # 调用回调函数输出数据块
                response_func(streamly, user, chunk)
                
                # 如果有下一个模块，则传递数据
                if self.next_model:
                    next_func(streamly, user, chunk)
                    
                chunk_count += 1
                
            # 输出统计信息
            logger.info(f"[TTS] 共发送 {chunk_count} 个数据块，总计 {total_bytes} 字节")
            
            # 如果没有下一个模块，标记处理完成
            if not self.next_model:
                response_func(streamly, user, self.ENDSIGN)
                next_func(streamly, user, self.ENDSIGN)

            return b''  # 返回空字节作为完成标记
            
        except Exception as e:
            # 处理异常
            error_msg = f"[TTS] 错误: {str(e)}"
            logger.error(error_msg)
            
            # 通知调用者出现错误
            response_func(streamly, user, f"ERROR: {str(e)}".encode())
            next_func(streamly, user, self.ENDSIGN)
            
            return b''  # 返回空字节作为完成标记
