import json
import threading
from typing import Optional, Any

from fastapi import requests

from ..BaseModule import BaseModule
from .SovitsPost import PostChat

class GPTSoVit_TTS_Module(BaseModule):

    def HeartBeat(self,user:str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                self.session.head("http://127.0.0.1:8090/", timeout=10)
                return {
                    "status": "success",
                }
            except requests.exceptions.RequestException as e:
                print(f"Heartbeat failed: {e}")

    def HandleInput(self, request: Any) -> bytes:
        return request.Input

    """语音合成模块（输入类型：str，输出类型：bytes）"""
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
        print(f"[TTS] 开始为用户 {user} 处理文本: {input_data[:20]}...")
        chat_response = None
        #data = json.loads(input_data)
        #temp_streamly =   data["TTS"]["streamly"]
        try :
            # 发送文本到TTS服务
            chat_response = PostChat(streamly=False, user=user, text=input_data).GetResponse()
            print(f"[TTS] 响应状态码: {chat_response.status_code}")
            
            # 用于统计处理的数据块
            chunk_count = 0
            total_bytes = 0
            
            # 循环处理响应中的数据块
            for chunk in chat_response.iter_content(chunk_size=None):
                if self.stop_events[user].is_set():
                    break

                if not chunk:  # 跳过空块
                    print("[TTS] 收到空数据块")
                    continue
                    
                # 检查是否应该停止处理
                if user in self.stop_events and self.stop_events[user].is_set():
                    print(f"[TTS] 用户 {user} 已请求停止处理")
                    break
                    
                # 处理数据块
                chunk_size = len(chunk)
                total_bytes += chunk_size
                print(f"[TTS] 发送数据块 #{chunk_count} 给用户 {user} ({chunk_size} 字节)")
                
                # 调用回调函数输出数据块
                response_func(streamly, user, chunk)
                
                # 如果有下一个模块，则传递数据
                if self.next_model:
                    next_func(streamly, user, chunk)
                    
                chunk_count += 1
                
            # 输出统计信息
            print(f"[TTS] 共发送 {chunk_count} 个数据块，总计 {total_bytes} 字节")
            
            # 如果没有下一个模块，标记处理完成
            if not self.next_model:
                response_func(streamly, user, self.ENDSIGN)
                next_func(streamly, user, self.ENDSIGN)

            return b''  # 返回空字节作为完成标记
            
        except Exception as e:
            # 处理异常
            error_msg = f"[TTS] 错误: {str(e)}"
            print(error_msg)
            
            # 通知调用者出现错误
            response_func(streamly, user, f"ERROR: {str(e)}".encode())
            next_func(streamly, user, self.ENDSIGN)
            
            return b''  # 返回空字节作为完成标记
