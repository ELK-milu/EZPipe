import asyncio
import json
from abc import abstractmethod, ABC
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, APIRouter
import uvicorn
from pydantic import BaseModel
from starlette.responses import JSONResponse, StreamingResponse

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
                api_request = self.APIRequest(**request)
                return StreamingResponse(
                    content=self._handle_request_stream(api_request),
                    media_type="text/event-stream"
                )
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

    async def _handle_request_stream(self, request: APIRequest):
        print(f"[API] Starting stream for {request.user}")
        try:
            # 清理之前的请求
            self.pipeline._cleanup(request.user)

            processed_data = self.HandleInput(request)
            print(f"[API] Processed data: {processed_data}...")

            # 使用新的异步任务
            async def service_task():
                try:
                    self.pipeline.GetService(
                        streamly=request.streamly,
                        user=request.user,
                        input_data=processed_data
                    )
                except Exception as e:
                    print(f"Service error: {str(e)}")

            # 在正确的事件循环中运行
            task = asyncio.create_task(service_task())

            # 流式响应
            async for chunk in self.pipeline.ResponseOutput(request.user):
                if task.done() and task.exception():
                    raise task.exception()
                yield f"{json.dumps({'chunk': str(chunk)})}\n"

        except asyncio.CancelledError:
            print(f"请求被取消: {request.user}")
            raise
        except Exception as e:
            print(f"[API] Stream error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            print(f"[API] Stream closed for {request.user}")

    async def GetFinalOut(self, request: APIRequest):
        """统一请求处理流程"""
        try:
            return await self.pipeline.Output(request.user)
        finally:
            pass
            #self.pipeline.Destroy()  # 确保无论是否异常都会执行销毁

    @abstractmethod
    def HandleInput(self, request: APIRequest) -> Any:
        """抽象方法，子类必须实现具体数据处理逻辑"""
        pass

    def Run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 关键修复：同步pipeline的事件循环
        self.pipeline.main_loop = self.loop

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        self.loop.run_until_complete(server.serve())
