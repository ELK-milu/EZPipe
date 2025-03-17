import asyncio
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Dict, Any
import queue
import threading

if TYPE_CHECKING:
    from modules.PipeLine.BasePipeLine import PipeLine

class BaseModule(ABC):
    def __init__(self):
        self.stop_events: Dict[str, threading.Event] = {}  # 新增停止事件字典
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


            #TODO: 这段代码是有问题的，目前不知道怎么返回chunk块，所以用字符串组合来表示
            chunk = str(output_data)
            self.output += chunk

            asyncio.run_coroutine_threadsafe(
                self.pipeline.add_chunk(user, output_data),
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

    def _thread_wrapper(self, streamly: bool, user: str, input_data: Any):
        try:
            self.Thread_Task(streamly, user, input_data, self.Output)
        finally:
            self._cleanup(user)

    def _create_thread(self, streamly: bool, user: str, input_data: Any):
        if user in self.user_threads:
            self._cleanup(user)  # 创建新线程前先清理

        self.stop_events[user] = threading.Event()  # 创建新事件
        thread = threading.Thread(
            target=self._thread_wrapper,
            args=(streamly, user, input_data))

        self.user_queues[user] = queue.Queue()
        # 创建线程并启动
        #thread = threading.Thread(target=self.Thread_Task, args=(streamly, user, input_data, self.Output))
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
        """增强型清理，添加存在性检查"""
        if user in self.stop_events:
            self.stop_events[user].set()  # 触发停止标志
        # 清理线程
        if user in self.user_threads:
            thread = self.user_threads[user]
            if thread.is_alive():
                if thread.is_alive():
                    print(f"强制终止用户{user}的线程")
            del self.user_threads[user]  # 先删除线程记录
        # 清理队列
        if user in self.user_queues:
            while not self.user_queues[user].empty():
                try:
                    self.user_queues[user].get_nowait()
                except queue.Empty:
                    break
            del self.user_queues[user]
        # 清理停止标志
        if user in self.stop_events:
            del self.stop_events[user]


    def Destory(self):
        del self.user_threads
        del self.user_queues