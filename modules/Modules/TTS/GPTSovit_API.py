import threading
from asyncio import Queue
from threading import Thread

from ..BaseModule import BaseModule

from .SovitsPost import PostChat

"""语音合成模块（输入类型：str，输出类型：bytes）"""
class GPTSoVit_TTSModule(BaseModule):
    def process(self,streamly:bool, user: str, input_data: str) -> bytes:
        # 模拟音频接收逻辑
        print(f"[AudioReceiver] Receiving audio from {user}")
        return b"fake_wav_data"
