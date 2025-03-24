import requests
import json

url = "http://localhost/v1/chat-messages"

headers = {
    'Authorization': 'Bearer app-vskz5McIRNmySfIek7cReqgC',
    'Content-Type': 'application/json',
}


class Answer_Chunk:
    def __init__(self, text, user, streamly):
        self.text = text
        self.user = user
        self.streamly = streamly
        self.in_think_block = False
        self.think_string = ""
        self.response_string = ""
        self.full_content = ""
        self.Is_End = False

    def GetThinking(self) -> str:
        return self.think_string

    def GetResponse(self) -> str:
        return self.response_string

    def AppendThinking(self, content):
        self.think_string += content

    def AppendResponse(self, content):
        self.response_string += content

def extract_think_response(answer: Answer_Chunk, response: str, streamly: bool) -> tuple:
    """
    处理流式和非流式响应，提取思考内容和最终响应
    """
    prefix = 'data: {"event": "message"'
    if not response.strip().startswith(prefix):
        return answer.GetThinking(), answer.GetResponse()

    # 有时返回的输出结果太长了，只能分几段输出，导致json.loads报错
    print(response)
    if streamly:
        # 处理流式响应
        if response:
            data = response[6:]
            data = json.loads(data)
            print(data)
            if data['event'] == 'message':
                message = str(data['answer'])
                print(message)
                answer.full_content += message

                # 检查是否进入 <think> 块
                if "<think>" in message:
                    print("进入思考块")
                    answer.in_think_block = True

                # 如果当前在 <think> 和 </think> 块中，将内容添加到 think_string
                if answer.in_think_block:
                    answer.AppendThinking(message)
                else:
                    answer.AppendResponse(message)

                # 检查是否退出 <think> 块
                if "</think>" in message:
                    answer.in_think_block = False
    else:
        # 处理非流式响应
        if "message" in response:
            data = response[6:]
            data = json.loads(data)
            message = data["answer"]
            think_start = message.find("<think>")
            think_end = message.find("</think>")
            if think_start != -1 and think_end != -1:
                think_string = message[think_start + 7: think_end]
                response_string = message[think_end + 8:]
    return answer.GetThinking(), answer.GetResponse()


class PostChat:
    def __init__(self,streamly,user,text):
        self.payload = {
            "inputs": {},
            "query": text,
            "response_mode": "streaming",
            "conversation_id": "fb82baaa-383e-4958-8316-e1333df65154",
            "user": user,
            "files": [
            ]
        }

        question = {
            "role": "user",
            "content": text
        }
        #self.payload["messages"].append(question)
        self.streamly = streamly
        self.response = requests.request("POST", url, json=self.payload, headers=headers,stream=streamly)
        self.response.encoding = 'utf-8'
        return


    def GetResponse(self):
        return self.response
    def PrintAnswer(self):
        return self.response_text  # 返回存储的响应内容





if __name__ == '__main__':
    answer = Answer_Chunk("你好，介绍下你自己？", "user", True)
    # 生成文本
    response = PostChat(
        True    ,
        "user",
        "你好，介绍下你自己？"
    ).GetResponse()
    for chunk in response.iter_content(chunk_size=None):
        decoded = chunk.decode('utf-8')
        extract_think_response(answer, decoded, answer.streamly)

