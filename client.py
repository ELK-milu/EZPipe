import argparse
import logging
import atexit
import signal
import sys
from utils.entry_args import Start_EntryService
from utils.entry_args import ShutDown_ALL_Service

#TODO: 后续还需要加入自定义的混合模块设置，可自由配置其中经过的模型流程


# 配置日志
logging.basicConfig(level=logging.DEBUG)

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument(
    "--host", type=str, default="127.0.0.1", required=False, help="host ip, localhost, 0.0.0.0"
)
parser.add_argument("--port", type=int, default=9090, required=False, help="grpc server port")
parser.add_argument(
    "--entrypoint",
    type=str,
    default="ASR",  # 设置默认选项
    help="选择服务启动入口,可在Config中自定义"
)
args = parser.parse_args()

# 注册 atexit 回调，确保程序正常退出时关闭所有服务
atexit.register(ShutDown_ALL_Service)

# 定义信号处理函数
def signal_handler(signum, frame):
    logging.info(f"收到信号 {signum}，关闭服务")
    ShutDown_ALL_Service()
    sys.exit(0)

# 注册信号处理函数
signal.signal(signal.SIGINT, signal_handler)  # 捕获 Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 捕获 kill 命令


#TODO: 最后启动的服务项可以提供一个API作为入口，使用多进程+异步IO处理并发

if __name__ == '__main__':
    try:
        # 启动入口服务
        Start_EntryService(args)
        # 主进程保持运行
        while True:
            pass
    except Exception as e:
        logging.error(f"程序发生异常: {e}")
    finally:
        # 确保在异常退出时关闭所有服务
        logging.info("关闭所有服务")
        ShutDown_ALL_Service()