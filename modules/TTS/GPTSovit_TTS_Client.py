import requests
import wave
import pyaudio
import io

url = "http://127.0.0.1:8080/?text="


def GetService(streamly, user, text):
    print("GetTTSService")
    # 发送 GET 请求
    finalURL = url + text
    response = requests.get(finalURL)

    # 检查响应状态码
    if response.status_code == 200:
        # 假设响应内容是 audio/wav 类型的数据
        # 使用 io.BytesIO 将响应内容转换为字节流
        audio_data = io.BytesIO(response.content)

        # 使用 wave 模块读取音频数据
        with wave.open(audio_data, "rb") as wf:
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()
        print("音频已播放")
    else:
        print(f"请求失败，状态码: {response.status_code}")
    return audio_data


if __name__ == '__main__':
    GetService(False, "user", "你们好")
