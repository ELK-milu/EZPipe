import asyncio
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Dict, Any
import queue
import threading
import time
import logging
from datetime import datetime

import requests
from fastapi import APIRouter
from utils.logger import get_logger

if TYPE_CHECKING:
    from modules.PipeLine.BasePipeLine import PipeLine
    from modules.PipeLineAPI.BasePipeAPI import API_Service

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
        self.logger = get_logger(self.__class__.__name__)
        self.RegisterRoutes()


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

            # 如果下一个模块未开启处理线程，则开启处理线程
            if user not in self.next_model.user_threads:
                # 使用asyncio.run_coroutine_threadsafe来在事件循环中执行异步方法
                asyncio.run_coroutine_threadsafe(
                    self.next_model.GetService(streamly, user, output),
                    self.pipeline.main_loop
                )

            if user not in self.next_model.user_InputQueue:
                self.next_model.user_InputQueue[user] = queue.Queue()
            
            # 直接添加数据到队列，不创建新线程
            self.next_model.user_InputQueue[user].put(output)
            self.logger.info(f"[{self.__class__.__name__}] 添加数据{str(output)}到 {self.next_model.__class__.__name__} 输入队列")

    def Response_output(self, streamly: bool, user: str, response_data: Any) -> None:
        """将模块输出发送到Pipeline并传递给下一个模块"""
        self.logger.info(f"[{self.__class__.__name__}] 用户 {user} 处理完成，输出数据")
        try:
            # 检查是否已请求停止处理
            if user in self.stop_events and self.stop_events[user].is_set():
                self.logger.info(f"[{self.__class__.__name__}] 用户 {user} 已请求停止处理，不再输出数据")
                return

            # 如果输出为None,且没有后续模块,且当前队列里没有待处理的内容,标记任务完成
            if response_data == self.ENDSIGN and self.next_model is None:
                self.logger.info(f"[{self.__class__.__name__}] 用户 {user} 已处理完成，不再输出数据")
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
                return

            if response_data == self.ENDSIGN and self.next_model is not None:
                self.logger.info(f"[{self.__class__.__name__}]执行结束 下一个模块是 [{self.next_model.__class__.__name__}] ")

            # 保存输出并发送到Pipeline
            self.output = response_data
            
            # 检查用户是否已断开连接
            future = asyncio.run_coroutine_threadsafe(
                self._check_if_disconnected(user),
                self.pipeline.main_loop
            )
            
            if future.result(timeout=1.0):
                self.logger.info(f"[{self.__class__.__name__}] 用户 {user} 已断开连接，停止处理")
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
            self.logger.error(f"[{self.__class__.__name__}] 输出错误: {error_chunk}")
            try:
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.add_chunk(user, error_chunk),
                    self.pipeline.main_loop
                )
                self.logger.error("pipeline出现错误,强行终止")
                asyncio.run_coroutine_threadsafe(
                    self.pipeline.mark_complete(user),
                    self.pipeline.main_loop
                )
            except Exception as inner_e:
                self.logger.error(f"[{self.__class__.__name__}] 无法发送错误消息: {str(inner_e)}")

    async def _check_if_disconnected(self, user: str) -> bool:
        """检查用户是否已断开连接"""
        if not hasattr(self.pipeline, 'disconnect_events'):
            return False
            
        # 检查断开连接事件
        return user in self.pipeline.disconnect_events and self.pipeline.disconnect_events[user].is_set()



    async def GetService(self, streamly: bool, user: str, input_data: Any) -> None:
        """
        启动服务，为指定用户创建处理线程
        
        Args:
            streamly: 是否流式输出
            user: 用户标识
            input_data: 输入数据
        """
        try:
            # 确保用户有对应的停止事件
            if user not in self.stop_events:
                self.stop_events[user] = threading.Event()
            
            # 确保用户有对应的输入队列
            if user not in self.user_InputQueue:
                self.user_InputQueue[user] = queue.Queue()
            
            # 如果有输入数据，添加到队列
            if input_data is not None:
                self.user_InputQueue[user].put(input_data)
                print(f"[{self.__class__.__name__}] 添加初始数据到用户 {user} 的输入队列")
            
            # 创建并启动处理线程
            if user not in self.user_threads or not self.user_threads[user].is_alive():
                self.user_threads[user] = threading.Thread(
                    target=self._create_thread,
                    args=(streamly, user, None),
                    daemon=True
                )
                self.user_threads[user].start()
                print(f"[{self.__class__.__name__}] 模块启动线程服务 :{user} {self.user_threads[user].ident}")

            # 预初始化下一个模块的处理线程
            if self.next_model is not None:
                await self.next_model.GetService(streamly, user, None)


        except Exception as e:
            print(f"[{self.__class__.__name__}] 启动服务时出错: {str(e)}")
            # 确保在出错时清理资源
            await self._cleanup(user)

    def _create_thread(self, streamly: bool, user: str, input_data: Any) -> None:
        """
        创建并运行处理线程，持续从队列中获取数据并处理，直到收到停止信号
        
        Args:
            streamly: 是否流式输出
            user: 用户标识
            input_data: 初始输入数据，如果为None则从队列获取
        """
        # 确保用户有对应的停止事件
        if user not in self.stop_events:
            self.stop_events[user] = threading.Event()
        
        # 确保用户有对应的输入队列
        if user not in self.user_InputQueue:
            self.user_InputQueue[user] = queue.Queue()
        
        # 如果有初始输入数据，直接处理
        if input_data is not None:
            try:
                start_time = time.time()
                self.Thread_Task(streamly, user, input_data,self.Response_output, self.Next_output)
                end_time = time.time()
                self.logger.info(f"[{self.__class__.__name__}] 处理初始输入数据完成，耗时: {end_time - start_time:.3f}秒")
            except Exception as e:
                self.logger.error(f"[{self.__class__.__name__}] 处理初始输入数据时出错: {str(e)}")

        # 持续处理队列中的数据，直到收到停止信号
        timeout_counter = 0  # 新增超时计数器
        max_continuous_timeout = 10  # 最大连续超时次数（秒），可调整或作为配置参数

        while not self.stop_events[user].is_set():
            try:
                # 从队列中获取数据，设置超时以便定期检查停止信号
                try:
                    data = self.user_InputQueue[user].get(timeout=1)
                    self.logger.info(f"[{self.__class__.__name__}] 从队列获取数据: {str(data)[:20]}")

                    # 处理获取到的数据
                    start_time = time.time()
                    self.Thread_Task(streamly, user, data, self.Response_output, self.Next_output)
                    end_time = time.time()
                    self.logger.info(f"[{self.__class__.__name__}] 处理队列数据完成，耗时: {end_time - start_time:.3f}秒")

                    timeout_counter = 0  # 成功获取数据后重置计数器

                except queue.Empty:
                    # 队列为空，增加超时计数
                    timeout_counter += 1
                    self.logger.warning(f"[{self.__class__.__name__}] 连续空队列超时次数: {timeout_counter}/{max_continuous_timeout}")

                    # 达到最大连续超时次数则退出循环
                    if timeout_counter >= max_continuous_timeout:
                        self.logger.info(f"[{self.__class__.__name__}] 连续超时{max_continuous_timeout}次，退出处理循环")
                        break
                    continue

            except Exception as e:
                self.logger.error(f"[{self.__class__.__name__}] 处理队列数据时出错: {str(e)}")
                # 出错后短暂等待，避免CPU占用过高
                time.sleep(0.1)
                timeout_counter = 0  # 发生异常时也重置计数器

        self.logger.info(f"[{self.__class__.__name__}] 用户 {user} 的处理线程已停止")
        self.Response_output(streamly, user, self.ENDSIGN)
        self.Next_output(streamly, user, self.ENDSIGN)

    def _cleanup_thread(self, user: str) -> None:
        """清理线程资源，但不清理用户队列"""
        # 清理线程
        if user in self.user_threads:
            thread = self.user_threads[user]
            thread_id = thread.ident
            if thread.is_alive():
                print(f"[{self.__class__.__name__}] 终止用户 {user} 的线程 {thread_id}")
            del self.user_threads[user]


    def GetOutPut(self, user: str) -> Any:
        """获取最后一次输出"""
        return self.output

    def _cleanup(self, user: str) -> None:
        """
        清理用户相关资源
        
        Args:
            user: 用户标识
        """
        print(f"[{self.__class__.__name__}] 开始清理用户 {user} 的资源")
        
        # 设置停止事件，通知处理线程停止
        if user in self.stop_events:
            self.stop_events[user].set()
            print(f"[{self.__class__.__name__}] 已设置用户 {user} 的停止事件")
        
        # 等待线程结束（设置超时避免无限等待）
        if user in self.user_threads and self.user_threads[user].is_alive():
            thread = self.user_threads[user]
            thread_id = thread.ident
            print(f"[{self.__class__.__name__}] 等待用户 {user} 的线程 {thread_id} 结束")
            thread.join(timeout=5.0)  # 最多等待5秒
            
            if thread.is_alive():
                print(f"[{self.__class__.__name__}] 用户 {user} 的线程 {thread_id} 未能正常结束")
        
        # 清理线程资源
        if user in self.user_threads:
            del self.user_threads[user]
            print(f"[{self.__class__.__name__}] 已删除用户 {user} 的线程资源")
        
        # 清理队列资源
        if user in self.user_InputQueue:
            # 清空队列中的所有数据
            while not self.user_InputQueue[user].empty():
                try:
                    self.user_InputQueue[user].get_nowait()
                except queue.Empty:
                    break
            del self.user_InputQueue[user]
            print(f"[{self.__class__.__name__}] 已删除用户 {user} 的队列资源")
        
        # 清理流式状态
        if user in self.streaming_status:
            del self.streaming_status[user]
            print(f"[{self.__class__.__name__}] 已删除用户 {user} 的流式状态")
        
        # 延迟删除停止事件，确保其他地方可以检查它
        if user in self.stop_events:
            del self.stop_events[user]
            print(f"[{self.__class__.__name__}] 已删除用户 {user} 的停止事件")
        
        print(f"[{self.__class__.__name__}] 用户 {user} 的资源清理完成")

    def Destroy(self) -> None:
        """
        销毁模块，清理所有资源
        """
        print(f"[{self.__class__.__name__}] 开始销毁模块")
        
        # 获取所有用户的副本，避免在迭代过程中修改字典
        users = list(self.user_threads.keys())
        
        # 清理每个用户的资源
        for user in users:
            self._cleanup(user)
        
        # 清理会话资源
        if self.session:
            self.session.close()
            print(f"[{self.__class__.__name__}] 已关闭会话")
        
        # 清空所有字典
        self.user_threads.clear()
        self.stop_events.clear()
        self.streaming_status.clear()
        self.user_InputQueue.clear()
        
        print(f"[{self.__class__.__name__}] 模块销毁完成")