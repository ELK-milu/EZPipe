import asyncio
import os
import time

from modules.Modules.BaseModule import BaseModule
from .LiveTalkingPost import PostChat, SetSessionConfig
from modules.utils.ConfigLoader import read_config

class LiveTalking_Module(BaseModule):
    def __init__(self):
        super().__init__()
        self.ENDSIGN = "ENDTALKING"
        self.Module_Config =read_config(os.path.dirname(os.path.abspath(__file__)) +  "/Config.yaml")

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
        @self.router.get("/awake")
        async def Awake(sessionid: int, voice: str):
            """
            json格式:
            {
                "sessionid":0,
                "filepath":"",
            }
            """
            result = self.session.post(url = f"{self.url}/humanaudio",
                                       json = {
                                           "sessionid": sessionid,
                                           "filepath": self.Module_Config[voice]["awake"],
                                       })
            return result.json()



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
                                        interrupt = jsonInfo["TTS"]["interrupt"],
                                        type = self.pipeline.config["TTS"]["LiveTalking"]["type"],
                                        user = user,
                                        sessionid = jsonInfo["TTS"]["sessionid"],
                                        reftext = reftext,
                                        reffile = reffile,
                                        input_data = input_data,
                                        response_func = response_func,
                                        next_func = next_func)

    def process_single_text(self, streamly: bool,type:str,interrupt:bool,reftext:str,reffile:str,user: str,sessionid:int, input_data: str, response_func, next_func) -> bytes:
        """处理单条文本"""
        start_time = time.time()
        self.logger.info(f"开始为用户 {user} 处理文本: {input_data}")
        try:
            # 发送文本到LiveTalking服务
            self.RequestSender = PostChat(interrupt=interrupt,type = type,url = self.url, session=self.session)

            chat_response = self.RequestSender.Post(text = input_data,
                                                    sessionid = sessionid,
                                                   reffile = reffile,
                                                   reftext = reftext)

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
