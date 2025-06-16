import argparse
import sys

from pathlib import Path

from modules.Modules.TTS.GPTSovits.GPTSoVit_TTS_Module import GPTSoVit_TTS_Module
from modules.Modules.TTS.DouBao.DouBao_TTS_Module import Doubao_TTS_Module
# 获取项目根目录路径

project_root = Path(__file__).resolve().parent.parent

sys.path.append(str(project_root))
from modules.Modules.LLM.Dify.Dify_LLM_Module import Dify_LLM_Module
from modules.Modules.TTS.LiveTalking.LiveTalking_Module import LiveTalking_Module
from modules.PipeLine.BasePipeLine import PipeLine
from modules.PipeLineAPI.ChildPipeAPI import TextToVideoHumanAPIService
from modules.utils.logger import setup_root_logger, get_logger

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument(
    "--host", type=str, default="192.168.30.46", required=False, help="host ip, localhost, 0.0.0.0"
)
parser.add_argument("--port", type=int, default=3422, required=False, help="grpc server port")
parser.add_argument("--workers", type=int, default=4, required=False, help="grpc server workers")
parser.add_argument("--config", type=str, default="VideoHumanConfig.yaml", required=False, help="grpc server workers")
args = parser.parse_args()

# 初始化全局logger
setup_root_logger()

# 获取服务logger
service_logger = get_logger("Service")

service_logger.info("服务启动中...")

# 创建Pipeline
pipeline = PipeLine.create_pipeline(
Dify_LLM_Module,
    LiveTalking_Module,
)

# 启动服务
if __name__ == "__main__":

    service = TextToVideoHumanAPIService(
        pipeline=pipeline,
        host=args.host,
        port=args.port,
        workers=args.workers,
        configName = args.config
    )
    #service.Print_Request_Schema()
    service_logger.info(f"服务已启动，监听地址: {args.host}:{args.port}")
    service.Run()

