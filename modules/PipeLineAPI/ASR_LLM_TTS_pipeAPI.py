from typing import Any

from modules.PipeLineAPI.BasePipeAPI import API_Service

# @router.post("/input") 接收输入
# @router.get("/schema") 打印请求体

# 一个自定义的API服务的用例
class ASR_LLM_TTS_pipeAPI(API_Service):
    # 扩展请求模型
    class APIRequest(API_Service.APIRequest):
        Input: Any  # 指定输入为any类型
        temperature: float = 0.7  # 带默认值的新参数
        max_length: int = 100
        class Config:
            extra = "allow"  # 允许额外字段（可选）
