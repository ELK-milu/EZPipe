import base64
import json
import sys
import os
import keyboard
import asyncio
import threading
import time
import wave
import platform

import pyaudio
import requests
from queue import Queue

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 正确推导到pipeline目录（上溯两级）
pipeline_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(pipeline_dir)

url = "http://127.0.0.1:3421/input"

headers = {
    "Authorization": "",
    "Content-Type": "application/json"
}

'''
POST:
```json
{
    streamly:boolean,
    user:string,
    Input:string,
    text: text,
    temperature:number,
    max_length:integer
}
```
'''


class PostChat:
    def __init__(self, streamly, user, text):
        self.payload = {
            "streamly": streamly,
            "user": user,
            "Input": text,
            "text": text,
            "temperature": 1,
            "max_length": 1024,
        }
        self.streamly = streamly
        self.response = requests.request("POST", url, json=self.payload, headers=headers, stream=streamly)
        self.response.encoding = 'utf-8'

    def GetResponse(self):
        return self.response
        
    def PrintAnswer(self):
        return self.text  # 返回存储的响应内容


class FunASRClient:
    def __init__(self, host="127.0.0.1", port=10095, ssl_enabled=False, mode="2pass",
                 chunk_size=[5, 10, 5], chunk_interval=10, encoder_chunk_look_back=4,
                 decoder_chunk_look_back=0, hotwords="", use_itn=True, audio_fs=16000):
        self.host = host
        self.port = port
        self.ssl_enabled = ssl_enabled
        self.mode = mode
        self.chunk_size = chunk_size
        self.chunk_interval = chunk_interval
        self.encoder_chunk_look_back = encoder_chunk_look_back
        self.decoder_chunk_look_back = decoder_chunk_look_back
        self.hotwords = hotwords
        self.use_itn = use_itn
        self.audio_fs = audio_fs
        self.websocket = None
        self.is_connected = False
        self.recognized_text = ""
        self.loop = None
        self.ws_task = None
        
    async def connect(self):
        """连接到FunASR服务器"""
        import websockets
        import ssl

        if self.ssl_enabled:
            ssl_context = ssl.SSLContext()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            uri = f"wss://{self.host}:{self.port}"
        else:
            uri = f"ws://{self.host}:{self.port}"
            ssl_context = None
            
        print(f"连接到 {uri}")
        self.websocket = await websockets.connect(
            uri, subprotocols=["binary"], ping_interval=None, ssl=ssl_context
        )
        self.is_connected = True
        
        # 发送初始化消息
        init_message = json.dumps({
            "mode": self.mode,
            "chunk_size": self.chunk_size,
            "chunk_interval": self.chunk_interval,
            "encoder_chunk_look_back": self.encoder_chunk_look_back,
            "decoder_chunk_look_back": self.decoder_chunk_look_back,
            "wav_name": "microphone",
            "is_speaking": True,
            "hotwords": self.hotwords,
            "itn": self.use_itn,
        })
        await self.websocket.send(init_message)
        
        # 启动接收消息的任务
        self.ws_task = asyncio.create_task(self.receive_messages())
        
    async def receive_messages(self):
        """接收并处理来自FunASR服务器的消息"""
        try:
            while self.is_connected:
                message = await self.websocket.recv()
                message = json.loads(message)
                print(message)
                if "text" in message:
                    if "mode" in message:
                        if message["mode"] == "2pass-online":
                            self.recognized_text += message["text"]
                        elif message["mode"] == "2pass-offline":
                            # 替换之前的文本为更准确的离线识别结果
                            self.recognized_text = message["text"]
                    else:
                        self.recognized_text += message["text"]
                    # 清屏并打印当前识别文本
                    self.clear_screen()
                    #print(f"识别文本: {self.recognized_text}")
        except Exception as e:
            print(f"接收消息时出错: {e}")
            self.is_connected = False
        
    def clear_screen(self):
        """清屏"""
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")
            
    async def send_audio(self, audio_data):
        """发送音频数据到FunASR服务器"""
        if self.is_connected and self.websocket:
            await self.websocket.send(audio_data)
            
    async def stop_recording(self):
        """停止录音并通知服务器"""
        print("停止录音并通知服务器")
        if self.is_connected and self.websocket:
            stop_message = json.dumps({
                "is_speaking": False
            })
            await self.websocket.send(stop_message)
            await asyncio.sleep(1)  # 等待最后的处理结果
            
            # 关闭WebSocket连接
            await self.websocket.close()
            self.is_connected = False
            if self.ws_task:
                self.ws_task.cancel()
                
            return self.recognized_text
        return ""
        
    def close(self):
        """关闭连接"""
        if self.loop and self.is_connected:
            asyncio.run_coroutine_threadsafe(self.stop_recording(), self.loop)


class MicrophoneManager:
    def __init__(self, sample_rate=16000, chunk_size=1600):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.audio_data = bytearray()
        self.funasr_client = FunASRClient()
        self.record_thread = None
        self.loop = None
        
    def start_recording(self):
        """开始麦克风录音"""
        if self.is_recording:
            return
            
        # 初始化新的录音会话
        self.audio_data = bytearray()
        self.is_recording = True
        
        # 创建异步事件循环
        self.loop = asyncio.new_event_loop()
        
        # 启动录音线程
        self.record_thread = threading.Thread(target=self._record_thread)
        self.record_thread.daemon = True
        self.record_thread.start()
        
        print("开始录音，按下q键停止...")
        
    def _record_thread(self):
        """录音线程函数"""
        asyncio.set_event_loop(self.loop)
        
        # 连接FunASR服务器
        async def setup_and_record():
            await self.funasr_client.connect()
            self.loop = asyncio.get_event_loop()
            self.funasr_client.loop = self.loop
            
            # 创建并开启麦克风流
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            # 循环录音并发送到FunASR服务器
            while self.is_recording:
                if self.stream:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    self.audio_data.extend(data)
                    await self.funasr_client.send_audio(data)
                await asyncio.sleep(0.01)
        
        # 运行异步录音任务
        self.loop.run_until_complete(setup_and_record())
        
    def stop_recording(self):
        """停止录音并获取识别文本"""
        if not self.is_recording:
            return ""
            
        self.is_recording = False
        
        # 关闭麦克风流
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
        # 获取识别结果
        recognized_text = ""
        if self.loop:
            future = asyncio.run_coroutine_threadsafe(
                self.funasr_client.stop_recording(), self.loop
            )
            recognized_text = future.result(timeout=5)
            
            # 保存录音文件（可选）
            # self.save_audio_to_file("recorded_audio.wav")
            
        # 清理
        if self.record_thread:
            if self.record_thread.is_alive():
                self.record_thread.join(timeout=2)
            self.record_thread = None
            
        return recognized_text
        
    def save_audio_to_file(self, filename):
        """保存录音到WAV文件（可选功能）"""
        if len(self.audio_data) > 0:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16位音频
                wf.setframerate(self.sample_rate)
                wf.writeframes(self.audio_data)
            print(f"录音已保存到 {filename}")


def keyboard_listener(mic_manager):
    """键盘事件监听函数"""
    def on_key_event(event):
        if event.name == 'w' and not mic_manager.is_recording:
            print("按下w键，开始录音...")
            mic_manager.start_recording()
        elif event.name == 'q' and mic_manager.is_recording:
            print("按下q键，停止录音...")
            recognized_text = mic_manager.stop_recording()
            print(f"最终识别结果: {recognized_text}")
            
            # 发送POST请求到Pipeline
            if recognized_text:
                try:
                    print(f"发送识别结果到Pipeline: {recognized_text}")
                    ps = PostChat(streamly=True, user="user", text=recognized_text).GetResponse()
                    
                    for chunk in ps.iter_content(chunk_size=None):
                        chunk_str = chunk.decode('utf-8').strip()
                        try:
                            chunk_data = json.loads(chunk_str)
                            print(chunk_data)
                        except json.JSONDecodeError:
                            print(f"未能解析JSON: {chunk_str}")
                except Exception as e:
                    print(f"发送POST请求时出错: {e}")
    
    # 注册键盘事件
    keyboard.on_press(on_key_event)


if __name__ == "__main__":
    # 创建麦克风管理器
    mic_manager = MicrophoneManager()
    
    # 设置键盘监听
    keyboard_listener(mic_manager)
    
    print("语音识别服务已启动")
    print("按下w键开始录音，按下q键停止录音并发送识别结果")
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("程序退出中...")
        if mic_manager.is_recording:
            mic_manager.stop_recording()


