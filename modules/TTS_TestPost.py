import base64
import json

import pyaudio
import requests

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
    def __init__(self,streamly,user,text):
        self.payload = {
            "streamly": streamly,
            "user": user,
            "Input": text,
            "text": text,
            "temperature": 1,
            "max_length": 1024,
        }
        self.streamly = streamly
        self.response = requests.request("POST", url, json=self.payload, headers=headers,stream=streamly)
        self.response.encoding = 'utf-8'


    def GetResponse(self):
        return self.response
    def PrintAnswer(self):
        return self.text  # 返回存储的响应内容

if __name__ == "__main__":
    from queue import Queue
    audio_queue = Queue()  # 示例队列

    # 启动 main 服务
    ps = PostChat(streamly=True,user="user",
             text="臣本布衣，躬耕于南阳，苟全性命于乱世，不求闻达于诸侯。先帝不以臣卑鄙，猥自枉屈，三顾臣于草庐之中，咨臣以当世之事，由是感激，遂许先帝以驱驰。后值倾覆，受任于败军之际，奉命于危难之间：尔来二十有一年矣").GetResponse()

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=32000,  # 根据实际音频采样率调整
        output=True
    )

    for chunk in ps.iter_content(chunk_size=None):
        try:
            # 1. 将bytes转换为JSON
            chunk_str = chunk.decode('utf-8').strip()
            chunk_data = json.loads(chunk_str)

            # 2. 提取base64编码的音频数据
            if 'chunk' in chunk_data:
                # 3. Base64解码
                audio_bytes = base64.b64decode(chunk_data['chunk'])
                # 4. 放入队列
                audio_queue.put(audio_bytes)
                stream.write(audio_bytes)

        except Exception as e:
            print(f"处理chunk时出错: {str(e)}")

    # 使用示例（后续处理）：
    while not audio_queue.empty():
        audio_data = audio_queue.get()
        # 这里可以添加播放音频或保存为wav文件的逻辑


