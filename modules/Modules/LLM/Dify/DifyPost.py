import requests
import json

URL = "http://localhost/v1"

# 在程序启动时创建全局Session并配置headers
SESSION = requests.Session()
SESSION.headers.update({
    'Authorization': 'Bearer app-5NYcfDmCigqLgwGoPSD0HtrQ',
    'Content-Type': 'application/json',
    'Connection': 'Keep-Alive'
})

def SetSessionConfig(seturl, headerkey):
    global URL
    global SESSION
    SESSION.close()
    URL = seturl
    SESSION = requests.Session()
    SESSION.headers.clear()
    SESSION.headers.update({
        'Authorization': f'Bearer {headerkey}',
        'Content-Type': 'application/json',
        'Connection': 'Keep-Alive'
    })
    print(f"DifyConfig URL已设置为{seturl}, headerkey为{headerkey}")
    return SESSION, seturl  # Return both the session and url

class PostChat:
    # userID 和 ConversationID对应的会话不存在会报错404
    def __init__(self, streamly,session):
        self.payload = {
            "inputs": {},
            "query": "text",
            "response_mode": "streaming",
            "conversation_id": "",
            "user": "user",
            "files": []
        }
        self.session = session
        self.streamly = streamly

    def Post(self,text,conversation_id,user):
        self.payload["query"] = text
        self.payload["conversation_id"] = conversation_id
        self.payload["user"] = user
        # 使用全局session发送请求，复用TCP连接
        self.response = self.session.post(f"{URL}/chat-messages", json=self.payload, stream=self.streamly)
        self.response.encoding = 'utf-8'
        return self.response


if __name__ == '__main__':
    #开始时间
    import time
    start_time = time.time()
    # 生成文本
    response = PostChat(
        streamly=True,
        conversation_id="",

        user="user-1",
        text="你是谁？",
        session=SESSION
    ).GetResponse()
    i = 0
    for chunk in response.iter_content(chunk_size=None):
        if(i == 0):
            print(f"第一次请求时间:{time.time()-start_time}")
        print(chunk)
        i += 1
