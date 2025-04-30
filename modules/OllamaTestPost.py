import base64
import json

import pyaudio
import requests

url = "http://192.168.10.118:3421/input"

headers = {
    "Authorization": "",
    "Content-Type": "application/json"
}

class PostChat:
    def __init__(self,streamly,user,text,conversation_id):
        self.payload = {
            "streamly": streamly,
            "user": user,
            "Input": text,
            "text": text,
            "Entry": 0,
            "temperature": 1,
            "max_length": 1024,
            "conversation_id":conversation_id,
            "message_id" : "",
            "LLM":{"streamly":True},
        }
        self.streamly = streamly
        self.response = requests.request("POST", url, json=self.payload, headers=headers,stream=streamly)
        self.response.encoding = 'utf-8'


    def GetResponse(self):
        return self.response
    def PrintAnswer(self):
        return self.text  # 返回存储的响应内容

if __name__ == "__main__":
    # 启动 main 服务
    ps = PostChat(streamly=True,user="user",
             text="帮我开下灯",conversation_id="").GetResponse()

    from queue import Queue
    audio_queue = Queue()  # 示例队列

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=32000,  # 根据实际音频采样率调整
        output=True
    )

    for chunk in ps.iter_content(chunk_size=None):
        if chunk:
            #print(chunk)
            chunk_str = chunk.decode('utf-8').strip()
            chunk_data = json.loads(chunk_str)
            if chunk_data.get("type") == "text" :
                response_json = chunk_data.get("chunk")
                final_json = json.loads(response_json)
                final_think = final_json.get("think")
                final_response = final_json.get("response")
                print(final_think + final_response)
            elif chunk_data.get("type") == "audio/wav":
                # 3. Base64解码
                audio_bytes = base64.b64decode(chunk_data['chunk'])

                # 4. 放入队列
                audio_queue.put(audio_bytes)
                stream.write(audio_bytes)
                print(f"接收到音频")
