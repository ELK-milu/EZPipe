import argparse
import json
from typing import Generator, Union
from threading import Thread
from .DeepSeekPost import PostChat
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# 正确推导到pipeline目录（上溯两级）
pipeline_dir = os.path.dirname(os.path.dirname(current_dir))  # D:\LCBot\LCBotDocker\pipeline
sys.path.append(pipeline_dir)
from modules.TTS.GPTSovit_TTS_Client import GetService as GetTTSService


def extract_think_response(response, streamly: bool) -> tuple:
    """
    处理流式和非流式响应，提取思考内容和最终响应
    """
    think_string = ""
    response_string = ""
    full_content = ""
    in_think_block = False  # 标记是否在 <think> 块中
    #print("response:" + str(response))

    if streamly:
        # 处理流式响应
        if response.startswith("data: "):
            data = response[6:]
            data = json.loads(data)
            if "choices" in data and data["choices"]:
                content = data["choices"][0].get("delta", {}).get("content", "")
                print("content:" + str(content))
                full_content += content

                # 检查是否进入 <think> 块
                if "<think>" in content:
                    in_think_block = True
                # 检查是否退出 <think> 块
                if "</think>" in content:
                    in_think_block = False

                # 如果当前在 <think> 块中，将内容添加到 think_string
                if in_think_block:
                    think_string += content
                else:
                    response_string += content

                print("think_string:" + str(think_string))
                print("response_string:" + str(response_string))
                # 检查是否结束
                #if data["choices"][0].get("finish_reason") == "stop":
                    #break
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

    return think_string, response_string

def handle_stream_response(chat_response: Generator):
    for response in chat_response:
        think_string, response_string = extract_think_response(response, streamly=True)
        # 在这里处理 think_string 和 response_string
        print("Stream Response - Think:", think_string)
        print("Stream Response - Response:", response_string)

def GetService(streamly,user,text):
    print("GetLLMService")
    # 调用对话服务
    chat_Response = PostChat(
        streamly=streamly,
        user=user,
        text=text
    ).GetResponse()

    print("Response:",chat_Response.text)

    if streamly:
        # 开启一个线程用于持续接收返回响应并处理
        thread = Thread(target=handle_stream_response, args=(chat_Response,))
        thread.start()
    else:
        # 非流式传输则直接接收并处理
        think_string, response_string = extract_think_response(chat_Response.text, streamly=False)
        print("Think:", think_string)
        print("Response:", response_string)

    GetTTSService(streamly,user,response_string)
    return response_string

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="LLM对话服务客户端")
    parser.add_argument("--streamly", action="store_true", help="使用流式传输")
    parser.add_argument("--user", type=str, default="user", help="用户标识")
    parser.add_argument("--text", type=str, required=True, help="输入文本")
    args = parser.parse_args()
    GetService(args.streamly, args.user, args.text)


if __name__ == "__main__":
    main()