import base64
import io
import json
import wave

import pyaudio
import requests

url = "http://192.168.30.46:3421/input"

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
            "TTS":{"streamly":True,
                   "voice": "佼佼仔",
                   "emotion": "中立"},
        }
        self.streamly = streamly
        self.response = requests.request("POST", url, json=self.payload, headers=headers,stream=streamly)
        self.response.encoding = 'utf-8'


    def GetResponse(self):
        return self.response
    def PrintAnswer(self):
        return self.text  # 返回存储的响应内容


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



if __name__ == "__main__":
    # 启动 main 服务
    ps = PostChat(streamly=True,user="user",
             text="介绍下你自己",conversation_id="").GetResponse()

    from queue import Queue
    audio_queue = Queue()  # 示例队列

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
            elif chunk_data.get("type") == "audio/wav":
                # 3. Base64解码
                audio_bytes = base64.b64decode(chunk_data['chunk'])
                PlayAudio(audio_bytes)
                print(f"接收到音频")
