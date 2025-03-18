import asyncio
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Dict, Any
import queue
import threading
import time

if TYPE_CHECKING:
    from modules.PipeLine.BasePipeLine import PipeLine

class BaseModule(ABC):
    def __init__(self):
        self.stop_events: Dict[str, threading.Event] = {}
        self.next_model: Optional["BaseModule"] = None
        self.pipeline: Optional["PipeLine"] = None
        self.user_threads: Dict[str, threading.Thread] = {}
        self.output: Any = None
        self.thread_timeout = 30.0  # 线程超时时间（秒）

    def Output(self, streamly: bool, user: str, output_data: Any) -> None:
        """将模块输出发送到Pipeline并传递给下一个模块"""
        try:
            # 检查是否已请求停止处理
            if user in self.stop_events and self.stop_events[user].is_set():
                print(f"[Module] 用户 {user} 已请求停止处理，不再输出数据")
                return

            # 如果输出为None，标记任务完成
            if output_data is None:
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
                return

            # 保存输出并发送到Pipeline
            self.output = output_data
            
            # 检查用户是否已断开连接
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )
            
            if future.result(timeout=1.0):
                print(f"[Module] 用户 {user} 已断开连接，停止处理")
                # 设置停止事件
                if user in self.stop_events:
                    self.stop_events[user].set()
                return
            
            # 用户仍然连接，发送数据
            asyncio.run_coroutine_threadsafe(
                self.pipeline.add_chunk(user, output_data),
                self.pipeline.main_loop
            )

            # 如果有下一个模块，传递输出
            if self.next_model and not (user in self.stop_events and self.stop_events[user].is_set()):
                self.next_model._create_thread(streamly, user, output_data)

        except Exception as e:
            # 处理错误
            error_chunk = f"ERROR: {str(e)}"
            print(f"[Module] 输出错误: {error_chunk}")
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
                print(f"[Module] 无法发送错误消息: {str(inner_e)}")

    async def _check_if_disconnected(self, user: str) -> bool:
        """检查用户是否已断开连接"""
        if not hasattr(self.pipeline, 'disconnect_events'):
            return False
            
        # 检查断开连接事件
        return user in self.pipeline.disconnect_events and self.pipeline.disconnect_events[user].is_set()

    @abstractmethod
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, invoke_func) -> Any:
        """模块的主要处理逻辑，子类必须实现"""
        pass

    def GetService(self, streamly: bool, user: str, input_data: Any) -> None:
        """为用户创建新线程处理任务"""
        self._create_thread(streamly, user, input_data)

    def _thread_wrapper(self, streamly: bool, user: str, input_data: Any) -> None:
        """线程的包装函数，确保资源清理"""
        start_time = time.time()
        
        try:
            # 设置超时定时器
            def check_timeout():
                if time.time() - start_time > self.thread_timeout:
                    print(f"[Module] 用户 {user} 处理超时，强制终止")
                    if user in self.stop_events:
                        self.stop_events[user].set()
            
            # 启动定时器线程
            timer = threading.Timer(self.thread_timeout, check_timeout)
            timer.daemon = True
            timer.start()
            
            # 执行任务
            self.Thread_Task(streamly, user, input_data, self.Output)
            
        except Exception as e:
            print(f"[Module] {self.__class__.__name__} 线程执行错误: {str(e)}")
            try:
                self.Output(streamly, user, f"ERROR: {str(e)}")
            except:
                print(f"[Module] 无法发送错误消息给用户 {user}")
        finally:
            # 清理资源
            self._cleanup(user)
            # 取消定时器
            timer.cancel()

    def _create_thread(self, streamly: bool, user: str, input_data: Any) -> None:
        """创建新线程处理用户请求"""
        # 清理可能存在的旧线程
        self._cleanup(user)

        # 检查用户是否已断开连接
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )
            
            if future.result(timeout=1.0):
                print(f"[Module] 用户 {user} 已断开连接，不创建新线程")
                return
        except Exception as e:
            print(f"[Module] 检查用户连接状态时出错: {str(e)}")

        # 创建停止事件和线程
        self.stop_events[user] = threading.Event()
        thread = threading.Thread(
            target=self._thread_wrapper,
            args=(streamly, user, input_data),
            daemon=True  # 使用守护线程，避免程序退出时线程仍在运行
        )

        self.user_threads[user] = thread
        thread.start()
        print(f"[Module] 为用户 {user} 创建新线程: {thread.name}")

    def GetOutPut(self, user: str) -> Any:
        """获取最后一次输出"""
        return self.output

    def _cleanup(self, user: str) -> None:
        """清理用户相关资源"""
        # 设置停止事件
        if user in self.stop_events:
            self.stop_events[user].set()
            
        # 清理线程
        if user in self.user_threads:
            thread = self.user_threads[user]
            thread_id = thread.ident
            if thread.is_alive():
                print(f"[Module] 终止用户 {user} 的线程 {thread_id}")
                # 不再join线程，避免阻塞
            del self.user_threads[user]
            
        # 延迟删除停止事件，确保其他地方可以检查它
        if user in self.stop_events:
            del self.stop_events[user]

    def Destroy(self) -> None:
        """销毁模块，清理所有资源"""
        print(f"[Module] 销毁模块 {self.__class__.__name__}")
        # 获取所有用户的副本，避免在迭代过程中修改字典
        users = list(self.user_threads.keys())
        for user in users:
            self._cleanup(user)
        self.user_threads.clear()
        self.stop_events.clear()