import base64
import json
import time
import re
from typing import Optional, Any, Dict, List, AsyncGenerator

import requests
from starlette.responses import StreamingResponse

from modules.Modules.BaseModule import BaseModule
from .DouBaoPost import PostChat, SetSessionConfig

class Doubao_TTS_Module(BaseModule):
    def __init__(self):
        super().__init__()
        self.ENDSIGN = "ENDDouBaoTTS"

    def StartUp(self):
        if self.session is None:
            self.session,self.url = SetSessionConfig(token = self.pipeline.config["TTS"]["Doubao"]["token"],
                                                     host = self.pipeline.config["TTS"]["Doubao"]["host"])
            self.RequestSender = PostChat(appid= self.pipeline.config["TTS"]["Doubao"]["appid"],
                                          cluster=self.pipeline.config["TTS"]["Doubao"]["cluster"],
                                          session=self.session)

    def register_module_routes(self):
        super().register_module_routes()
        @self.router.post("/awake")
        async def Awake(user: str, voice: str):
            """
            json格式:
            {
                "user":0,
                "voice":"",
            }
            """
            return StreamingResponse(
                content=self.generate_stream(user,voice),
                media_type="text/event-stream",
            )

    async def generate_stream(self,user,voice) -> AsyncGenerator[str, None]:
        awakeText = self.Module_Config[voice]["awake_text"]
        # 第一条文本数据
        # 服务端替客户端处理成Json再返回
        final_json = json.dumps({
            "think": "",
            "response": awakeText,
            "conversation_id": "",
            "message_id": "",
            "Is_End": True
        })
        yield json.dumps({
            "type": "text",
            "chunk": final_json
        })+ "\n"

        # 第二条音频数据
        print(self.GetAbsPath() + self.Module_Config[voice]["awake_audio"])
        awakeAudioPath = self.GetAbsPath() + self.Module_Config[voice]["awake_audio"]
        try:
            with open(awakeAudioPath, 'rb') as f:
                yield json.dumps({
                    "type": "audio/wav",
                    "chunk": base64.b64encode(f.read()).decode("utf-8")
                }) + "\n"
        except Exception as e:
            yield json.dumps({
                "type": "error",
                "chunk": f"文件加载失败: {str(e)}"
            }) + "\n"
        finally:
            # 关闭文件
            f.close()

    async def HeartBeat(self, user: str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                request = self.session.head(f"{self.url}", timeout=10)
                return request.status_code
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Heartbeat failed: {e}")

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
        voice_type = self.Module_Config[data["TTS"]["voice"]]["voice_type"]
        emotin = self.Module_Config[data["TTS"]["voice"]]["emotions"][data["TTS"]["emotion"]]
        # 处理当前输入的文本
        return self.process_single_text(tempStreamly, voice_type,emotin, user, input_data, response_func, next_func)

    def process_single_text(self, streamly: bool,voice_type:str,emotion:str, user: str, input_data: str, response_func, next_func) -> bytes:
        """处理单条文本"""
        max_retries = 3
        retry_count = 0
        start_time = time.time()

        self.logger.info(f"[TTS] 开始为用户 {user} 处理文本: {input_data[:20]}")

        while retry_count <= max_retries:
            try:
                # 发送文本到TTS服务
                chat_response = self.RequestSender.Post(user = user,
                                                        text= input_data,
                                                        voice_type = voice_type,
                                                        emotion = emotion,)

                if not chat_response.ok:
                    raise Exception(f"合成失败，状态码: {chat_response.status_code}")

                self.logger.info(f"[TTS] 响应状态码: {chat_response.status_code}")

                # 循环处理响应中的数据块

                if self.stop_events[user].is_set():
                    break

                response_json = chat_response.json()
                chunk = base64.b64decode(response_json['data'])
                if not chunk:  # 跳过空块
                    self.logger.warning("[TTS] 收到空数据块")
                    continue

                # 检查是否应该停止处理
                if user in self.stop_events and self.stop_events[user].is_set():
                    self.logger.info(f"[TTS] 用户 {user} 已请求停止处理")
                    break

                return self.ParseChunk(chunk, input_data, next_func, response_func, start_time, streamly, user)

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

    def ParseChunk(self, chunk, input_data, next_func, response_func, start_time, streamly, user):
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

