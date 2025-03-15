import argparse
import io
import sys
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread

import pyaudio

current_dir = os.path.dirname(os.path.abspath(__file__))
pipeline_dir = os.path.dirname(os.path.dirname(current_dir))  # D:\LCBot\LCBotDocker\pipeline
sys.path.append(pipeline_dir)
from modules.TTS.SovitsPost import PostChat


class Answer_Chunk:
    def __init__(self, text, user, streamly):
        self.text = text
        self.user = user
        self.streamly = streamly
        self.audio_queue:Queue = Queue()  # 音频数据队列
        self.is_end = False
        self.thread: Thread = None
        self.streaming = False
        self.audio_ready = threading.Event()
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.chunk_size = None  # 动态块大小
        # 增加缓冲区阈值控制
        self.min_buffer_size = 3  # 至少缓存3个音频块再开始播放
        self.buffer_ready = threading.Event()

    def init_audio_stream(self):
        """初始化音频流"""
        if not self.stream:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=32000,  # 根据实际音频采样率调整
                output=True
            )

    def write_stream_audio(self, chunk):
        """写入音频数据并播放"""
        #将块放入队列
        self.audio_queue.put(chunk)
        if self.streamly:
            self.init_audio_stream()
            self.stream.write(chunk)  # 流式模式下逐块播放

    def stop_streaming(self):
        """停止流式传输"""
        self.streaming = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def play_audio_from_buffer(self):
        """从缓冲区播放音频"""
        if self.stream: return
        self.init_audio_stream()
        while True:
            data = self.audio_queue.get() #从队列中取出块
            if not data:
                break
            self.stream.write(data)
        self.stop_streaming()

    def close(self):
        """释放资源"""
        self.stop_streaming()
        if self.thread and self.thread.is_alive():
            self.thread.join()
            print("线程已释放")
        self.p.terminate()

    def __del__(self):
        print("对象被销毁")
        self.close()


def stream_audio(answer: Answer_Chunk, response, streamly: bool):
    """流式音频处理"""
    answer.streaming = True
    if not streamly:
        # 非流式模式下，等待所有数据写入缓冲区
        answer.write_stream_audio(response)
        answer.audio_ready.set()  # 通知音频数据已准备好
    else:
        # 流式模式下逐块写入和播放
        answer.write_stream_audio(response)



def handle_stream_response(chat_response, answer: Answer_Chunk, invoke_func):
    """处理流式响应"""
    try:
        for chunk in chat_response.iter_content(chunk_size=None):  # 动态块大小
            stream_audio(answer, chunk, answer.streamly)
            invoke_func(answer)
    except Exception as e:
        print(f"处理流时出错: {str(e)}")
    finally:
        answer.is_end = True
        invoke_func(answer)
        chat_response.close()  # 确保释放连接


def GetService(streamly, user, text):
    """获取TTS服务"""
    print("GetLLMService")
    chat_response = PostChat(streamly=streamly, user=user, text=text).GetResponse()
    answer = Answer_Chunk(text=text, user=user, streamly=streamly)
    answer.thread = Thread(target=handle_stream_response, args=(chat_response, answer, on_stream_complete))
    answer.thread.start()
    return answer


def on_stream_complete(answer: Answer_Chunk):
    """传输完成后的回调"""
    answer.play_audio_from_buffer()
    if answer.is_end:
        del answer


def external_call(streamly, user, text):
    """外部调用"""
    answer = GetService(streamly, user, text)
    answer.thread.join()
    answer.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TTS服务客户端")
    parser.add_argument("--streamly", action="store_true", help="使用流式传输")
    parser.add_argument("--user", type=str, default="user", help="用户标识")
    parser.add_argument("--text", type=str, required=True, help="输入文本")
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=4) as executor:
        future = executor.submit(GetService, streamly=args.streamly, user=args.user, text=args.text)
        answer = future.result()
        answer.thread.join()
        answer.close()


if __name__ == "__main__":
    main()