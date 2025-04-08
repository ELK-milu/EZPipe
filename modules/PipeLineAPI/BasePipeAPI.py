import asyncio
import base64
import json
import logging
from abc import abstractmethod, ABC
from typing import Any, Dict, AsyncGenerator
from fastapi import FastAPI, HTTPException, APIRouter, Request
import uvicorn
from pydantic import BaseModel
from starlette.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from modules.PipeLine.BasePipeLine import PipeLine

# 配置logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 防止重复配置（新增）
if not logger.handlers:
    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)

    # 添加处理器到logger
    logger.addHandler(console_handler)

class API_Service(ABC):
    def __init__(self, pipeline: PipeLine, host: str = "0.0.0.0", port: int = 8000, workers: int = 1,
                 post_router: str = "/input"):
        self.pipeline = pipeline
        self.host = host
        self.port = port
        self.workers = workers
        self.app = FastAPI(title="API Service")
        self.post_router = post_router
        self.router = APIRouter()
        self._register_routes()
        self.logger = logger
        # 用于跟踪活跃的连接
        self.active_connections = set()

    class APIRequest(BaseModel):
        """API请求模型"""
        streamly: bool = False  # 是否流式输出
        user: str  # 用户标识
        Input: Any  # 输入数据
        Entry: int

    def _register_routes(self):
        """注册API路由"""

        @self.router.post(f"{self.post_router}")
        async def process_input(request: Dict[str, Any], req: Request):
            """调用管线服务"""
            user_id = request.get("user", None)
            if not user_id:
                raise HTTPException(status_code=400, detail="必须提供用户ID")

            # 为每个连接生成唯一标识符
            connection_id = f"{user_id}_{id(req)}"
            self.logger.info(f"[API] 收到用户 {user_id} 的请求，连接ID: {connection_id}")

            try:
                # 验证请求数据
                api_request = self.APIRequest(**request)

                # 强制终止该用户之前的请求
                await self.pipeline._force_cleanup_user(api_request.user)

                # 添加到活跃连接集合
                self.active_connections.add(connection_id)

                # 创建后台任务清理资源
                cleanup_task = BackgroundTask(self._cleanup_connection, connection_id, api_request.user)

                # 返回流式响应
                return StreamingResponse(
                    content=self._handle_request_stream(api_request, connection_id, req),
                    media_type="text/event-stream",
                    background=cleanup_task
                )
            except Exception as e:
                if connection_id in self.active_connections:
                    self.active_connections.remove(connection_id)
                raise HTTPException(status_code=422, detail=str(e))

        @self.router.get("/schema")
        async def get_schema():
            """返回API请求模式"""
            return JSONResponse(
                content=self.APIRequest.model_json_schema(),
                status_code=200
            )

        @self.router.get("/heartbeat")
        async def process_input(user: str):
            """心跳请求"""
            return self.pipeline.HeartBeat(user)

        # 收集所有模块路由
        for module in self.pipeline.modules:
            self.app.include_router(
                module.router,
                #prefix=f"/{module.__class__.__name__}",  # 添加模块名前缀
                #tags=[module.__class__.__name__]
            )

        # 注册路由到FastAPI应用
        self.app.include_router(self.router)

    async def _cleanup_connection(self, connection_id: str, user_id: str):
        """清理连接资源"""
        self.logger.info(f"[API] 清理连接 {connection_id} 的资源")
        if connection_id in self.active_connections:
            self.active_connections.remove(connection_id)
        await self.pipeline._cleanup_user(user_id)

    async def _is_client_disconnected(self, request: Request) -> bool:
        """检查客户端是否已断开连接"""
        try:
            # 尝试读取客户端状态
            return await request.is_disconnected()
        except:
            # 如果出现异常，假设客户端已断开
            return True

    async def _handle_request_stream(self, request: APIRequest, connection_id: str, client_request: Request) -> \
    AsyncGenerator[str, None]:
        """处理请求并返回流式响应"""
        try:
            # 处理输入数据
            processed_data = self.HandleInput(request)

            # 等待pipeline服务启动完成
            await self.pipeline.GetService(
                streamly=request.streamly,
                user=request.user,
                input_data=processed_data,
                logger = self.logger
            )

            # 流式输出结果
            async for chunk in self.pipeline.ResponseOutput(request.user):
                # 检查客户端是否断开连接
                if connection_id not in self.active_connections or await self._is_client_disconnected(client_request):
                    self.logger.info(f"[API] 检测到客户端 {request.user} 已断开连接")
                    raise asyncio.CancelledError("客户端已断开连接")

                # 转换数据格式
                response_data = None
                if isinstance(chunk, bytes):
                    # 二进制数据（如音频）编码为base64
                    response_data = {
                        "type": "audio/wav",
                        "chunk": base64.b64encode(chunk).decode("utf-8")
                    }
                elif isinstance(chunk, str):
                    # 文本数据直接输出
                    response_data = {
                        "type": "text",
                        "chunk": chunk
                    }
                else:
                    # 其他类型数据转换为字符串
                    response_data = {
                        "type": "text",
                        "chunk": str(chunk)
                    }

                # 发送数据
                yield json.dumps(response_data) + "\n"

        except asyncio.CancelledError:
            # 处理取消请求
            self.logger.info(f"[API] 请求已取消: {request.user}")
            # 从活跃连接中移除
            if connection_id in self.active_connections:
                self.active_connections.remove(connection_id)
            # 强制清理资源
            await self.pipeline._force_cleanup_user(request.user)
            return
        except Exception as e:
            # 处理其他异常
            self.logger.error(f"[API] 处理请求错误: {str(e)}")
            yield json.dumps({"error": str(e)}) + "\n"
        finally:
            pass
            # 确保清理资源
            #if connection_id in self.active_connections:
                #self.active_connections.remove(connection_id)
            #await self.pipeline._cleanup_user(request.user)

    def HandleInput(self, request: APIRequest) -> Any:  # 注意这里使用子类的APIRequest类型
        return self.pipeline.modules[request.Entry].HandleInput(request)

    def Run(self):
        """启动API服务"""
        # 首先检查pipeline是否通过验证
        if not self.pipeline.validated:
            self.logger.error("Pipeline未通过验证，无法启动API服务")
            import sys
            sys.exit(1)

        # 创建新的事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 设置pipeline的主事件循环
        self.pipeline.main_loop = self.loop
        # 配置uvicorn服务器
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            loop="asyncio"
        )
        self.pipeline.logger = self.logger
        self.pipeline.StartUp()
        # 启动服务器
        server = uvicorn.Server(config)
        self.loop.run_until_complete(server.serve())
