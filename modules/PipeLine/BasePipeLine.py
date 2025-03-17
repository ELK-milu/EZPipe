import asyncio
import os
import queue
import threading
from typing import List, Type, Any, Dict

from modules.Modules.BaseModule import BaseModule
# PipeLine只应处理调用服务的API模块，不要包含需要长期保持连接的模块，做到即用即拿
class PipeLine:
    def __init__(self, modules: List[Type[BaseModule]]):
        self.modules = [m() for m in modules]
        self._link_instances()
        self.user_queues: Dict[str, queue.Queue] = {}  # 用户级输出队列
        self.active_users: Dict[str, bool] = {}        # 用户处理状态
        self.lock = asyncio.Lock()  # 异步锁
        self.main_loop = asyncio.get_event_loop()  # 保存主线程事件循环
        # 为所有模块注入pipeline引用
        for module in self.modules:
            module.pipeline = self

        self.active_tasks = threading.BoundedSemaphore(5)  # 限制并发请求数

        print(self.Validate())

    def _link_instances(self):
        """连接实例链"""
        for i in range(len(self.modules)-1):
            self.modules[i].next_model = self.modules[i+1]

    async def add_chunk(self, user: str, chunk: Any):
        """向指定用户的队列添加数据块（异步线程安全）"""
        async with self.lock:
            if user not in self.user_queues:
                self.user_queues[user] = queue.Queue()
                self.active_users[user] = True
            # 使用线程池执行同步队列操作
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.user_queues[user].put(chunk)
            )

    async def mark_complete(self, user: str):
        """标记用户处理完成（异步线程安全）"""
        async with self.lock:
            self.active_users[user] = False
            if user in self.user_queues:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.user_queues[user].put(None)
                )

    async def ResponseOutput(self, user: str):
        print(f"[Response] Starting output stream for {user}")
        try:
            while True:
                async with self.lock:
                    q = self.user_queues.get(user)
                    active = self.active_users.get(user, None)

                if not q:
                    if active is None:
                        print(f"[Response] 等待{user}服务开启")
                    elif active:
                        print(f"[Response] {user}服务开启中,等待流式返回")
                    elif not active:
                        print(f"[Response] No queue and inactive for {user}")
                        break

                if q:
                    try:
                        chunk = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: q.get(timeout=0.1)  # 增加短暂等待
                        )
                        if chunk is None:
                            break
                        yield chunk
                    except queue.Empty:
                        if not active:
                            print(f"[Response] Queue empty and inactive for {user}")
                            break
                    except Exception as e:
                        print(f"[Response] Error: {str(e)}")
                        break
                else:
                    await asyncio.sleep(0.1)
        finally:
            pass

    def _cleanup_user(self, user: str):
        if user in self.user_queues:
            del self.user_queues[user]
        if user in self.active_users:
            del self.active_users[user]
    def _link_instances(self):
        """连接实例链"""
        for i in range(len(self.modules)-1):
            self.modules[i].next_model = self.modules[i+1]

    def _validate_pipeline(self):
        """内部验证方法"""
        # 1. 检查空管道
        if not self.modules:
            raise ValueError("Pipeline cannot be empty")

        # 2. 检查类型连续性
        for i in range(len(self.modules) - 1):
            curr = self.modules[i]
            next_mod = self.modules[i + 1]

            curr_output = curr.Thread_Task.__annotations__['return']
            next_input = next_mod.Thread_Task.__annotations__['input_data']

            if curr_output != next_input:
                raise TypeError(
                    f"Type mismatch: {type(curr).__name__} outputs {curr_output} "
                    f"but {type(next_mod).__name__} expects {next_input}"
                )

    def Validate(self) -> str:
        """验证并返回管道状态"""
        status = []

        # 基础验证
        try:
            self._validate_pipeline()
            status.append("✅ Pipeline validation passed")
        except Exception as e:
            status.append(f"❌ Validation failed: {str(e)}")

        # 管线结构展示
        pipe_structure = " -> ".join(
            [f"{type(inst).__name__}" for inst in self.modules]
        )
        status.append(f"Current pipeline: {pipe_structure}")

        # 详细类型信息
        type_details = []
        for inst in self.modules:
            sig = inst.Thread_Task.__annotations__
            type_details.append(
                f"{type(inst).__name__} "
                f"(in: {sig['input_data']}, out: {sig['return']})"
            )
        status.append("Type details:\n" + "\n".join(type_details))
        status.append("#################################################")
        return "\n".join(status)

    @classmethod
    def create_pipeline(cls, *modules: Type[BaseModule]) -> 'PipeLine':
        """类方法创建管道实例"""
        return cls(list(modules))  # 将可变参数转换为列表

    def GetService(self, streamly: bool, user: str, input_data: Any):
        with self.active_tasks:
            print("[PipeLine] Start PipeLine Service")
            """带中断机制的入口"""
            # 延迟确保清理完成
            def delayed_start():
                import time
                time.sleep(0.1)  # 等待100ms确保清理完成
                if not self.modules:
                    raise ValueError("Unconfigured pipeline")
                self.active_users[user] = True
                self.modules[0].GetService(streamly, user, input_data)

            # 在新线程中启动
            threading.Thread(target=delayed_start).start()
            self.WaitForCompletion(user)

    async def Output(self, user: str) -> Any:
        """统一输出入口（修复版本）"""
        return self.modules[-1].GetOutPut(user)

    def _cleanup(self, user: str):
        """增强型资源清理"""
        print(f"开始清理用户{user}的资源")
        # 1. 终止所有模块的线程
        for module in self.modules:
            module._cleanup(user)

        # 2. 清理管道级队列
        async def async_cleanup():
            async with self.lock:
                if user in self.user_queues:
                    while not self.user_queues[user].empty():
                        try:
                            self.user_queues[user].get_nowait()
                        except queue.Empty:
                            break
                    del self.user_queues[user]
                if user in self.active_users:
                    del self.active_users[user]

        # 在事件循环中执行清理
        asyncio.run_coroutine_threadsafe(async_cleanup(), self.main_loop)

    def Destroy(self):
        """统一销毁资源"""
        for module in self.modules:
            module.Destory()

    def WaitForCompletion(self, user: str, timeout: float = 30):
        """等待指定用户的所有处理线程完成"""
        for module in self.modules:
            if user in module.user_threads:
                module.user_threads[user].join(timeout)
                if module.user_threads[user].is_alive():
                    raise TimeoutError(f"Module {type(module).__name__} timed out")