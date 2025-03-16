import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# 正确推导到pipeline目录（上溯两级）
pipeline_dir = os.path.dirname(os.path.dirname(current_dir))  # D:\LCBot\LCBotDocker\pipeline
sys.path.append(pipeline_dir)
from modules.Modules.LLM.LangChain_LLM_Client import external_call


if __name__ == '__main__':
    external_call(streamly=True, user="user123", text="你好，这是一个测试。")