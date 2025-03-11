import requests

# 生成文本
response = requests.post(
    "http://127.0.0.1:11434/api/generate",
    json={
        "model": "deepseek-r1:8b",
        "prompt": "你好，介绍下你自己？",
        "stream": False
    }
)
print(response.json())