from typing import Any
import sys

from pathlib import Path


# 获取项目根目录路径

project_root = Path(__file__).resolve().parent.parent

sys.path.append(str(project_root))
from Modules.ASR.FunASR_ASR_Module import FunASR_ASR_Module
from Modules.TTS.GPTSoVit_TTS_Module import GPTSoVit_TTS_Module
from Modules.LLM.Ollama_LLM_Module import Ollama_LLM_Module
from PipeLine.BasePipeLine import PipeLine
from PipeLineAPI.ChildPipeAPI import TextToSpeechAPIService

# 测试用例
pipeline = PipeLine.create_pipeline(
    FunASR_ASR_Module,

)

# 启动服务
if __name__ == "__main__":
    service = TextToSpeechAPIService(
        pipeline=pipeline,
        host="127.0.0.1",
        port=3421
    )
    #service.Print_Request_Schema()
    service.Run()
