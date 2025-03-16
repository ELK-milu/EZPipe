from typing import Any
import sys

from pathlib import Path

# 获取项目根目录路径

project_root = Path(__file__).resolve().parent.parent

sys.path.append(str(project_root))
from Modules.TTS.GPTSovit_API import GPTSoVit_TTSModule
from PipeLine.BasePipeLine import PipeLine
from PipeLineAPI.ChildPipeAPI import SampleAPIService

# 测试用例
pipeline = PipeLine.create_pipeline(
    GPTSoVit_TTSModule
)

# 启动服务
# 修改后的测试代码调用方式
#pipeline.GetService(streamly=False, user="test_user", input_data=b"fake_wav_data")
#final_audio = pipeline.Output("test_user")
#print(f"Success! Output length: {(final_audio)}")
#pipeline.Destroy()


# 启动服务
if __name__ == "__main__":
    service = SampleAPIService(
        pipeline=pipeline,
        host="127.0.0.1",
        port=3421
    )
    service.Print_Request_Schema()
    service.Run()
