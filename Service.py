import argparse
from typing import Any
import sys
import time
import threading

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
from modules.utils.logger import setup_root_logger, get_logger

def warm_up_tts_service():
    """预热TTS服务，减少首次请求响应时间"""
    from modules.Modules.TTS.SovitsPost import PostChat
    service_logger = get_logger("Service")
    service_logger.info("正在预热TTS服务...")
    
    # 创建预热线程
    def warmup_thread():
        try:
            # 预热短句
            common_phrases = ["您好", "谢谢", "请稍等", "正在处理中", "我明白了"]
            for phrase in common_phrases:
                start = time.time()
                tts = PostChat(streamly=False, user="system", text=phrase)
                response = tts.GetResponse()
                if response.ok:
                    elapsed = time.time() - start
                    service_logger.info(f"TTS预热短句[{phrase}]成功，耗时: {elapsed:.3f}秒")
                else:
                    service_logger.warning(f"TTS预热短句[{phrase}]失败，状态码: {response.status_code}")
        except Exception as e:
            service_logger.error(f"TTS预热出现异常: {str(e)}")
    
    # 启动预热线程
    warmup = threading.Thread(target=warmup_thread)
    warmup.daemon = True
    warmup.start()
    
    return warmup  # 返回线程对象供主线程等待

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument(
    "--host", type=str, default="192.168.10.118", required=False, help="host ip, localhost, 0.0.0.0"
)
parser.add_argument("--port", type=int, default=3421, required=False, help="grpc server port")
parser.add_argument("--workers", type=int, default=4, required=False, help="grpc server workers")
args = parser.parse_args()

# 初始化全局logger
setup_root_logger()

# 获取服务logger
service_logger = get_logger("Service")

service_logger.info("服务启动中...")

# 预热TTS服务
warmup_thread = warm_up_tts_service()

# 创建Pipeline
pipeline = PipeLine.create_pipeline(
    Dify_LLM_Module,
    GPTSoVit_TTS_Module
)

# 启动服务
if __name__ == "__main__":
    # 等待TTS预热完成，最多等待5秒
    warmup_thread.join(timeout=5.0)
    
    service = TextToSpeechAPIService(
        pipeline=pipeline,
        host=args.host,
        port=args.port,
        workers=args.workers
    )
    #service.Print_Request_Schema()
    service_logger.info(f"服务已启动，监听地址: {args.host}:{args.port}")
    service.Run()

