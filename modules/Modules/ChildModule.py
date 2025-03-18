from .BaseModule import BaseModule
from typing import Any

# 一个自定义功能模块的用例，当然以下模块都是简单模拟实现
# 注意返回值没啥意义，只是需要在重构的时候指定类型，便于PipeLine进行类型检查
class SampleModule(BaseModule):
    """音频接收模块（输入类型：Any，输出类型：wav）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> bytes:
        # 模拟音频接收逻辑
        print(f"[AudioReceiver] Receiving audio from {user}")
        #return b"fake_wav_data"

class AudioReceiverModule(BaseModule):
    """音频接收模块（输入类型：Any，输出类型：wav）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> bytes:
        # 模拟音频接收逻辑
        print(f"[AudioReceiver] Receiving audio from {user}")
        #return b"fake_wav_data"

class ASRModule(BaseModule):
    """语音识别模块（输入类型：wav，输出类型：str）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> str:
        # 模拟ASR处理
        print(f"[ASR] Processing audio of length {len(input_data)}")
        #return "Transcribed text"

class LLMModule(BaseModule):
    """大语言模型模块（输入类型：str，输出类型：str）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> str:
        # 模拟LLM处理
        print(f"[LLM] Processing text: {input_data}")
        #return "Generated response"

class TTSModule(BaseModule):
    """语音合成模块（输入类型：str，输出类型：bytes）"""
    def Thread_Task(self, streamly: bool, user: str, input_data: Any, response_func, next_func) -> bytes:
        # 模拟TTS处理
        print(f"[TTS] Synthesizing: {input_data}")
        #return b"fake_audio_output"