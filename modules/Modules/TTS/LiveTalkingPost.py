import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

url = "http://117.50.245.216:8010/"

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
})


class PostChat:
    def __init__(self, interrupt,type, sessionid, text,reffile,reftext):
        self.payload = {
            "text": text,
            "type": type,
            "interrupt" : interrupt,
            "sessionid": sessionid,
            "reffile" : reffile,
            "reftext": reftext
        }

        print(f"请求参数: {self.payload}")
        # 设置合理的超时时间，避免长时间等待
        timeout = (3.0, 10.0)  # (连接超时，读取超时)
        self.url = url

        postURl = self.url + "human"
        
        # 使用全局session发送请求，复用TCP连接
        start_time = time.time()
        try:
            self.response = session.post(
                postURl,
                json=self.payload, 
                stream=False,
                timeout=timeout
            )
            elapsed = time.time() - start_time
            # 如果请求时间超过100ms，记录下来用于调试
            if elapsed > 0.1:
                print(f"请求耗时: {elapsed:.3f}秒, 文本长度: {len(text)}")
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}")

    def GetResponse(self):
        return self.response

    def GetURL(self):
        return self.url
        
    def PrintAnswer(self):
        return self.response.text  # 返回存储的响应内容

if __name__ == "__main__":
    # 启动 main 服务
    start = time.time()
    chat = PostChat(streamly=False, user="user", text="测试一下TTS服务的响应速度")
    response = chat.GetResponse()
    print(f"请求总耗时: {time.time() - start:.3f}秒, 状态码: {response.status_code}")
