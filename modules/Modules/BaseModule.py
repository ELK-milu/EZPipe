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
        self.streaming_status: Dict[str, bool] = {}  # 跟踪用户的流式处理状态
        self.answer_chunk = None

    # 一个简单的用于处理线程任务内数据的类，如有需要可拓展和使用
    class Answer_Chunk:
        streamly: bool = False  # 是否流式输出
        user: str  # 用户标识
        Input: Any  # 输入数据

    # 一个模块参数自定义的类，如有需要可拓展和使用
    class Module_Config:
        streamly: bool = False

    # 有时我们希望API给出的流式返回值和进入下一个模块的输入值不一样，因此设置了两个回调函数
    def Next_output(self, streamly: bool, user: str, output: Any):
        # 如果有下一个模块，且next_input非空,传递输出
        if self.next_model and not (user in self.stop_events and self.stop_events[user].is_set()):
            self.next_model._create_thread(streamly, user, output)
            self.output = output
        return output

    def Response_output(self, streamly: bool, user: str, response_data: Any) -> None:
        """将模块输出发送到Pipeline并传递给下一个模块"""
        try:
            print(f"[{self.__class__.__name__}] response_data:{response_data}")
            # 检查是否已请求停止处理
            if user in self.stop_events and self.stop_events[user].is_set():
                print(f"[{self.__class__.__name__}] 用户 {user} 已请求停止处理，不再输出数据")
                return

            # 如果输出为None,且没有后续模块,标记任务完成
            if response_data is None and self.next_model is None:
                print(f"[{self.__class__.__name__}] 用户 {user} 已处理完成，不再输出数据")
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
                return

            if response_data is None:
                print(f"[{self.__class__.__name__}] 下一个模块是 [{self.next_model.__class__.__name__}] ")

            # 保存输出并发送到Pipeline
            self.output = response_data
            
            # 检查用户是否已断开连接
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )
            
            if future.result(timeout=1.0):
                print(f"[{self.__class__.__name__}] 用户 {user} 已断开连接，停止处理")
                # 设置停止事件
                if user in self.stop_events:
                    self.stop_events[user].set()
                return


            # 如果输出为None且没有后续模块,把终止信号None输出到PipeLine
            if response_data is None and self.next_model is None:
                # 用户仍然连接，发送数据
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.add_chunk(user, response_data),
                    self.pipeline.main_loop
                )
            elif response_data is not None:
                # 用户仍然连接，发送数据
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.add_chunk(user, response_data),
                    self.pipeline.main_loop
                )


        except Exception as e:
            # 处理错误
            error_chunk = f"ERROR: {str(e)}"
            print(f"[{self.__class__.__name__}] 输出错误: {error_chunk}")
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
                print(f"[{self.__class__.__name__}] 无法发送错误消息: {str(inner_e)}")

    async def _check_if_disconnected(self, user: str) -> bool:
        """检查用户是否已断开连接"""
        if not hasattr(self.pipeline, 'disconnect_events'):
            return False
            
        # 检查断开连接事件
        return user in self.pipeline.disconnect_events and self.pipeline.disconnect_events[user].is_set()

    @abstractmethod
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> Any:
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
                    print(f"[{self.__class__.__name__}] 用户 {user} 处理超时，强制终止")
                    if user in self.stop_events:
                        self.stop_events[user].set()
            
            # 启动定时器线程
            timer = threading.Timer(self.thread_timeout, check_timeout)
            timer.daemon = True
            timer.start()
            
            # 执行任务
            self.Thread_Task(streamly, user, input_data, self.Response_output,self.Next_output)
            
        except Exception as e:
            print(f"[{self.__class__.__name__}] {self.__class__.__name__} 线程执行错误: {str(e)}")
            try:
                self.Response_output(streamly, user, f"[ERROR]: {str(e)}")
            except:
                print(f"[{self.__class__.__name__}] 无法发送错误消息给用户 {user}")
        finally:
            # 清理资源
            if not streamly or user in self.stop_events and self.stop_events[user].is_set():
                self._cleanup(user)
            # 取消定时器
            timer.cancel()

    def _create_thread(self, streamly: bool, user: str, input_data: Any) -> None:
        """创建新线程处理用户请求"""
        # 检查用户是否已断开连接
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )
            
            if future.result(timeout=1.0):
                print(f"[{self.__class__.__name__}] 用户 {user} 已断开连接，不创建新线程")
                return
        except Exception as e:
            print(f"[{self.__class__.__name__}] 检查用户连接状态时出错: {str(e)}")

        # 如果是流式处理，检查是否已有活跃线程
        if streamly and user in self.streaming_status and self.streaming_status[user]:
            print(f"[{self.__class__.__name__}] 用户 {user} 的流式处理正在进行中，跳过新线程创建")
            return

        # 创建停止事件和线程
        self.stop_events[user] = threading.Event()
        thread = threading.Thread(
            target=self._thread_wrapper,
            args=(streamly, user, input_data),
            daemon=True
        )

        self.user_threads[user] = thread
        if streamly:
            self.streaming_status[user] = True
        thread.start()
        print(f"[{self.__class__.__name__}] 为用户 {user} 创建新线程: {thread.ident}")

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
                print(f"[{self.__class__.__name__}] 终止用户 {user} 的线程 {thread_id}")
            del self.user_threads[user]
            
        # 清理流式状态
        if user in self.streaming_status:
            del self.streaming_status[user]
            
        # 延迟删除停止事件，确保其他地方可以检查它
        if user in self.stop_events:
            del self.stop_events[user]

    def Destroy(self) -> None:
        """销毁模块，清理所有资源"""
        print(f"[{self.__class__.__name__}] 销毁模块 {self.__class__.__name__}")
        # 获取所有用户的副本，避免在迭代过程中修改字典
        users = list(self.user_threads.keys())
        for user in users:
            self._cleanup(user)
        self.user_threads.clear()
        self.stop_events.clear()
        self.streaming_status.clear()