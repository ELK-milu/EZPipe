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
RESP:
成功: 直接返回 wav 音频流， http code 200
失败: 返回包含错误信息的 json, http code 400
'''

#本台消息，国家主席习近平在中国龙年元宵节

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
    # 启动 main 服务
    ps = PostChat(streamly=True,user="user",
             text="1111")
    print(ps.GetResponse().text)