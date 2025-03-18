import threading
from typing import Optional

from ..BaseModule import BaseModule
from .OllamaPost import PostChat



class Ollama_LLM_Module(BaseModule):
    """语音合成模块（输入类型：str，输出类型：str）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: str, invoke_func) -> str:
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
        print(f"[Ollama] 开始为用户 {user} 处理文本: {input_data[:20]}...")
        chat_response = None

        try:
            chat_response = PostChat(streamly=streamly, user=user, text=input_data).GetResponse()
            print(f"[Ollama] 响应状态码: {chat_response.status_code}")
            # 用于统计处理的数据块
            chunk_count = 0
            # 循环处理响应中的数据块
            for chunk in chat_response.iter_content(chunk_size=None):
                decoded = chunk.decode('utf-8')
                print(f"[Ollama] chunk:{decoded}")
                if self.stop_events[user].is_set():
                    break
                if not chunk:  # 跳过空块
                    print("[Ollama] 收到空数据块")
                    continue
                # 检查是否应该停止处理
                if user in self.stop_events and self.stop_events[user].is_set():
                    print(f"[Ollama] 用户 {user} 已请求停止处理")
                    break
                # 处理数据块
                # 调用回调函数输出数据块
                invoke_func(streamly, user, decoded)
                chunk_count += 1
            # 输出统计信息
            print(f"[Ollama] 共发送 {chunk_count} 个数据块，最终输出:")
            # 标记处理完成
            invoke_func(streamly, user, None)
            return ""  # 返回空字符作为完成标记

        except Exception as e:
            # 处理异常
            error_msg = f"[Ollama] 错误: {str(e)}"
            print(error_msg)

            # 通知调用者出现错误
            invoke_func(streamly, user, f"ERROR: {str(e)}".encode())
            invoke_func(streamly, user, None)

            return ""  # 返回空字节作为完成标记

        finally:
            # 确保关闭响应
            if chat_response:
                chat_response.close()

    def extract_think_response(answer: Answer_Chunk, response: str, streamly: bool) -> tuple:
        """
        处理流式和非流式响应，提取思考内容和最终响应
        """

        if streamly:
            # 处理流式响应
            if response:
                data = json.loads(response)
                if "message" in data:
                    message = data["message"]
                    if isinstance(message, list):  # 兼容数组格式
                        content = message[0].get("content", "") if message else ""
                    else:  # 处理对象格式
                        content = message.get("content", "")
                    answer.full_content += content

                    # 检查是否进入 <think> 块
                    if "<think>" in content:
                        answer.in_think_block = True

                    # 如果当前在 <think> 和 </think> 块中，将内容添加到 think_string
                    if answer.in_think_block:
                        answer.AppendThinking(content)
                    else:
                        answer.AppendResponse(content)

                    # 检查是否退出 <think> 块
                    if "</think>" in content:
                        answer.in_think_block = False
                    # 检查是否结束
                    if data["done"] is True:
                        answer.Is_End = True
        else:
            # 处理非流式响应
            if "message" in response:
                data = json.loads(response)
                message = data["message"]
                if isinstance(message, list):  # 兼容数组格式
                    content = message[0].get("content", "") if message else ""
                else:  # 处理对象格式
                    content = message.get("content", "")
                think_start = content.find("<think>")
                think_end = content.find("</think>")
                if think_start != -1 and think_end != -1:
                    think_string = content[think_start + 7: think_end]
                    response_string = content[think_end + 8:]

            if data["done"] is True:
                answer.Is_End = True

        return answer.GetThinking(), answer.GetResponse()


