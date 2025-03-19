import asyncio
import json
import keyboard
import pyaudio
import requests
import threading
import time
import logging
from queue import Queue
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ASRTester')

class ASRTester:
    def __init__(self, api_url="http://127.0.0.1:3421/input"):
        self.api_url = api_url
        self.is_recording = False
        self.audio_queue = Queue()
        self.stream = None
        self.pyaudio_instance = None
        self.sample_rate = 16000
        self.chunk_size = 1600
        self.response = None
        self.session = requests.Session()
        self.silence_threshold = 100  # 静音阈值
        self.min_audio_level = 500    # 最小音频电平
        logger.info("ASRTester 初始化完成")
        logger.debug(f"配置参数: sample_rate={self.sample_rate}, chunk_size={self.chunk_size}")

    def is_silence(self, audio_data):
        """检查是否是静音数据"""
        # 将字节数据转换为numpy数组
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        # 计算音频电平
        audio_level = np.abs(audio_array).mean()
        return audio_level < self.silence_threshold

    def is_valid_audio(self, audio_data):
        """检查是否是有效的音频数据"""
        # 将字节数据转换为numpy数组
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        # 检查音频电平是否在合理范围内
        audio_level = np.abs(audio_array).mean()
        return self.min_audio_level <= audio_level <= 32767

    def start_stream(self):
        logger.info("开始初始化音频流")
        try:
            # Initialize PyAudio
            self.pyaudio_instance = pyaudio.PyAudio()
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            self.is_recording = True
            logger.debug("音频流初始化成功")

            # Start recording thread
            recording_thread = threading.Thread(target=self._record_audio)
            recording_thread.daemon = True
            recording_thread.start()
            logger.debug("录音线程已启动")

            # Start API streaming thread
            streaming_thread = threading.Thread(target=self._stream_to_api)
            streaming_thread.daemon = True
            streaming_thread.start()
            logger.debug("API流式传输线程已启动")

            # Start response reading thread
            response_thread = threading.Thread(target=self._read_response)
            response_thread.daemon = True
            response_thread.start()
            logger.debug("响应读取线程已启动")

        except Exception as e:
            logger.error(f"启动流失败: {e}")
            raise

    def _record_audio(self):
        logger.info("开始录音")
        chunks_count = 0
        valid_chunks = 0
        while self.is_recording:
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                if self.is_valid_audio(data):
                    self.audio_queue.put(data)
                    valid_chunks += 1
                chunks_count += 1
                if chunks_count % 100 == 0:  # 每100个块记录一次
                    logger.debug(f"已录制 {chunks_count} 个音频块，有效块数: {valid_chunks}")
            except Exception as e:
                logger.error(f"录音错误: {e}")
                break
        logger.info(f"录音结束，共录制 {chunks_count} 个音频块，有效块数: {valid_chunks}")

    def _stream_to_api(self):
        logger.info("开始向API传输数据")
        headers = {
            "Content-Type": "application/json"
        }

        # 初始化连接
        payload = {
            "streamly": True,
            "user": "test_user",
            "Input": None,
            "temperature": 0.7,
            "max_length": 100
        }

        try:
            logger.debug("建立初始连接")
            self.response = requests.request(
                "POST", self.api_url, json=payload, headers=headers, stream=True)
            self.response.encoding = 'utf-8'
            logger.info("API连接建立成功")

            chunks_sent = 0
            while self.is_recording or not self.audio_queue.empty():
                if not self.audio_queue.empty():
                    audio_chunk = self.audio_queue.get()
                    # 发送音频数据
                    chunk_payload = {
                        "streamly": True,
                        "user": "test_user",
                        "Input": audio_chunk.hex(),
                        "temperature": 0.7,
                        "max_length": 100
                    }
                    self.response = requests.request(
                        "POST", self.api_url, json=chunk_payload, headers=headers, stream=True)
                    chunks_sent += 1
                    if chunks_sent % 100 == 0:  # 每100个块记录一次
                        logger.debug(f"已发送 {chunks_sent} 个音频块")
                time.sleep(0.01)

            # 发送结束信号
            logger.info("发送结束信号")
            end_payload = {
                "streamly": True,
                "user": "test_user",
                "Input": None,
                "temperature": 0.7,
                "max_length": 100
            }
            self.response = requests.request(
                "POST", self.api_url, json=end_payload, headers=headers, stream=True)
            logger.info(f"数据传输完成，共发送 {chunks_sent} 个音频块")

        except Exception as e:
            logger.error(f"API 流式传输错误: {e}")

    def _read_response(self):
        """读取并处理API响应"""
        logger.info("开始读取API响应")
        if self.response:
            try:
                for chunk in self.response.iter_lines():
                    if chunk:
                        try:
                            response_data = json.loads(chunk.decode('utf-8'))
                            logger.info(f"收到响应: {response_data}")
                        except json.JSONDecodeError:
                            logger.warning(f"无法解析响应: {chunk.decode('utf-8')}")
            except Exception as e:
                logger.error(f"读取响应错误: {e}")
        logger.info("响应读取结束")

    def stop_stream(self):
        logger.info("开始停止录音流")
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            logger.debug("音频流已关闭")
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            logger.debug("PyAudio实例已终止")
        logger.info("录音流停止完成")
        # 不关闭session，保持连接


def keyboard_listener(tester):
    def on_key_event(event):
        if event.name == 'w' and not tester.is_recording:
            logger.info("检测到'w'键按下，开始录音...")
            tester.start_stream()
        elif event.name == 'q' and tester.is_recording:
            logger.info("检测到'q'键按下，停止录音...")
            tester.stop_stream()

    keyboard.on_press(on_key_event)


if __name__ == "__main__":
    try:
        logger.info("=== ASR 测试程序启动 ===")
        tester = ASRTester()

        print("\n=== ASR 测试说明 ===")
        print("1. 按 'w' 开始录音")
        print("2. 按 'q' 停止录音")
        print("3. 按 Ctrl+C 退出程序")
        print("4. 查看日志了解详细运行状态\n")

        keyboard_listener(tester)

        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("接收到退出信号")
        print("\n正在安全退出...")
        if tester.is_recording:
            tester.stop_stream()
        logger.info("=== ASR 测试程序已退出 ===")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        raise