# coding=utf-8
import asyncio
import base64
import re
import time
from requests.adapters import HTTPAdapter

import requests
import websockets
import uuid
import json
import gzip
import copy
import os
from datetime import datetime

from urllib3 import Retry

# 默认请求头
default_header = bytearray(b'\x11\x10\x11\x00')
TOKEN = "HvLwi9jvzAOExH7hzbIxEndcZq3C28Dm"
HOST = "openspeech.bytedance.com"
API_URL = f"wss://{HOST}/api/v1/tts/ws_binary"

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
    API_URL = f"wss://{HOST}/api/v1/tts/ws_binary"
    session = requests.Session()
    session.headers.clear()
    # 更新会话头信息
    session.headers.update({
        "Authorization": f"Bearer; {TOKEN}",
        "Content-Type": "application/json",
    })
    session.mount('http://', ADAPTER)
    session.mount('https://', ADAPTER)
    print(f"DouBaoPost URL已设置为{API_URL}, token为{TOKEN}")
    return session, API_URL  # Return both the session and url


class PostChat:
    def __init__(self,appid,cluster,voice_type):
        # 配置参数
        self.appid = appid
        self.cluster = cluster
        self.voice_type = voice_type # 可根据需要修改发音人

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
                "voice_type": voice_type,
                "encoding": "mp3",
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

    def Post(self,user,text):
        # 基础请求模板
        self.payload  = {
            "app": {
                "appid": self.appid,
                "token": "access_token",
                "cluster": self.cluster
            },
            "user": {
                "uid": user
            },
            "audio": {
                "voice_type": self.voice_type,
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": "uuid",
                "text": text,
                "text_type": "plain",
                "operation": "query"
            }
        }


        print(f"请求参数: {self.payload}")
        timeout = (3.0, 10.0)  # (连接超时，读取超时)
        start_time = time.time()
        try:
            self.response = SESSION.post(
                "https://openspeech.bytedance.com/api/v1/tts",
                json=self.payload,
                stream=False,
                timeout=timeout
            )
            elapsed = time.time() - start_time
            print(f"请求耗时: {elapsed:.2f}秒")
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")
    def GetResponse(self):
        return self.response

    def GetURL(self):
        return self.url

    def PrintAnswer(self):
        return self.response.text  # 返回存储的响应内容

if __name__ == '__main__':
    response = PostChat().GetResponse()
    audio_data = base64.b64decode(response.json().get('data'))
    #保存为demo.mp3文件
    with open('demo.mp3', 'wb') as f:
        f.write(audio_data)