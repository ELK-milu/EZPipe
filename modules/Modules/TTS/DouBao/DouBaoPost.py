# coding=utf-8
import base64
import io
import time
import wave

import pyaudio
from requests.adapters import HTTPAdapter
import requests
from urllib3 import Retry
import uuid

# 默认请求头
default_header = bytearray(b'\x11\x10\x11\x00')
TOKEN = "HvLwi9jvzAOExH7hzbIxEndcZq3C28Dm"
HOST = "openspeech.bytedance.com"
API_URL = f"https://{HOST}/api/v1/tts"

# 创建连接池和重试策略
retry_strategy = Retry(
    total=3,  # 总的重试次数
    backoff_factor=0.5,  # 重试之间的延迟时间因子
    status_forcelist=[500, 502, 503, 504],  # 需要重试的HTTP状态码
    allowed_methods=["POST", "HEAD"]  # 允许重试的HTTP方法
)

# 在程序启动时创建全局Session并配置
SESSION = requests.Session()
# 配置最大连接数和连接超时
ADAPTER = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=5,  # 连接池中连接的最大数量
    pool_maxsize=10,     # 连接池中保持的最大连接数
    pool_block=False     # 连接池满时不阻塞
)
SESSION.mount('http://', ADAPTER)
SESSION.mount('https://', ADAPTER)

# 更新会话头信息
SESSION.headers.update({
    "Authorization": f"Bearer; {TOKEN}",
    "Content-Type": "application/json",
})


def SetSessionConfig(token, host):
    global TOKEN
    global HOST
    global API_URL
    global ADAPTER
    global SESSION
    TOKEN = token
    HOST = host
    API_URL = f"https://{HOST}/api/v1/tts"
    SESSION.close()
    SESSION = requests.Session()

    SESSION.mount('http://', ADAPTER)
    SESSION.mount('https://', ADAPTER)

    SESSION.headers.clear()
    # 更新会话头信息
    SESSION.headers.update({
        "Authorization": f"Bearer; {TOKEN}",
        "Content-Type": "application/json",
    })
    print(f"DouBaoPost URL已设置为{API_URL}, token为{TOKEN}")
    return SESSION, API_URL  # Return both the session and url


def uuidv4():
    """生成UUIDv4"""
    return str(uuid.uuid4())


class PostChat:
    def __init__(self,appid,cluster,session):
        # 配置参数
        self.appid = appid
        self.cluster = cluster
        self.voice_type = None # 可根据需要修改发音人
        self.session = session

        # 基础请求模板
        self.payload  = {
            "app": {
                "appid": appid,
                "token": "access_token",
                "cluster": cluster
            },
            "user": {
                "uid": "user"
            },
            "audio": {
                "voice_type": "zh_female_linjianvhai_moon_bigtts",
                "encoding": "wav",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": "uuid",
                "text": "字节跳动语音合成。",
                "text_type": "plain",
                "operation": "query"
            }
        }

    def Post(self,user,text,voice_type,emotion):
        # 基础请求模板
        self.payload["user"]["uid"] = user
        self.payload["request"]["text"] = text
        self.payload["audio"]["voice_type"] = voice_type
        self.payload["request"]["reqid"] = uuidv4()

        timeout = (3.0, 10.0)  # (连接超时，读取超时)
        start_time = time.time()
        self.response = self.session.post(
            API_URL,
            json=self.payload,
            stream=False,
            timeout=timeout
        )
        return self.response

    def PrintAnswer(self):
        return self.response.text  # 返回存储的响应内容

def PlayAudio(audio_bytes):
    """直接播放WAV格式音频字节流"""
    try:
        p = pyaudio.PyAudio()
        # 使用wave模块解析内存中的音频数据
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wf:
            stream = p.open(
                format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )

            # 流式播放（每次读取4KB）
            data = wf.readframes(4096)
            while data:
                stream.write(data)
                data = wf.readframes(4096)

            # 安全释放资源
            stream.stop_stream()
            stream.close()
            p.terminate()

    except Exception as e:
        print(f"播放失败：{str(e)}")




if __name__ == '__main__':
    session, api_url = SetSessionConfig(TOKEN, HOST)

    # 创建TTS实例
    tts = PostChat(
        appid="4487078679",  # 替换实际appid
        cluster="volcano_tts",  # 替换实际cluster
        session=session
    )

    # 发送合成请求
    response = tts.Post(
        user="test_user",
        text="欢迎使用字节跳动语音合成服务",
        voice_type="zh_female_linjianvhai_moon_bigtts",  # 使用默认发音人
        emotion="neutral"  # 可以根据需要设置情感
    )

    if response.status_code == 200:
        for chunk in response.iter_content(chunk_size=None):
            response_data = response.json()
            print(response_data)
            if 'data' in response_data:
                audio_data = base64.b64decode(response_data['data'])
                # 直接播放无需保存
                PlayAudio(audio_data)  # <-- 关键调用

                # 保存为本地WAV文件
                with wave.open("output_audio.wav", "wb") as wf:
                    wf.setnchannels(1)  # 假设是单声道
                    wf.setsampwidth(2)  # 假设采样宽度为2字节（16位）
                    wf.setframerate(24000)  # 假设采样率为24000Hz
                    wf.writeframes(audio_data)
