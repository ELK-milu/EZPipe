import requests

url = "http://127.0.0.1:7861/chat/chat/completions"

headers = {
    "Authorization": "",
    "Content-Type": "application/json"
}

class PostChat:
    def __init__(self,streamly,user,text):
        self.payload = {
            "user": user,
            "model": "deepseek-r1:8b",
            "frequency_penalty": 0,
            "max_tokens": 4096,
            "temperature": 0.7,
            "stream": streamly,
            "top_k": 50,
            "top_p": 0.7,
            "n": 1,
            "response_format": {
                "type": "text"
            },
            "messages": [
            ]
        }

        question = {
            "role": "user",
            "content": text
        }
        self.payload["messages"].append(question)
        self.streamly = streamly
        self.response = requests.request("POST", url, json=self.payload, headers=headers,stream=streamly)
        self.response.encoding = 'utf-8'
        # 检查响应状态码
        if self.response.status_code == 200:
            if self.streamly:
                # 逐步读取流式数据
                for chunk in self.response.iter_content(chunk_size=None):
                    if chunk:
                        # 处理每个 chunk（假设是 UTF-8 编码的文本）
                        print(chunk.decode('utf-8'), end="")
                return
            else:
                self.response_text = self.response.text
                return
        else:
            print(f"Request failed with status code: {self.response.status_code}")
            self.response_text = self.response.status_code


    def GetResponse(self):
        return self.response
    def PrintAnswer(self):
        return self.response_text  # 返回存储的响应内容


