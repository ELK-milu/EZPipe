import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

url = "http://127.0.0.1:8090/tts"

# 创建连接池和重试策略
retry_strategy = Retry(
    total=3,  # 总的重试次数
    backoff_factor=0.5,  # 重试之间的延迟时间因子
    status_forcelist=[500, 502, 503, 504],  # 需要重试的HTTP状态码
    allowed_methods=["POST", "HEAD"]  # 允许重试的HTTP方法
)

# 在程序启动时创建全局Session并配置
session = requests.Session()
# 配置最大连接数和连接超时
adapter = HTTPAdapter(
    max_retries=retry_strategy,
    pool_connections=5,  # 连接池中连接的最大数量
    pool_maxsize=10,     # 连接池中保持的最大连接数
    pool_block=False     # 连接池满时不阻塞
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# 更新会话头信息
session.headers.update({
    "Authorization": "",
    "Content-Type": "application/json",
    'Connection': 'Keep-Alive',
    'Keep-Alive': 'timeout=60, max=100'  # 保持连接活跃
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
    def __init__(self, streamly, user, text,ref_audio_path,prompt_text):
        self.payload = {
            "text": text,
            "text_lang": "auto",
            "ref_audio_path": ref_audio_path,
            "aux_ref_audio_paths": [],
            "prompt_text": prompt_text,
            "prompt_lang": "zh",
            "top_k": 10,
            "top_p": 1,
            "temperature": 1,
            "text_split_method": "cut0",
            "return_fragment": False,
            "batch_size": 24,  # 增加batch_size以加速处理
            "batch_threshold": 0.75,
            "split_bucket": False,
            "speed_factor": 1.0,
            "streaming_mode": False,
            "seed": -1,
            "parallel_infer": True,  # 确保并行推理开启
            "repetition_penalty": 1.35
        }
        self.streamly = streamly
        
        # 添加短文本优化，减少TTS处理时间
        if text and len(text) <= 5:  # 对于非常短的文本
            self.payload["batch_size"] = 1  # 减小batch_size
            self.payload["parallel_infer"] = True
            
        # 设置合理的超时时间，避免长时间等待
        timeout = (15.0, 15.0)  # (连接超时，读取超时)
        
        # 使用全局session发送请求，复用TCP连接
        start_time = time.time()
        try:
            self.response = session.post(
                url, 
                json=self.payload, 
                stream=streamly,
                timeout=timeout
            )
            elapsed = time.time() - start_time
            # 如果请求时间超过100ms，记录下来用于调试
            if elapsed > 0.1:
                print(f"[TTS_POST] 请求耗时: {elapsed:.3f}秒, 文本长度: {len(text)}")
        except requests.exceptions.RequestException as e:
            print(f"[TTS_POST] 请求异常: {e}")
            # 创建一个空响应对象
            self.response = type('obj', (object,), {
                'ok': False,
                'status_code': 500,
                'text': f"连接错误: {str(e)}",
                'iter_content': lambda chunk_size: []
            })

    def GetResponse(self):
        return self.response
        
    def PrintAnswer(self):
        return self.response.text  # 返回存储的响应内容

if __name__ == "__main__":
    # 启动 main 服务
    start = time.time()
    chat = PostChat(streamly=False, user="user", text="你好，请问有什么我可以帮助你的吗？",ref_audio_path="./GPT_SoVITS/models/佼佼仔_中立.wav", prompt_text="今天，我将带领大家穿越时空，去到未来的杭州。")
    response = chat.GetResponse()
    print(f"请求总耗时: {time.time() - start:.3f}秒, 状态码: {response.status_code}")
    # +++ 新增保存音频逻辑 +++
    if response.status_code == 200:
        # 定义输出路径（按需修改）
        output_path = "./output.wav"
        # 二进制写入模式保存音频
        with open(output_path, "wb") as f:
            f.write(response.content)
        print(f"音频已保存至: {output_path}")
    else:
        print("请求失败，错误信息:", response.text)
