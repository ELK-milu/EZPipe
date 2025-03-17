import asyncio
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Dict, Any
import queue
import threading

if TYPE_CHECKING:
    from modules.PipeLine.BasePipeLine import PipeLine

class BaseModule(ABC):
    def __init__(self):
        self.next_model: Optional["BaseModule"] = None
        self.pipeline: Optional["PipeLine"] = None
        self.user_queues: Dict[str, queue.Queue] = {}  # 实例级队列
        self.user_threads: Dict[str, threading.Thread] = {}
        self.mark_complete = False
        self.output:str = ""

    def Output(self, streamly: bool, user: str, output_data: Any):
        """处理输出并传递到下一环节"""
        try:
            print(f"[Output] User {user} received data: {type(output_data)}")
            if output_data is None:  # 结束标记
                print(f"[Output] Sending completion signal for {user}")
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
                return

            chunk = str(output_data)
            self.output += chunk

            asyncio.run_coroutine_threadsafe(
                self.pipeline.add_chunk(user, chunk),
                self.pipeline.main_loop
            )

            if self.next_model:
                self.next_model._create_thread(streamly, user, output_data)

        except Exception as e:
            error_chunk = f"ERROR: {str(e)}"
            asyncio.run_coroutine_threadsafe(
                self.pipeline.add_chunk(user, error_chunk),
                self.pipeline.main_loop
            )
            asyncio.run_coroutine_threadsafe(
                self.pipeline.mark_complete(user),
                self.pipeline.main_loop
            )
    # 用于重写数据自定义处理和整合
    @abstractmethod
    def Thread_Task(self, streamly: bool, user: str, input_data: Any,invoke_func) -> Any:
        # 在重写方法的时候可以自定义回调触发的时机
        invoke_func(streamly,user,input_data)
        pass

    def GetService(self, streamly: bool, user: str, input_data: Any) -> None:
        self._create_thread(streamly, user, input_data)

    def _create_thread(self, streamly: bool, user: str, input_data: Any):
        if user in self.user_threads:
            raise RuntimeError(f"User {user} already has active request")

        self.user_queues[user] = queue.Queue()
        # 创建线程并启动
        thread = threading.Thread(target=self.Thread_Task, args=(streamly, user, input_data, self.Output))
        self.user_threads[user] = thread
        thread.start()

    def GetOutPut(self, user: str, timeout: float = 30.0) -> Any:
        try:
            if self.output is None:
                self.output = self.user_queues[user].get(timeout=timeout)
            return self.output
        except queue.Empty:
            raise TimeoutError(f"Timeout waiting for output from {self.__class__.__name__}")

    def _cleanup(self, user: str):
        # 终止正在运行的线程
        if user in self.user_threads:
            thread = self.user_threads[user]
            if thread.is_alive():
                # 安全终止线程
                thread.join(timeout=0.5)  # 等待0.5秒
                if thread.is_alive():
                    print(f"强制终止用户{user}的线程")
                    # 这里可以添加更安全的终止逻辑
            del self.user_threads[user]

        # 清空队列
        if user in self.user_queues:
            while not self.user_queues[user].empty():
                try:
                    self.user_queues[user].get_nowait()
                except queue.Empty:
                    break
            del self.user_queues[user]

    def Destory(self):
        del self.user_threads
        del self.user_queues