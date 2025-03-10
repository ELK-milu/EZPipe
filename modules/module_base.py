import os
import signal
import subprocess
import psutil
import platform

class BaseModule:
    def __init__(self, start_command, service_path, args):
        self.start_command = start_command
        self.service_path = service_path
        self.args = args
        self.process = None
        self.start_args = [str(self.start_command), str(self.service_path)]

        # 解析 args 并添加到 command 列表中
        for arg in args:
            if ' ' in arg:
                key, value = arg.split(' ', 1)
                self.start_args.extend([key, value])
            else:
                self.start_args.append(arg)

        print(f"start_args: {self.start_args}")
        print(f"{self.__class__.__name__} 启动项设置完成")

    def Input(self):
        print("Input")

    def Output(self):
        print("Output")

    def run(self):
        print(self.start_args)
        if platform.system() == 'Windows':
            # Windows 系统使用 CREATE_NEW_PROCESS_GROUP 标志
            self.process = subprocess.Popen(
                self.start_args,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Unix 系统使用 os.setsid 创建新的进程组
            self.process = subprocess.Popen(
                self.start_args,
                preexec_fn=os.setsid
            )

        print(f"{self.__class__.__name__} 服务启动, pid: {self.process.pid}")
        return self.process

    def ShutDown_Service(self):
        print("关闭全部服务及子进程")
        if self.process is None:
            print("没有正在运行的进程")
            return

        try:
            parent = psutil.Process(self.process.pid)
            children = parent.children(recursive=True)

            # 先终止子进程
            for child in children:
                child.terminate()

            # 等待子进程终止
            gone, alive = psutil.wait_procs(children, timeout=5)

            # 最后终止父进程
            if self.process.poll() is None:
                if platform.system() == 'Windows':
                    # Windows 系统发送 CTRL_BREAK_EVENT 信号
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    # Unix 系统终止整个进程组
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                self.process.wait(5)
        except psutil.NoSuchProcess:
            print(f"进程 {self.process.pid} 不存在")
        except Exception as e:
            print(f"终止进程 {self.process.pid} 失败: {e}")

class ASR(BaseModule):
    pass

class LLM(BaseModule):
    pass

class TTS(BaseModule):
    pass

if __name__ == '__main__':
    asr = ASR("test", "[test]", [])
    asr.run()
    asr.ShutDown_Service()