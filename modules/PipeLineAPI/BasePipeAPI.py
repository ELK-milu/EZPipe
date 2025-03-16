import json
from abc import abstractmethod, ABC
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, APIRouter
import uvicorn
from pydantic import BaseModel
from starlette.responses import JSONResponse

from modules.PipeLine.BasePipeLine import PipeLine

class API_Service(ABC):
    def __init__(self, pipeline: PipeLine, host: str = "0.0.0.0", port: int = 8000, workers: int = 1,post_router: str = "/input"):
        self.pipeline = pipeline
        self.host = host
        self.port = port
        self.workers = workers
        self.app = FastAPI(title="API Service")
        self.post_router = post_router
        self.router = APIRouter()
        self.result = None
        self._register_routes()

    class APIRequest(BaseModel):
        streamly: bool = False
        user: str
        Input: Any  # 允许子类通过继承扩展字段

    def Print_Request_Schema(self):
        """打印API请求体的结构定义（可被子类重写）"""
        schema = self.APIRequest.model_json_schema()
        print("\n" + "="*35 + " API Request Structure " + "="*35)
        print(json.dumps(schema, indent=2, ensure_ascii=False))
        print("="*92 + "\n")

    def Print_Request(self, request: APIRequest):
        """打印请求体（可被子类重写）"""
        print("\n" + "="*40 + " API Request " + "="*40)
        print(request.model_dump())  # Pydantic v2+ 使用 model_dump()
        # 若使用Pydantic v1可替换为 dict() 或 json()
        print("="*93 + "\n")


    def _register_routes(self):
        @self.router.post(f"{self.post_router}")
        async def process_input(request: Dict[str, Any]):
            try:
                # 请求参数验证
                api_request = self.APIRequest(**request)
                return await self._handle_request(api_request)
            except Exception as e:
                raise HTTPException(status_code=422, detail=str(e))

        @self.router.get("/schema")
        async def get_schema():
            """获取API请求结构定义"""
            return JSONResponse(
                content=self.APIRequest.model_json_schema(),
                status_code=200
            )

        self.app.include_router(self.router)


    def _register_shutdown_handler(self):
        # 注册FastAPI的shutdown事件处理器
        self.app.add_event_handler("shutdown", self._shutdown_pipeline)

    def _shutdown_pipeline(self):
        """服务关闭时销毁pipeline"""
        if hasattr(self.pipeline, "Destroy"):
            self.pipeline.Destroy()

    async def _handle_request(self, request: APIRequest):
        """统一请求处理流程"""
        processed_data = self.HandleInput(request)
        self.pipeline.GetService(
            streamly=request.streamly,
            user=request.user,
            input_data=processed_data
        )
        try:
            return await self.pipeline.Output(request.user)
        finally:
            self.pipeline.Destroy()  # 确保无论是否异常都会执行销毁

    @abstractmethod
    def HandleInput(self, request: APIRequest) -> Any:
        """抽象方法，子类必须实现具体数据处理逻辑"""
        pass

    def Run(self):
        """启动API服务"""
        uvicorn.run(
            app=self.app,
            host=self.host,
            port=self.port,
            workers=self.workers,
            reload=False
        )
