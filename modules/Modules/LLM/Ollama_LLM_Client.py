import argparse
import json
import platform
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# 正确推导到pipeline目录（上溯两级）
pipeline_dir = os.path.dirname(os.path.dirname(current_dir))  # D:\LCBot\LCBotDocker\pipeline
sys.path.append(pipeline_dir)
from modules.Modules.LLM.OllamaPost import PostChat

class Answer_Chunk:
    def __init__(self, text, user, streamly, NextModel=None):
        self.text = text
        self.user = user
        self.streamly = streamly
        self.in_think_block = False
        self.think_string = ""
        self.response_string = ""
        self.full_content = ""
        self.Is_End = False
        self.OutPut:BaseModel = NextModel
        self.thread: Thread = None

    def GetThinking(self) -> str:
        return self.think_string

    def GetResponse(self) -> str:
        return self.response_string

    def AppendThinking(self, content):
        self.think_string += content

    def AppendResponse(self, content):
        self.response_string += content

    def close(self):
        if self.thread and self.thread.is_alive():
            self.thread.join()
            print("线程已释放")
    def __del__(self):
        print(f"LLM对象被销毁")
        # 释放线程
        self.close()

def extract_think_response(answer: Answer_Chunk,response:str, streamly: bool) -> tuple:
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
                else :
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
                think_string = content[think_start + 7 : think_end]
                response_string = content[think_end + 8 :]

        if data["done"] is True:
            answer.Is_End = True

    return answer.GetThinking(),  answer.GetResponse()




def handle_stream_response(chat_response, answer: Answer_Chunk, invoke_func):
    try:
        if not answer.streamly:
            # 非流式传输则直接接收并处理
            extract_think_response(answer, chat_response.text, answer.streamly)
            invoke_func(answer)
        else:
            for chunk in chat_response.iter_content(chunk_size=None):
                if chunk:
                    try:
                        decoded = chunk.decode('utf-8')
                        # 处理业务逻辑
                        extract_think_response(answer, decoded, answer.streamly)
                        invoke_func(answer)
                    except UnicodeDecodeError:
                        print(f"解码失败: {chunk.hex()}")

    except Exception as e:
        print(f"处理流时出错: {str(e)}")
    finally:
        chat_response.close()  # 确保释放连接
def GetService(streamly:bool,user:str,text):
    print("GetLLMService")
    # 调用对话服务
    chat_Response = PostChat(
        streamly=streamly,
        user=user,
        text=text
    ).GetResponse()
    answer = Answer_Chunk(text=text, user=user, streamly=streamly)
    answer.thread = Thread(target=handle_stream_response, args=(chat_Response, answer, on_stream_complete))
    answer.thread.start()
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
        answer.NextModel.GetTTSService(answer.streamly, answer.user, answer.GetResponse())
        del answer


def external_call(streamly, user, text):
    # 外部调用 GetService
    answer = GetService(streamly, user, text)
    # 等待线程完成
    answer.thread.join()
    # 显式释放资源
    answer.close()

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="LLM对话服务客户端")
    parser.add_argument("--streamly", action="store_true", help="使用流式传输")
    parser.add_argument("--user", type=str, default="user", help="用户标识")
    parser.add_argument("--text", type=str, required=True, help="输入文本")
    args = parser.parse_args()
    #GetService(args.streamly, args.user, args.text)
    # 使用线程池管理线程
    with ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(GetService, streamly=args.streamly, user=args.user, text=args.text)
        answer = future.result()  # 获取 Answer_Chunk 对象
        # 主程序等待线程完成
        answer.thread.join()
        # 显式释放资源
        answer.close()


if __name__ == "__main__":
    # 启动 main 服务
    main()
