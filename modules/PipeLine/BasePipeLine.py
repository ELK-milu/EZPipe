import asyncio
import queue
import threading
import time
from logging import Logger
from typing import List, Type, Any, Dict, Optional, AsyncGenerator, Set

from modules.Modules.BaseModule import BaseModule

class PipeLine:
    def __init__(self, modules: List[Type[BaseModule]]):
        # 初始化模块实例
        self.modules = [m() for m in modules]
        self._link_instances()
        
        # 用户队列和状态管理
        self.user_queues: Dict[str, asyncio.Queue] = {}  # 异步队列
        self.active_users: Dict[str, bool] = {}
        self.lock = asyncio.Lock()
        self.main_loop = asyncio.get_event_loop()
        self.disconnect_events: Dict[str, asyncio.Event] = {}  # 用户断开连接事件
        self.validated:bool = False    #当前pipe是否可用的指示位
        self.ENDSIGN = None
        self.logger = None
        # 设置模块的pipeline引用
        for module in self.modules:
            module.pipeline = self
            
        # 任务并发控制
        self.active_tasks = threading.BoundedSemaphore(5)

        self.validated:bool = False
        print(self.Validate())

    def _link_instances(self) -> None:
        """链接模块实例"""
        for i in range(len(self.modules) - 1):
            self.modules[i].next_model = self.modules[i + 1]


    def HeartBeat(self,user:str):
        print("管线心跳")
        for module in self.modules:
            module.HeartBeat(user)

    def StartUp(self):
        print("管线初始化")
        for module in self.modules:
            module.logger = self.logger
            module.StartUp()

    async def add_chunk(self, user: str, chunk: Any) -> None:
        """添加数据块到用户队列"""
        async with self.lock:
            # 如果用户已断开，不再处理数据
            if user in self.disconnect_events and self.disconnect_events[user].is_set():
                print(f"[Pipeline] 用户 {user} 已断开连接，停止添加数据")
                return
                
            if user not in self.user_queues:
                self.user_queues[user] = asyncio.Queue()
                self.active_users[user] = True
                self.disconnect_events[user] = asyncio.Event()
            
            # 数据正常处理
            await self.user_queues[user].put(chunk)
            print(f"[Pipeline] 为用户 {user} at {time.time()} 添加数据块: {type(chunk)} {len(str(chunk))} bytes")

    async def mark_complete(self, user: str) -> None:
        """标记用户任务完成"""
        async with self.lock:
            print(f"[Pipeline] 标记用户 {user} 的任务完成")
            self.active_users[user] = False
            if user in self.user_queues:
                await self.add_chunk(user,self.ENDSIGN)  # 发送结束信号

    async def mark_disconnected(self, user: str) -> None:
        """标记用户已断开连接"""
        async with self.lock:
            print(f"[Pipeline] 标记用户 {user} 已断开连接")
            if user in self.disconnect_events:
                self.disconnect_events[user].set()
            self.active_users[user] = False

    async def ResponseOutput(self, user: str) -> AsyncGenerator[Any, None]:
        """流式返回用户数据"""
        try:
            # 确保用户队列存在
            async with self.lock:
                if user not in self.user_queues:
                    self.user_queues[user] = asyncio.Queue()
                    self.active_users[user] = True
                    self.disconnect_events[user] = asyncio.Event()
                    print(f"[Response] 为用户 {user} 创建新队列")
                
                user_queue = self.user_queues[user]
                
                # 重置断开连接事件
                if user in self.disconnect_events:
                    self.disconnect_events[user].clear()
            
            # 持续从队列获取数据
            while True:
                try:
                    # 检查用户是否已断开连接
                    if user in self.disconnect_events and self.disconnect_events[user].is_set():
                        print(f"[Response] 用户 {user} 已标记为断开连接，停止响应")
                        break
                        
                    # 使用超时避免无限等待
                    chunk = await asyncio.wait_for(user_queue.get(), timeout=2)

                    # None表示结束信号
                    if chunk == self.ENDSIGN:
                        print(f"[Response] 接收到终止信号,用户 {user} 处理完成")
                        break

                    yield chunk
                    print(f"[Response] 发送给用户 {user} 数据块: {type(chunk)}")
                    
                except asyncio.TimeoutError:
                    # 检查用户是否仍然活跃
                    async with self.lock:
                        # 检查断开连接标记
                        if user in self.disconnect_events and self.disconnect_events[user].is_set():
                            print(f"[Response] 用户 {user} 已标记为断开连接，停止响应")
                            break
                            
                        # 检查活跃状态
                        if user not in self.active_users or not self.active_users[user]:
                            print(f"[Response] 用户 {user} 不再活跃，结束响应")
                            break
                        # 否则继续等待
                        
                except Exception as e:
                    print(f"[Response] 获取数据错误: {str(e)}")
                    break
        finally:
            # 响应结束时清理资源并标记用户断开
            await self.mark_disconnected(user)
            # 响应结束时清理资源
            await self._cleanup_user(user)

    def Validate(self) -> str:
        """验证Pipeline配置"""
        status = []
        try:
            self._validate_pipeline()
            status.append("✅ Pipeline验证通过")
            self.validated = True
        except Exception as e:
            status.append(f"❌ 验证失败: {str(e)}")
            self.validated = False

        pipe_structure = " -> ".join(
            [f"{type(inst).__name__}" for inst in self.modules]
        )
        status.append(f"当前Pipeline: {pipe_structure}")

        type_details = []
        for inst in self.modules:
            sig = inst.Thread_Task.__annotations__
            type_details.append(
                f"{type(inst).__name__} "
                f"(输入: {sig['input_data']}, 输出: {sig['return']})"
            )
        status.append("类型详情:\n" + "\n".join(type_details))
        status.append("#################################################")
        return "\n".join(status)

    def _validate_pipeline(self) -> None:
        """验证Pipeline的类型兼容性"""
        if not self.modules:
            raise ValueError("Pipeline不能为空")
            
        for i in range(len(self.modules) - 1):
            curr = self.modules[i]
            next_mod = self.modules[i + 1]
            curr_output = curr.Thread_Task.__annotations__['return']
            next_input = next_mod.Thread_Task.__annotations__['input_data']
            
            if curr_output != next_input:
                raise TypeError(
                    f"类型不匹配: {type(curr).__name__} 输出 {curr_output} "
                    f"但 {type(next_mod).__name__} 期望 {next_input}"
                )

    @classmethod
    def create_pipeline(cls, *modules: Type[BaseModule]) -> 'PipeLine':
        """创建新的Pipeline实例"""
        return cls(list(modules))

    async def GetService(self, streamly: bool, user: str, input_data: Any,logger:Logger) -> None:

        self.logger = logger
        """启动Pipeline服务处理"""
        with self.active_tasks:
            # 直接等待清理完成
            await self._force_cleanup_user(user)

            # 标记用户为活跃状态
            async with self.lock:
                self.active_users[user] = True
                if user in self.disconnect_events:
                    self.disconnect_events[user].clear()
                else:
                    self.disconnect_events[user] = asyncio.Event()

            # 启动第一个模块处理
            if not self.modules:
                raise ValueError("未配置Pipeline")
            # 启动处理
            await self.modules[0].GetService(streamly, user, input_data)

    async def Output(self, user: str) -> Any:
        """获取用户的最终输出"""
        return self.modules[-1].GetOutPut(user)

    async def _force_cleanup_user(self, user: str) -> None:
        """强制清理用户资源，用于新请求前终止旧请求"""
        print(f"[Pipeline] 强制清理用户 {user} 的资源")
        
        # 首先标记用户断开
        await self.mark_disconnected(user)
        
        # 清理所有模块中的用户资源
        for module in self.modules:
            try:
                if hasattr(module, '_cleanup'):
                    module._cleanup(user)
            except Exception as e:
                print(f"[Pipeline] 模块 {type(module).__name__} 强制清理错误: {str(e)}")
        
        # 清理Pipeline中的用户资源
        async with self.lock:
            if user in self.user_queues:
                # 清空队列
                while not self.user_queues[user].empty():
                    try:
                        await self.user_queues[user].get_nowait()
                    except asyncio.QueueEmpty:
                        break
                del self.user_queues[user]
                
            if user in self.active_users:
                del self.active_users[user]
                
            # 保持断开连接事件的标记
            if user in self.disconnect_events:
                self.disconnect_events[user].set()
        
        # 等待一小段时间确保清理完成
        await asyncio.sleep(0.2)

    async def _cleanup_user(self, user: str) -> None:
        """清理用户资源"""
        print(f"[Pipeline] 清理用户 {user} 的资源")
        
        # 清理模块中的用户资源
        for module in self.modules:
            try:
                if hasattr(module, '_cleanup'):
                    module._cleanup(user)
            except KeyError as e:
                print(f"[Pipeline] 模块 {type(module).__name__} 清理时键错误: {str(e)}")
            except Exception as e:
                print(f"[Pipeline] 模块清理错误: {str(e)}")

        # 清理Pipeline中的用户资源
        async with self.lock:
            if user in self.user_queues:
                del self.user_queues[user]
            if user in self.active_users:
                del self.active_users[user]
            # 保持断开连接事件以备将来使用
            # if user in self.disconnect_events:
            #     del self.disconnect_events[user]

    def Destroy(self) -> None:
        """销毁Pipeline及所有模块"""
        for module in self.modules:
            module.Destroy()

    def WaitForCompletion(self, user: str, timeout: float = 30) -> None:
        """等待用户任务完成 (不推荐使用，可能导致阻塞)"""
        for module in self.modules:
            if user in module.user_threads:
                module.user_threads[user].join(timeout)
                if module.user_threads[user].is_alive():
                    raise TimeoutError(f"模块 {type(module).__name__} 超时")