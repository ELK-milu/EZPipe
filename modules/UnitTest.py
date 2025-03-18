# 定义处理模块
import time

from modules.Modules.BaseModule import BaseModule
from modules.PipeLine.BasePipeLine import PipeLine
from modules.PipeLineAPI.BasePipeAPI import API_Service


class TextProcessor(BaseModule):
    def Thread_Task(self, streamly, user, input_data, response_func):
        # 模拟流式处理
        for word in input_data.split(""):
            response_func(streamly, user, word.upper())
            time.sleep(0.1)


# 创建管道
pipeline = PipeLine.create_pipeline(TextProcessor)


# API请求处理
async def example_usage():
    request = API_Service.APIRequest(
        user="test_user",
        Input="hello world",
        streamly=True
    )

    async for chunk in pipeline.ResponseOutput("test_user"):
        print(f"Received chunk: {chunk}")