import asyncio
import json
import re
import threading
import time
import logging
from typing import Optional, Any, Dict

import requests

from modules.Modules.BaseModule import BaseModule
from .DifyPost import PostChat,SetSessionConfig
from modules.utils.logger import get_logger


class Dify_LLM_Module(BaseModule):
    class Answer_Chunk:
        def __init__(self, text, user, streamly):
            self.text = text
            self.user = user
            self.streamly = streamly
            self.in_think_block = False
            self.think_string = ""
            self.response_string = ""
            self.full_content = ""
            self.Is_End = False

            self.message_id = ""
            self.conversation_id = ""
            self.final_json= ""
            self.ENDSIGN = "LLMEND"
            self.startTime = time.time()

            self.tempResponse = ""
            self.sentences = []
            self.IsFirst = True
            self.WaitCount = 1  # 减少等待的句子数量，从3改为1

            self.StartReceive = False

        def GetTempMsg(self):
            # 使用正向预查分割保留标点符号
            split_pattern = r'(?<=[，,!?。！？])'
            fragments = re.split(split_pattern, self.tempResponse)

            # 收集完整句子和未完成部分
            complete_sentences = []
            pending_fragment = ''

            for frag in fragments:
                if re.search(r'[，,!?。！？]$', frag):
                    complete_sentences.append(frag)
                    # 一旦有完整句子就返回，不再等待更多句子
                    if len(complete_sentences) >= self.WaitCount:
                        self.sentences = complete_sentences[:self.WaitCount]
                        self.tempResponse = ''.join(fragments[len(complete_sentences):])
                        return self.sentences
                else:
                    pending_fragment = frag
                    break

            # 如果没有完整句子，继续累积
            self.tempResponse = self.tempResponse
            self.sentences = []
            return self.sentences

        # 判断是否准备好返回
        def ReadyToResponse(self) -> bool:
            if(self.GetTempMsg() == []):
                return False
            else:
                return True

        def PrintSentences(self):
            # 打印完整句子
            for sentence in self.sentences:
                self.logger.info(f"句子: {sentence}")

        def GetThinking(self) -> str:
            return self.think_string

        def GetResponse(self) -> str:
            return self.response_string

        def AppendThinking(self, content):
            self.think_string += content

        def AppendResponse(self, content):
            self.tempResponse += content
            self.response_string += content

    async def HeartBeat(self,user:str):
        if self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                request = self.session.head(f"{self.url}/conversations", timeout=10)
                return request.status_code
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Heartbeat failed: {e}")

    def register_module_routes(self):
        self.logger.info(f"[Dify] 注册模块路由: {self.url}")
        @self.router.get("/messages")
        async def get_conversations(user:str, conversation_id: str):
            """获取历史会话"""
            # 调用Dify API获取数据（示例实现）
            result = self.session.get(url = f"{self.url}/messages?user={user}&conversation_id={conversation_id}")
            return result.json()
        @self.router.get("/conversations")
        async def get_conversations(user:str, last_id: str = None,limit: int = 20):
            """获取用户会话列表"""
            result = self.session.get(url = f"{self.url}/conversations?user={user}&last_id={last_id}&limit={limit}")
            # 调用Dify API获取数据（示例实现）
            return result.json()

        @self.router.delete("/conversations/delete")
        async def delete_conversation(request: Dict[str, Any]):
            """删除指定会话"""
            user = request.get("user", None)
            conversation_id = request.get("conversation_id", None)
            payload = {
                "user": user
            }
            result = self.session.delete(url = f"{self.url}/conversations/{conversation_id}",json = payload)
                # 调用Dify API删除会话
            return result.json()

        @self.router.post("/conversations/rename")
        async def rename_conversation(request: Dict[str, Any]):
            """会话重命名"""
            name = request.get("name", None)
            user = request.get("user", None)
            conversation_id = request.get("conversation_id", None)
            payload = {
                "name": name,
                "auto_generate": False,
                "user": user
            }
            """会话重命名"""
            result = self.session.post(url=f"{self.url}/conversations/{conversation_id}/name", json=payload)
            # 调用Dify API更新会话名称
            return result.json()

        @self.router.get("/messages/suggested")
        async def rename_conversation(user:str,conversation_id: str):
            """会话重命名"""
            result = self.session.get(url=f"{self.url}/messages/{conversation_id}/suggested?user={user}")
            # 调用Dify API更新会话名称
            return result.json()

    def StartUp(self):
        if self.session is None:
            self.session,self.url = SetSessionConfig(seturl=self.pipeline.config["LLM"]["Dify"]["url"],headerkey=self.pipeline.config["LLM"]["Dify"]["headerkey"])
            self.RequestSender =  PostChat(streamly=True,session = self.session)


    """LLM对话模块（输入类型：str，输出类型：str）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: str, response_func,next_func) -> str:
        self.logger.info("Thread_Task user:" + user)
        data = self.pipeline.use_request[user]
        self.logger.info("LLM:" + str(data["LLM"]["streamly"]))
        temp_streamly : bool = data["LLM"]["streamly"]
        self.answer_chunk = self.Answer_Chunk(text=input_data, user=user, streamly=temp_streamly)
        first_sentence_sent = False
        """
        处理LLM模型对话的服务
        Args:
            streamly: 是否流式输出
            user: 用户标识
            input_data: 输入文本
            invoke_func: 输出回调函数
        Returns:
            str: 字符串
        """
        self.logger.info(f"[Dify] 开始为用户 {user} 处理文本: {input_data[:20]}...")
        chat_response = None
        try:
            self.logger.info(f"[Dify] 开始请求对话: {input_data},对话ID: {data['conversation_id']}")
            chat_response = self.RequestSender.Post(text=input_data, conversation_id=data["conversation_id"], user=user)
            self.logger.info(f"[Dify] 响应状态码: {chat_response.status_code}")
            # 用于统计处理的数据块
            chunk_count = 0
            # 循环处理响应中的数据块
            for chunk in chat_response.iter_content(chunk_size=None):
                decoded = chunk.decode('utf-8')
                self.extract_think_response(self.answer_chunk, decoded, True)
                self.logger.info(f"[Dify] think:{self.answer_chunk.GetThinking()}\nResponse:{self.answer_chunk.GetResponse()}")

                if self.stop_events[user].is_set():
                    break

                if not chunk:  # 跳过空块
                    self.logger.warning("[Dify] 收到空数据块")
                    continue
                # 检查是否应该停止处理
                if user in self.stop_events and self.stop_events[user].is_set():
                    self.logger.info(f"[Dify] 用户 {user} 已请求停止处理")
                    break
                # 处理数据块
                # 调用回调函数输出数据块,回调响应流式但不传输给下一个模块

                # 服务端替客户端处理成Json再返回
                self.answer_chunk.final_json = json.dumps({
                    "think": self.answer_chunk.GetThinking(),
                    "response": self.answer_chunk.GetResponse(),
                    "conversation_id": self.answer_chunk.conversation_id,
                    "message_id": self.answer_chunk.message_id,
                    "Is_End": self.answer_chunk.Is_End
                })

                # 流式传输给下一个模块
                if temp_streamly and self.answer_chunk.ReadyToResponse():
                    if not first_sentence_sent:
                        # 计算首次响应时间
                        elapsed = time.time() - self.answer_chunk.startTime
                        self.logger.info(f"[Dify] 首次响应耗时: {elapsed:.2f}s | 句子数: {len(self.answer_chunk.sentences)}")
                        first_sentence_sent = True
                    for sentence in self.answer_chunk.sentences:
                        self.logger.info(f"[Dify] 发送句子: {sentence}")
                        next_func(streamly, user, sentence)

                # 流式返回
                if streamly :
                    response_func(streamly, user, self.answer_chunk.final_json)

                chunk_count += 1
            # 输出统计信息
            #logger.info(f"[Dify] 共发送 {chunk_count} 个数据块，最终输出:")
            if not streamly:
                response_func(streamly, user, self.answer_chunk.final_json)
            # 标记处理完成,并返回LLM最终的响应结果
            # response_func(streamly, user, None)

            # 只返回给下一个模块最终的回复，不包含思考过程，当然这部分可通过一些模块参数自定义
            if not self.answer_chunk.streamly:
                next_func(streamly, user, self.answer_chunk.GetResponse())
                self.logger.info(f"[Dify] 发送句子: {self.answer_chunk.GetResponse()}")
            # 当流式返回给下一个模块，但是还有剩余的数据块时，将剩余的数据块返回给下一个模块
            elif self.answer_chunk.tempResponse is not None:
                next_func(streamly, user, self.answer_chunk.tempResponse)

            return ""  # 返回空字符作为完成标记

        except Exception as e:
            # 处理异常
            error_msg = f"[Dify] 错误: {str(e)}"
            self.logger.error(error_msg)
            # 通知调用者出现错误
            response_func(streamly, user, f"ERROR: {str(e)}".encode())
            next_func(streamly, user, self.ENDSIGN)

            return ""  # 返回空字节作为完成标记

    def extract_think_response(self,answer: Answer_Chunk, response: str, streamly: bool) -> tuple:
        """
        处理流式和非流式响应，提取思考内容和最终响应
        """
        prefix = 'data: {"event": "message"'
        if not response.strip().startswith(prefix):
            return answer.GetThinking(), answer.GetResponse()

        if not answer.StartReceive:
            elapsed = time.time() - answer.startTime
            self.logger.info(f"[Dify] 首次接收到文字响应耗时: {elapsed:.2f}s")
            answer.StartReceive = True

        # 有时返回的输出结果太长了，只能分几段输出，导致json.loads报错
        if streamly:
            # 处理流式响应
            if response:
                data = response[6:]
                data = json.loads(data)
                if(answer.conversation_id == ""):
                    answer.conversation_id = data['conversation_id']
                if(answer.message_id == ""):
                    answer.message_id = data['message_id']
                if data['event'] == 'message':
                    message = str(data['answer'])
                    answer.full_content += message

                    # 检查是否进入 <think> 块
                    if "<think>" in message:
                        #logger.info("进入思考块")
                        answer.in_think_block = True

                    # 如果当前在 <think> 和 </think> 块中，将内容添加到 think_string
                    if answer.in_think_block:
                        answer.AppendThinking(message)
                    else:
                        answer.AppendResponse(message)

                    # 检查是否退出 <think> 块
                    if "</think>" in message:
                        answer.in_think_block = False
        else:
            # 处理非流式响应
            if "message" in response:
                data = response[6:]
                data = json.loads(data)
                message = data['answer']
                think_start = message.find("<think>")
                think_end = message.find("</think>")
                if think_start != -1 and think_end != -1:
                    think_string = message[think_start + 7: think_end]
                    response_string = message[think_end + 8:]
        return answer.GetThinking(), answer.GetResponse()

