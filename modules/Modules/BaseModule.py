from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional, List
import threading
import queue


class BaseModule(ABC):
    """模块基类"""
    def __init__(self):
        self.next_model: Optional[BaseModule] = None  # 指向实例而非类
        self.user_queues: Dict[str, queue.Queue] = {}  # 实例级队列
        self.user_threads: Dict[str, threading.Thread] = {}  # 实例级线程管理
        self.output:Any = None

    @abstractmethod
    def process(self,streamly: bool, user: str, input_data: Any) -> Any:
        pass

    def GetService(cls, streamly: bool, user: str, input_data: Any) -> None:
        cls._create_thread(streamly, user, input_data)

    def _create_thread(self, streamly: bool, user: str, input_data: Any):
        if user in self.user_threads:
            raise RuntimeError(f"User {user} already has active request")

        self.user_queues[user] = queue.Queue()

        def _thread_task():
            try:
                result = self.process(streamly,user, input_data)
                if self.next_model:
                    self.next_model._create_thread(streamly, user, result)
                self.user_queues[user].put(result)
            finally:
                pass

        thread = threading.Thread(target=_thread_task)
        self.user_threads[user] = thread
        thread.start()

    # 需要重写的方法，重新封装成Response响应后再返回
    def GetOutPut(self, user: str, timeout: float = 30.0) -> Any:
        try:
            if self.output is None:
                self.output = self.user_queues[user].get(timeout=timeout)
            return self.output
        except queue.Empty:
            raise TimeoutError(f"Timeout waiting for output from {self.__class__.__name__}")

    def _cleanup(self, user: str):
        del self.user_threads[user]
        del self.user_queues[user]