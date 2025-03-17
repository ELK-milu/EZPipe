from typing import Any

from modules.PipeLineAPI.BasePipeAPI import API_Service

# @router.post("/input") 接收输入
# @router.get("/schema") 打印请求体

# 一个自定义的API服务的用例
class SampleAPIService(API_Service):
    # 扩展请求模型
    class APIRequest(API_Service.APIRequest):
        Input: str  # 指定输入为str类型
        temperature: float = 0.7  # 带默认值的新参数
        max_length: int = 100

        class Config:
            extra = "allow"  # 允许额外字段（可选）

    def HandleInput(self, request: APIRequest) -> Any:  # 注意这里使用子类的APIRequest类型
        # 现在可以使用新增字段
        print(f"Received request: {request}")
        processed_data = f"{request.Input}"
        print(f"Received input: {processed_data}")
        return processed_data