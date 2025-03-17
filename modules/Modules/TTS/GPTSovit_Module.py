import threading
from asyncio import Queue
from threading import Thread

import pyaudio
from starlette.responses import StreamingResponse

from ..BaseModule import BaseModule

from .SovitsPost import PostChat

"""语音合成模块（输入类型：str，输出类型：bytes）"""
class GPTSoVit_TTSModule(BaseModule):
    def Thread_Task(self, streamly: bool, user: str, input_data: str, invoke_func) -> bytes:
        print(f"[TTS] Starting task for {user} with input: {input_data[:20]}...")
        try:
            chat_response = PostChat(streamly=streamly, user=user, text=input_data).GetResponse()
            print(f"[TTS] Response status: {chat_response.status_code}")

            try:
                chunk_count = 0
                for chunk in chat_response.iter_content(chunk_size=None):
                    if chunk:
                        stop_event = self.stop_events[user]
                        if stop_event.is_set():  # 检查停止标志
                            print(f"[TTS] {user} 主动停止合成")
                            break  # 直接中断循环
                        print(f"[TTS] Sending {user} chunk #{chunk_count} ({len(chunk)} bytes)")
                        invoke_func(streamly, user, chunk)
                        chunk_count += 1
                    else:
                        print("[TTS] Received empty chunk")
            finally:
                print(f"[TTS] Total sent {chunk_count} chunks")
                invoke_func(streamly, user, None)
                chat_response.close()
        except Exception as e:
            print(f"[TTS] Error: {str(e)}")
            invoke_func(streamly, user, None)
            chat_response.close()
