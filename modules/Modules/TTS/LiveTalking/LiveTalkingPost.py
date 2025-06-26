import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

URL = "http://117.50.245.216:8010"

# 在程序启动时创建全局Session并配置headers
SESSION = requests.Session()
# 更新会话头信息
SESSION.headers.update({
    "Authorization": "",
    "Content-Type": "application/json",
    'Connection': 'Keep-Alive',
})

def SetSessionConfig(seturl, headerkey):
    global URL
    global SESSION
    SESSION.close()
    URL = seturl
    SESSION = requests.Session()
    SESSION.headers.clear()
    SESSION.headers.update({
        "Authorization": "",
        "Content-Type": "application/json",
        'Connection': 'Keep-Alive',
    })
    print(f"LiveTalkingPost URL已设置为{seturl}, headerkey为{headerkey}")
    return SESSION, seturl  # Return both the session and url



class PostChat:
    def __init__(self, interrupt,type,url,session):
        self.payload = {
            "text": "此处填写文字",
            "type": type,
            "interrupt" : interrupt,
            "sessionid": None,
            "voice" : "邻家女孩",
            "emotion": "中立"
        }

        self.url = url
        self.postURl = self.url + "/human"
        self.session = session
        self.timeout = 10

    def Post(self, text, sessionid, voice, emotion):
        self.payload["text"] = text
        self.payload["sessionid"] = sessionid
        self.payload["voice"] = voice
        self.payload["emotion"] = emotion
        # 使用全局session发送请求，复用TCP连接

        self.response = self.session.post(
                self.postURl,
                json=self.payload,
                stream=False,
                timeout=self.timeout
            )
        self.response.encoding = 'utf-8'
        return self.response


if __name__ == "__main__":
    # 启动 main 服务
    start = time.time()
    chat = PostChat(streamly=False, user="user", text="测试一下TTS服务的响应速度")
    response = chat.GetResponse()
    print(f"请求总耗时: {time.time() - start:.3f}秒, 状态码: {response.status_code}")
