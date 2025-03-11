import argparse
import json
import platform
from asyncio import as_completed
from concurrent.futures import ThreadPoolExecutor
from typing import Generator, Union
from threading import Thread
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# 正确推导到pipeline目录（上溯两级）
pipeline_dir = os.path.dirname(os.path.dirname(current_dir))  # D:\LCBot\LCBotDocker\pipeline
sys.path.append(pipeline_dir)
from modules.LLM.DeepSeekPost import PostChat
from modules.TTS.GPTSovit_TTS_Client import GetService as GetTTSService



class StreamProcessor:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._futures = []

    def process_stream(self, response):
        future = self._executor.submit(handle_stream_response, response)
        self._futures.append(future)
        return future

    def shutdown(self):
        for future in as_completed(self._futures):
            try:
                future.result()
            except Exception:
                pass
        self._executor.shutdown(wait=True)


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
        self.thread = None

    def GetThinking(self) -> str:
        return self.think_string

    def GetResponse(self) -> str:
        return self.response_string

    def AppendThinking(self, content):
        self.think_string += content

    def AppendResponse(self, content):
        self.response_string += content
    def close(self):
        """显式释放线程资源"""
        if self.thread and self.thread.is_alive():
            self.thread.join()  # 等待线程完成
        print("对象资源已释放")
    def __del__(self):
        self.close()  # 确保资源释放

def extract_think_response(answer: Answer_Chunk,response, streamly: bool) -> tuple:
    """
    处理流式和非流式响应，提取思考内容和最终响应
    """

    if streamly:
        # 处理流式响应
        if response.startswith("data: "):
            data = response[6:]
            data = json.loads(data)
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("delta", {}).get("content", "")
                answer.full_content += content

                # 检查是否进入 <think> 块
                if "<think>" in content:
                    answer.in_think_block = True

                # 如果当前在 <think> 和 </think> 块中，将内容添加到 think_string
                if answer.in_think_block:
                    answer.AppendThinking(content)
                else :
                    answer.AppendResponse(content)

                # 检查是否退出 <think> 块
                if "</think>" in content:
                    answer.in_think_block = False
                # 检查是否结束
                if data["choices"][0].get("finish_reason") == "stop":
                    answer.Is_End = True
    else:
        # 处理非流式响应
        if "choices" in response:
            data = json.loads(response)
            content = data["choices"][0].get("message", {}).get("content", "")
            think_start = content.find("<think>")
            think_end = content.find("</think>")
            if think_start != -1 and think_end != -1:
                think_string = content[think_start + 7 : think_end]
                response_string = content[think_end + 8 :]

        if data["choices"][0].get("finish_reason") == "stop":
            answer.Is_End = True

    return answer.GetThinking(),  answer.GetResponse()




def handle_stream_response(chat_response, answer: Answer_Chunk, invoke_func):
    try:
        if answer.streamly:
            # 非流式传输则直接接收并处理
            extract_think_response(answer, chat_response.text, streamly=False)
            invoke_func(answer)
        else:
            for chunk in chat_response.iter_content(chunk_size=4096):
                if chunk:
                    try:
                        decoded = chunk.decode('utf-8')
                        # 处理业务逻辑
                        extract_think_response(answer, decoded, True)
                        invoke_func(answer)
                    except UnicodeDecodeError:
                        print(f"解码失败: {chunk.hex()}")
    except Exception as e:
        print(f"处理流时出错: {str(e)}")
    finally:
        chat_response.close()  # 确保释放连接
def GetService(streamly,user,text):
    print("GetLLMService")
    # 调用对话服务
    chat_Response = PostChat(
        streamly=streamly,
        user=user,
        text=text
    ).GetResponse()
    response_string = ""
    answer = Answer_Chunk(text=text, user=user, streamly=streamly)
    answer.thread = Thread(target=handle_stream_response, args=(chat_Response, answer, on_stream_complete))
    answer.thread.start()
    ##GetTTSService(streamly,user,response_string)
    return answer

def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


def on_stream_complete(answer: Answer_Chunk):
    clear_screen()
    print("Think:", answer.GetThinking())
    print("Response:", answer.GetResponse())
    if answer.Is_End :
        GetTTSService(answer.streamly, answer.user, answer.GetResponse())
        answer.close()


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="LLM对话服务客户端")
    parser.add_argument("--streamly", action="store_true", help="使用流式传输")
    parser.add_argument("--user", type=str, default="user", help="用户标识")
    parser.add_argument("--text", type=str, required=True, help="输入文本")
    args = parser.parse_args()
    GetService(args.streamly, args.user, args.text)
    # 使用线程池管理线程
    with ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(GetService, streamly=True, user="test_user", text="Hello, world!")
        answer = future.result()  # 获取 Answer_Chunk 对象

        # 主程序等待线程完成
        answer.thread.join()

        # 显式释放资源
        answer.close()


if __name__ == "__main__":
    main()