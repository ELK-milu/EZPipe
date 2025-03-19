import asyncio
import json
import threading
import logging
from asyncio import AbstractEventLoop, Task
from typing import Optional, Dict
import time

from ..BaseModule import BaseModule
from .FunASR_WS_Test import FunASRClient

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FunASR_ASR_Module')

class FunASR_ASR_Module(BaseModule):
    """语音识别模块（输入类型：bytes，输出类型：str）"""
    def __init__(self):
        super().__init__()
        logger.info("初始化 FunASR_ASR_Module")
        self.funasr_client : Dict[str, FunASRClient] = {}
        self.last_activity : Dict[str, float] = {}  # 记录用户最后活动时间
        self.activity_timeout = 30  # 30秒无活动则清理资源
        self.loops : Dict[str, AbstractEventLoop] = {}  # 存储每个用户的事件循环
        logger.debug("FunASR 客户端字典已初始化")

    def _check_client_timeout(self, user: str):
        """检查客户端是否超时"""
        current_time = time.time()
        if user in self.last_activity:
            if current_time - self.last_activity[user] > self.activity_timeout:
                logger.info(f"用户 {user} 的连接已超时，清理资源")
                self._cleanup(user)
                return True
        return False

    def _get_or_create_loop(self, user: str) -> AbstractEventLoop:
        """获取或创建用户的事件循环"""
        if user not in self.loops:
            self.loops[user] = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loops[user])
        return self.loops[user]

    def Thread_Task(self, streamly: bool, user: str, input_data: bytes, response_func, next_func) -> str:
        """
        处理语音到文本的转换任务
        Args:
            streamly: 是否流式输出
            user: 用户标识
            input_data: 输入音频数据
            response_func: 流式输出回调函数
            next_func: 下个模块的回调
        Returns:
            str: 识别文本
        """
        logger.info(f"开始处理用户 {user} 的音频数据")
        logger.debug(f"输入参数: streamly={streamly}, user={user}, input_data长度={len(input_data) if input_data else 0}")

        try:
            # 更新最后活动时间
            self.last_activity[user] = time.time()

            # 检查客户端是否超时
            if self._check_client_timeout(user):
                return None

            # 获取用户的事件循环
            loop = self._get_or_create_loop(user)

            # 获取或创建FunASR客户端
            if user not in self.funasr_client or self.funasr_client[user] is None:
                logger.info(f"为用户 {user} 创建新的 FunASR 客户端")
                self.funasr_client[user] = FunASRClient()
                try:
                    logger.debug(f"正在连接 FunASR 服务器...")
                    # 使用事件循环运行异步连接
                    loop.run_until_complete(self.funasr_client[user].connect())
                    logger.info(f"FunASR 服务器连接成功")
                except Exception as e:
                    logger.error(f"连接 FunASR 服务器失败: {str(e)}")
                    raise

            # 检查是否是结束信号
            if input_data == b"ENDASR":
                logger.info(f"收到用户 {user} 的结束信号")
                try:
                    # 使用事件循环运行异步停止录音
                    final_text = loop.run_until_complete(self.funasr_client[user].stop_recording())
                    logger.info(f"用户 {user} 的最终识别结果: {final_text}")
                    
                    # 发送最终结果
                    if final_text:
                        logger.debug(f"发送最终结果到下一个模块: {final_text}")
                        next_func(streamly, user, final_text)
                    
                    return "ENDASR"
                except Exception as e:
                    logger.error(f"处理结束信号时出错: {str(e)}")
                    raise

            # 发送音频数据
            logger.debug(f"发送音频数据到 FunASR 服务器，数据长度: {len(input_data)}")
            # 使用事件循环运行异步发送音频
            loop.run_until_complete(self.funasr_client[user].send_audio(input_data))

            # 获取当前识别文本
            current_text = self.funasr_client[user].recognized_text

            if current_text:
                logger.debug(f"当前识别文本: {current_text}")
                final_json = json.dumps({
                    "response": current_text,
                })
                # 发送中间结果
                response_func(streamly, user, final_json)

            return current_text

        except Exception as e:
            error_msg = f"音频识别失败: {str(e)}"
            logger.error(error_msg)
            # 发送错误信息
            response_func(streamly, user, error_msg)
            return None
        finally:
            logger.debug(f"完成用户 {user} 的音频处理")
            response_func(streamly, user, None)
            next_func(streamly, user, None)

    def _cleanup(self, user: str):
        """销毁模块，清理所有资源"""
        logger.info(f"开始清理用户 {user} 的资源")
        try:
            # 关闭FunASR客户端
            if user in self.funasr_client and self.funasr_client[user]:
                logger.debug(f"关闭用户 {user} 的 FunASR 客户端")
                # 使用事件循环运行异步停止录音
                if user in self.loops:
                    self.loops[user].run_until_complete(self.funasr_client[user].stop_recording())
                del self.funasr_client[user]
            
            # 清理活动时间记录
            if user in self.last_activity:
                del self.last_activity[user]
            
            # 清理事件循环
            if user in self.loops:
                self.loops[user].close()
                del self.loops[user]
            
            # 调用父类的Destroy方法
            super()._cleanup(user)
            logger.info(f"用户 {user} 的资源清理完成")
        except Exception as e:
            logger.error(f"清理用户 {user} 资源时出错: {str(e)}")
            raise


            
