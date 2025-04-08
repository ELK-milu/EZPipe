import requests

url = "http://127.0.0.1:8090/tts"

# 在程序启动时创建全局Session并配置headers
session = requests.Session()
session.headers.update({
    "Authorization": "",
    "Content-Type": "application/json",
    'Connection': 'Keep-Alive'
})
'''
POST:
```json
{
    "text": "",                   # str.(required) text to be synthesized
    "text_lang: "",               # str.(required) language of the text to be synthesized
    "ref_audio_path": "",         # str.(required) reference audio path
    "aux_ref_audio_paths": [],    # list.(optional) auxiliary reference audio paths for multi-speaker tone fusion
    "prompt_text": "",            # str.(optional) prompt text for the reference audio
    "prompt_lang": "",            # str.(required) language of the prompt text for the reference audio
    "top_k": 5,                   # int. top k sampling
    "top_p": 1,                   # float. top p sampling
    "temperature": 1,             # float. 采样的temperature
    "text_split_method": "cut0",  # str. 切分方式，详见服务端代码text_segmentation_method.py
    "batch_size": 1,              # int. 推理的batch_size
    "batch_threshold": 0.75,      # float. batch拆分的阈值。
    "split_bucket: True,          # bool. 是否将 Batch 拆分为多个 Bucket。
    "speed_factor":1.0,           # float. 控制合成的语速
    "streaming_mode": False,      # bool. 是否流式返回
    "seed": -1,                   # int. 随机种子
    "parallel_infer": True,       # bool. 是否并行推理
    "repetition_penalty": 1.35    # float. T2S 模型的重复惩罚。
}
```
RESP:
成功: 直接返回 wav 音频流， http code 200
失败: 返回包含错误信息的 json, http code 400
'''

class PostChat:
    def __init__(self,streamly,user,text):
        self.payload = {
            "text": text,
            "text_lang": "auto",
            "ref_audio_path": "./GPT_SoVITS/models/派蒙_中立.wav",
            "aux_ref_audio_paths": [],
            "prompt_text": "可恶，怎么又是盗宝团！海灯节就快到了，也不知道安分一点。",
            "prompt_lang": "zh",
            "top_k": 5,
            "top_p": 1,
            "temperature": 1,
            "text_split_method": "cut0",
            "return_fragment": False,
            "batch_size": 2,
            "batch_threshold": 0.75,
            "split_bucket": True,
            "speed_factor":1.0,
            "streaming_mode": streamly,
            "seed": -1,
            "parallel_infer": True,
            "repetition_penalty": 1.35
        }
        self.streamly = streamly
        # 使用全局session发送请求，复用TCP连接
        self.response = session.post(url, json=self.payload, stream=streamly)
        return


    def GetResponse(self):
        return self.response
    def PrintAnswer(self):
        return self.response.text  # 返回存储的响应内容

if __name__ == "__main__":
    # 启动 main 服务
    PostChat(streamly=True,user="user",
             text="臣本布衣，躬耕于南阳，苟全性命于乱世，不求闻达于诸侯。先帝不以臣卑鄙，猥自枉屈，三顾臣于草庐之中，咨臣以当世之事，由是 感激，遂许先帝以驱驰。后值倾覆，受任于败军之际，奉命于危难之间：尔来二十有一年矣   感激，遂许先帝以驱驰。后值倾覆，受任于败军之际，奉命于危难之间：尔来二十有一年矣。")
