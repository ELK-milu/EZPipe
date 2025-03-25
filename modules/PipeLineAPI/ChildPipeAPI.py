from typing import Any, Dict

from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse, JSONResponse

from modules.PipeLineAPI.BasePipeAPI import API_Service
from fastapi import FastAPI, HTTPException, APIRouter, Request
# @router.post("/input") 接收输入
# @router.get("/schema") 打印请求体

# 一个自定义的API服务的用例
class TextToSpeechAPIService(API_Service):
    # 扩展请求模型
    class APIRequest(API_Service.APIRequest):
        Input: str  # 指定输入为str类型
        temperature: float = 0.7  # 带默认值的新参数
        max_length: int = 100
        conversation_id: str = ""
        class Config:
            extra = "allow"  # 允许额外字段（可选）

