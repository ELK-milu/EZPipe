import json
import threading
from typing import Optional, Any

import requests

from ..BaseModule import BaseModule
from .DifyPost import PostChat,session



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
            self.session: requests.Session = None  # 单会话，用于长连接，暂未使用多会话

        def GetThinking(self) -> str:
            return self.think_string

        def GetResponse(self) -> str:
            return self.response_string

        def AppendThinking(self, content):
            self.think_string += content

        def AppendResponse(self, content):
            self.response_string += content

    def Update(self):
        self.session = session

    def StartUp(self):
        if self.session is None:
            self.session = session

    def HandleInput(self, request: Any) -> str:
        return request.Input

    """LLM对话模块（输入类型：str，输出类型：str）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: str, response_func,next_func) -> str:
        self.answer_chunk = self.Answer_Chunk(text=input_data, user=user, streamly=streamly)
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
        print(f"[Dify] 开始为用户 {user} 处理文本: {input_data[:20]}...")
        chat_response = None
        try:
            if self.session is None:
                self.session = session
            chat_response = PostChat(streamly=streamly, user=user, text=input_data).GetResponse()
            print(f"[Dify] 响应状态码: {chat_response.status_code}")
            # 用于统计处理的数据块
            chunk_count = 0
            # 循环处理响应中的数据块
            for chunk in chat_response.iter_content(chunk_size=None):
                decoded = chunk.decode('utf-8')
                self.extract_think_response(self.answer_chunk, decoded, streamly)
                print(f"[Dify] think:{self.answer_chunk.GetThinking()}\nResponse:{self.answer_chunk.GetResponse()}")

                if self.stop_events[user].is_set():
                    break

                if not chunk:  # 跳过空块
                    print("[Dify] 收到空数据块")
                    continue
                # 检查是否应该停止处理
                if user in self.stop_events and self.stop_events[user].is_set():
                    print(f"[Dify] 用户 {user} 已请求停止处理")
                    break
                # 处理数据块
                # 调用回调函数输出数据块,回调响应流式但不传输给下一个模块

                # 服务端替客户端处理成Json再返回
                final_json = json.dumps({
                    "think": self.answer_chunk.GetThinking(),
                    "response": self.answer_chunk.GetResponse(),
                    "Is_End": self.answer_chunk.Is_End
                })
                response_func(streamly, user, final_json)
                chunk_count += 1
            # 输出统计信息
            print(f"[Dify] 共发送 {chunk_count} 个数据块，最终输出:")
            # 标记处理完成,并返回LLM最终的响应结果
            response_func(streamly, user, None)

            # 只返回给下一个模块最终的回复，不包含思考过程，当然这部分可通过一些模块参数自定义
            next_func(streamly, user, self.answer_chunk.GetResponse())

            return ""  # 返回空字符作为完成标记

        except Exception as e:
            # 处理异常
            error_msg = f"[Dify] 错误: {str(e)}"
            print(error_msg)
            # 通知调用者出现错误
            response_func(streamly, user, f"ERROR: {str(e)}".encode())
            next_func(streamly, user, None)

            return ""  # 返回空字节作为完成标记

        finally:
            # 确保关闭响应
            if chat_response:
                chat_response.close()

    def extract_think_response(self,answer: Answer_Chunk, response: str, streamly: bool) -> tuple:
        """
        处理流式和非流式响应，提取思考内容和最终响应
        """
        prefix = 'data: {"event": "message"'
        if not response.strip().startswith(prefix):
            return answer.GetThinking(), answer.GetResponse()

        # 有时返回的输出结果太长了，只能分几段输出，导致json.loads报错
        if streamly:
            # 处理流式响应
            if response:
                data = response[6:]
                data = json.loads(data)
                if data['event'] == 'message':
                    message = str(data['answer'])
                    print(message)
                    answer.full_content += message

                    # 检查是否进入 <think> 块
                    if "<think>" in message:
                        print("进入思考块")
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

