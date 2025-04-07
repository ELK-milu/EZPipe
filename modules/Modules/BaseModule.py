import asyncio
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Dict, Any
import queue
import threading
import time
import concurrent.futures

import requests
from fastapi import APIRouter

from utils.logger import get_logger, track_time, track_module_time

if TYPE_CHECKING:
    from modules.PipeLine.BasePipeLine import PipeLine
    from modules.PipeLineAPI.BasePipeAPI import API_Service

# 创建模块日志记录器
logger = get_logger("BaseModule")

class BaseModule(ABC):
    def __init__(self):
        self.stop_events: Dict[str, threading.Event] = {}
        self.next_model: Optional["BaseModule"] = None
        self.pipeline: Optional["PipeLine"] = None
        self.user_threads: Dict[str, threading.Thread] = {}
        self.user_InputQueue: Dict[str, queue.Queue] = {} # 接受输入的队列
        self.output: Any = None
        self.thread_timeout = 120.0  # 线程超时时间（秒）
        self.streaming_status: Dict[str, bool] = {}  # 跟踪用户的流式处理状态
        self.answer_chunk = None
        self.session : requests.Session = None  # 会话管理，用于长连接
        # 新增路由相关属性
        self.router: APIRouter = APIRouter()
        self.ENDSIGN = None
        self.RegisterRoutes()
        # 创建线程池，用于并行处理任务
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)


    # 初始化方法，用于模块被添加进PipeLine并启动API服务后自动调用
    def StartUp(self):
        pass


    def RegisterRoutes(self):
        """模块自定义路由注册入口"""
        self.register_module_routes()

    # 注册路由方法，可以由子类实现，用于注册模块专属的API
    # 子类可重写此方法添加自定义路由
    def register_module_routes(self):
        """供子类重写的路由注册方法"""
        pass

    # Update方法，用于一些持续性的输出，例如心跳连接
    def HeartBeat(self,user:str):
        '''
        while self.session:
            try:
                # 发送HEAD请求（轻量级，不下载响应体）
                self.session.head("http://localhost/v1", timeout=10)
            except requests.exceptions.RequestException as e:
                print(f"Heartbeat failed: {e}")
            time.sleep(0.5)
        '''
        pass

    # 一个简单的用于处理线程任务内数据的类，如有需要可拓展和使用
    class Answer_Chunk:
        streamly: bool = False  # 是否流式输出
        user: str  # 用户标识
        Input: Any  # 输入数据

    # 一个模块参数自定义的类，如有需要可拓展和使用
    class Module_Config:
        streamly: bool = False

    # 每个子模块需要实现的抽象方法，自定义输入数据，返回服务端请求体处理后的数据
    @abstractmethod
    def HandleInput(self,request: Any) -> Any:
        processed_data = request
        return processed_data

    @abstractmethod
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> Any:
        """模块的主要处理逻辑，子类必须实现"""
        # 在定义这个方法的时候需要指定input_data和函数输出的类型，用于pipeline检验当前模块所需的输入输出类型
        pass

    # 有时我们希望API给出的流式返回值和进入下一个模块的输入值不一样，因此设置了两个回调函数
    def Next_output(self, streamly: bool, user: str, output: Any):
        # 如果有下一个模块，且next_input非空,传递输出
        if self.next_model:
            # 使用异步方式添加数据到下一个模块的输入队列
            if user not in self.next_model.user_InputQueue:
                self.next_model.user_InputQueue[user] = queue.Queue()
            
            # 直接添加数据到队列，不创建新线程
            self.next_model.user_InputQueue[user].put(output)
            logger.debug(f"[{self.__class__.__name__}] 添加数据{str(output)}到 {self.next_model.__class__.__name__} 输入队列")
            
            # 为每个输入创建新线程，实现真正的并行处理
            self.next_model._create_thread(streamly, user, None)

    @track_time(logger)
    def Response_output(self, streamly: bool, user: str, response_data: Any) -> None:
        """将模块输出发送到Pipeline并传递给下一个模块"""
        logger.info(f"[{self.__class__.__name__}] 用户 {user} 处理完成，输出数据")
        try:
            # 检查是否已请求停止处理
            if user in self.stop_events and self.stop_events[user].is_set():
                logger.info(f"[{self.__class__.__name__}] 用户 {user} 已请求停止处理，不再输出数据")
                return

            # 如果输出为None,且没有后续模块,且当前队列里没有待处理的内容,标记任务完成
            if response_data == self.ENDSIGN and self.next_model is None:
                logger.info(f"[{self.__class__.__name__}] 用户 {user} 已处理完成，不再输出数据")
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
                return

            if response_data == self.ENDSIGN:
                logger.info(f"[{self.__class__.__name__}] 下一个模块是 [{self.next_model.__class__.__name__}] ")

            # 保存输出并发送到Pipeline
            self.output = response_data
            
            # 检查用户是否已断开连接
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )
            
            if future.result(timeout=1.0):
                logger.info(f"[{self.__class__.__name__}] 用户 {user} 已断开连接，停止处理")
                # 设置停止事件
                if user in self.stop_events:
                    self.stop_events[user].set()
                return


            # 如果输出为None且没有后续模块,把终止信号None输出到PipeLine
            if response_data == self.ENDSIGN and self.next_model is None:
                # 用户仍然连接，发送数据
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.add_chunk(user, self.pipeline.ENDSIGN),
                    self.pipeline.main_loop
                )
            elif response_data != self.ENDSIGN:
                # 用户仍然连接，发送数据
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.add_chunk(user, response_data),
                    self.pipeline.main_loop
                )


        except Exception as e:
            # 处理错误
            error_chunk = f"ERROR: {str(e)}"
            logger.error(f"[{self.__class__.__name__}] 输出错误: {error_chunk}")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.add_chunk(user, error_chunk),
                    self.pipeline.main_loop
                )
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
            except Exception as inner_e:
                logger.error(f"[{self.__class__.__name__}] 无法发送错误消息: {str(inner_e)}")

    async def _check_if_disconnected(self, user: str) -> bool:
        """检查用户是否已断开连接"""
        if not hasattr(self.pipeline, 'disconnect_events'):
            return False
            
        # 检查断开连接事件
        return user in self.pipeline.disconnect_events and self.pipeline.disconnect_events[user].is_set()



    def GetService(self, streamly: bool, user: str, input_data: Any) -> None:
        """为用户创建新线程处理任务"""
        self._create_thread(streamly, user, input_data)

    # 修改线程包装逻辑，使其处理单个输入后退出
    @track_time(logger)
    def _thread_wrapper(self, streamly: bool, user: str, input_data: Any) -> None:
        """处理单个输入数据的线程包装"""
        try:
            # 如果input_data为None，尝试从队列中获取数据
            if input_data is None and user in self.user_InputQueue:
                try:
                    input_data = self.user_InputQueue[user].get_nowait()
                    logger.debug(f"[{self.__class__.__name__}] 从队列获取数据: {str(input_data)[:20]}...")
                except queue.Empty:
                    logger.warning(f"[{self.__class__.__name__}] 队列为空，无法获取数据")
                    return
            
            # 处理单个数据块
            self.Thread_Task(streamly, user, input_data,
                             self.Response_output,
                             self.Next_output)
        finally:
            # 处理完成后清理资源
            self._cleanup_thread(user)

    def _cleanup_thread(self, user: str) -> None:
        """清理线程资源，但不清理用户队列"""
        # 清理线程
        if user in self.user_threads:
            thread = self.user_threads[user]
            thread_id = thread.ident
            if thread.is_alive():
                logger.info(f"[{self.__class__.__name__}] 终止用户 {user} 的线程 {thread_id}")
            del self.user_threads[user]

    @track_time(logger)
    def _create_thread(self, streamly: bool, user: str, input_data: Any) -> None:
        """创建新线程处理用户请求"""
        # 确保用户输入队列存在
        if user not in self.user_InputQueue:
            self.user_InputQueue[user] = queue.Queue()
            
        # 只有当input_data不为None时才添加到队列
        if input_data is not None:
            self.user_InputQueue[user].put(input_data)
            
        # 检查用户是否已断开连接
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )

            if future.result(timeout=1.0):
                logger.info(f"[{self.__class__.__name__}] 用户 {user} 已断开连接，不创建新线程")
                return
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] 检查用户连接状态时出错: {str(e)}")

        # 创建停止事件和线程
        self.stop_events[user] = threading.Event()
        
        # 使用线程池提交任务，而不是直接创建线程
        # 这样可以更好地管理线程资源，避免创建过多线程
        self.thread_pool.submit(
            self._thread_wrapper,
            streamly, user, input_data
        )
        
        # 记录线程信息
        if streamly:
            self.streaming_status[user] = True
        logger.info(f"[{self.__class__.__name__}] 为用户 {user} 提交任务到线程池")

    def GetOutPut(self, user: str) -> Any:
        """获取最后一次输出"""
        return self.output

    def _cleanup(self, user: str) -> None:
        """清理用户相关资源"""
        # 设置停止事件
        if user in self.stop_events:
            self.stop_events[user].set()

        if user in self.user_InputQueue:
            del self.user_InputQueue[user]
            
        # 清理线程
        if user in self.user_threads:
            thread = self.user_threads[user]
            thread_id = thread.ident
            if thread.is_alive():
                logger.info(f"[{self.__class__.__name__}] 终止用户 {user} 的线程 {thread_id}")
            del self.user_threads[user]
            
        # 清理流式状态
        if user in self.streaming_status:
            del self.streaming_status[user]
            
        # 延迟删除停止事件，确保其他地方可以检查它
        if user in self.stop_events:
            del self.stop_events[user]

    def Destroy(self) -> None:
        """销毁模块，清理所有资源"""
        logger.info(f"[{self.__class__.__name__}] 销毁模块 {self.__class__.__name__}")
        # 获取所有用户的副本，避免在迭代过程中修改字典
        users = list(self.user_threads.keys())
        for user in users:
            self._cleanup(user)
        self.user_threads.clear()
        self.stop_events.clear()
        self.streaming_status.clear()
        if self.session:
            self.session.close()
        # 关闭线程池
        self.thread_pool.shutdown(wait=False)