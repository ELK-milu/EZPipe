import argparse
from typing import Any
import sys

from pathlib import Path


# 获取项目根目录路径

project_root = Path(__file__).resolve().parent.parent

sys.path.append(str(project_root))
from modules.Modules.ASR.FunASR_ASR_Module import FunASR_ASR_Module
from modules.Modules.TTS.GPTSoVit_TTS_Module import GPTSoVit_TTS_Module
from modules.Modules.LLM.Ollama_LLM_Module import Ollama_LLM_Module
from modules.Modules.LLM.Dify_LLM_Module import Dify_LLM_Module
from modules.PipeLine.BasePipeLine import PipeLine
from modules.PipeLineAPI.ChildPipeAPI import TextToSpeechAPIService
from modules.PipeLineAPI.ASR_LLM_TTS_pipeAPI import ASR_LLM_TTS_pipeAPI

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument(
    "--host", type=str, default="127.0.0.1", required=False, help="host ip, localhost, 0.0.0.0"
)
parser.add_argument("--port", type=int, default=3421, required=False, help="grpc server port")
args = parser.parse_args()


pipeline = PipeLine.create_pipeline(
    Dify_LLM_Module,
    #GPTSoVit_TTS_Module
)

# 启动服务
if __name__ == "__main__":
    service = TextToSpeechAPIService(
        pipeline=pipeline,
        host=args.host,
        port=args.port
    )
    #service.Print_Request_Schema()
    service.Run()

