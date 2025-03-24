import requests
import json

url = "http://localhost/v1/chat-messages"

# 在程序启动时创建全局Session并配置headers
session = requests.Session()
session.headers.update({
    'Authorization': 'Bearer app-vskz5McIRNmySfIek7cReqgC',
    'Content-Type': 'application/json',
})

class PostChat:
    def __init__(self, streamly, user, text):
        self.payload = {
            "inputs": {},
            "query": text,
            "response_mode": "streaming",
            "conversation_id": "fb82baaa-383e-4958-8316-e1333df65154",
            "user": user,
            "files": []
        }
        # 使用全局session发送请求，复用TCP连接
        self.response = session.post(url, json=self.payload, stream=streamly)
        self.response.encoding = 'utf-8'

    def GetSession(self):
        return session

    def GetResponse(self):
        return self.response

