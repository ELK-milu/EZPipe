import requests
import json

url = "http://localhost/v1/chat-messages"

# 在程序启动时创建全局Session并配置headers
session = requests.Session()
session.headers.update({
    'Authorization': 'Bearer app-5NYcfDmCigqLgwGoPSD0HtrQ',
    'Content-Type': 'application/json',
    'Connection': 'Keep-Alive'
})

class PostChat:
    # userID 和 ConversationID对应的会话不存在会报错404
    def __init__(self, streamly,conversation_id,user, text):
        self.payload = {
            "inputs": {},
            "query": text,
            "response_mode": "streaming",
            "conversation_id": conversation_id,
            "user": user,
            "files": []
        }
        # 使用全局session发送请求，复用TCP连接
        self.response = session.post("http://localhost/v1/chat-messages", json=self.payload, stream=streamly)
        self.response.encoding = 'utf-8'

    def GetSession(self):
        return session

    def GetResponse(self):
        return self.response


if __name__ == '__main__':
    # 生成文本
    response = PostChat(
        streamly=True,
        conversation_id="",
        user="user-1",
        text="你是谁？"
    ).GetResponse()
    print(response.content)