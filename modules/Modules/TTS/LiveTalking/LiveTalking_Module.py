import asyncio
import base64
import json
import os
import time
from typing import AsyncGenerator

from starlette.responses import StreamingResponse

from modules.Modules.BaseModule import BaseModule
from modules.utils.AudioChange import convert_audio_to_wav
from .LiveTalkingPost import PostChat, SetSessionConfig
from modules.utils.ConfigLoader import read_config

class LiveTalking_Module(BaseModule):
    def __init__(self):
        super().__init__()
        self.ENDSIGN = "ENDTALKING"

    def StartUp(self):
        if self.session is None:
            self.session,self.url = SetSessionConfig(self.pipeline.config["TTS"]["LiveTalking"]["url"],
                                                     None)
            self.RequestSender = PostChat(interrupt= self.pipeline.config["TTS"]["LiveTalking"]["interrupt"],
                                          type=self.pipeline.config["TTS"]["LiveTalking"]["type"],
                                          url=self.url,
                                          session=self.session)

    def register_module_routes(self):
        super().register_module_routes()
        @self.router.post("/awake")
        async def Awake(user: str, voice: str):
            """
            json格式:
            {
                "sessionid":0,
                "filepath":"",
            }
            """
            '''
            awakePath = self.Module_Config[voice]["awake"]
            self.logger.info(f"发送请求sessionid:{user},filepath:{awakePath},到 {self.url}/humanaudio")
            result = self.session.post(url = f"{self.url}/humanaudio",
                                       json = {
                                           "sessionid": int(user),
                                           "filepath": awakePath,
                                       })
            return result.json()
            '''
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
                wav_audio = convert_audio_to_wav(f.read(), set_sample_rate=24000)
                yield json.dumps({
                    "type": "audio/wav",
                    "chunk": base64.b64encode(wav_audio).decode("utf-8")
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
                self.session.head(self.url, timeout=5)
                return {
                    "status": "success",
                }
            except Exception as e:
                self.logger.error(f"心跳失败: {e}")
                return {
                    "status": "failed",
                    "error": str(e),
                }


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
        reffile = self.Module_Config[jsonInfo["TTS"]["voice"]][jsonInfo["TTS"]["emotion"]]["reffile"]
        reftext = self.Module_Config[jsonInfo["TTS"]["voice"]][jsonInfo["TTS"]["emotion"]]["reftext"]
        if input_data is None:
            # 预启动加载模型
            self.logger.warning(f"输入数据为None，无法处理")
            return b''

        # 处理当前输入的文本
        return self.process_single_text(streamly = streamly,
                                        interrupt = self.pipeline.config["TTS"]["LiveTalking"]["interrupt"],
                                        type = self.pipeline.config["TTS"]["LiveTalking"]["type"],
                                        user = user,
                                        sessionid = jsonInfo["TTS"]["sessionid"],
                                        voice=reffile,
                                        emotion= reftext,
                                        input_data = input_data,
                                        response_func = response_func,
                                        next_func = next_func)

    def process_single_text(self, streamly: bool, type:str, interrupt:bool, emotion:str, voice:str, user: str, sessionid:int, input_data: str, response_func, next_func) -> bytes:
        """处理单条文本"""
        start_time = time.time()
        self.logger.info(f"开始为用户 {user} 处理文本: {input_data}")
        try:
            # 发送文本到LiveTalking服务
            self.RequestSender = PostChat(interrupt=interrupt,type = type,url = self.url, session=self.session)

            chat_response = self.RequestSender.Post(text = input_data,
                                                    sessionid = sessionid,
                                                    voice= voice,
                                                    emotion= emotion)

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
