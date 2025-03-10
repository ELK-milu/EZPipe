import json
import os
import platform
import signal
import sys
from pathlib import Path
import importlib

import psutil

Config_path = "Config.json"

entry_args = []

cmd_config = ""

def load_config(config_path=Config_path):
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 格式校验
        required_sections = ['services']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Config.json配置文件缺少必要字段: {section}")

        return config

    except json.JSONDecodeError as e:
        print(f"Config.json配置文件格式错误: {str(e)}")
        exit(1)
    except Exception as e:
        print(f"Config.json加载配置失败: {str(e)}")
        exit(1)

# 在entry_args.py中添加通用转换函数
def config_to_args(service_config, prefix=""):
    """将嵌套字典结构转换为命令行参数字符串列表"""
    for key, value in service_config.items():
        arg_name = f"--{prefix}{key}" if prefix else f"--{key}"
        #print(f"key: {str(key)};value: {str(value)}")

        # 处理不同数据类型
        if isinstance(value, list):
            entry_args.append(f"{arg_name} {','.join(map(str, value))}")
        elif isinstance(value, bool):
            entry_args.append(f"{arg_name} {1 if value else 0}")
        elif isinstance(value, dict):  # 处理嵌套配置
            entry_args.extend(config_to_args(value, prefix=f"{key}-"))
        else:
            entry_args.append(f"{arg_name} {value}")
    return entry_args


def Select_Entrypoint(args):
    service_config = cmd_config["services"].get(args.entrypoint)
    #print(f"配置文件:{str(service_config)}")
    if not service_config:
        print(f"Config.json配置文件中未找到 {args.entrypoint} 服务配置")
        exit(1)

    # 检查必填字段
    service_required_sections = ['cmd_type', 'client_path','host','port']
    for section in service_required_sections:
        if section not in service_config:
            raise ValueError(f"{args.entrypoint}配置文件Config.json缺少必要字段: {section}")

    # 生成动态参数
    dynamic_args = config_to_args({
        k: v for k, v in service_config.items()
        if k not in ['mode']  # 排除已显式处理的参数
    })
    # 执行命令示例
    print(f"启动命令:{str(dynamic_args)}")
    start_command,service_path,dynamic_args = Get_Pre_Command(dynamic_args)
    # 动态导入模块和类
    WakeUp_Service(args.entrypoint, start_command, service_path, dynamic_args)



def Get_Pre_Command(args):
    """从数组中提取cmd_type和client_path，并生成命令字符串"""
    cmd_type = None
    client_path = None
    filtered_args = []

    for arg in args:
        if '--cmd_type' in arg:
            cmd_type = arg.split(' ', 1)[1]  # 截取空格后的所有内容
        elif '--client_path' in arg:
            client_path = arg.split(' ', 1)[1]  # 截取空格后的所有内容
        else:
            filtered_args.append(arg)

    return cmd_type,client_path,filtered_args

def Start_EntryService(args):
    global cmd_config
    cmd_config = load_config()
    Select_Entrypoint(args)


# 管理的服务字典
Service_Process_Dictionary = {}


def WakeUp_Service(module_name, start_command, service_path, dynamic_args):
    module_path = "modules.module_base"  # 模块路径

    try:
        # 动态导入模块
        module = importlib.import_module(module_path)
        # 获取模块中的类
        cls = getattr(module, module_name)
        # 实例化类
        instance = cls(start_command, service_path, dynamic_args)
        # 启动服务
        process = instance.run()  # 假设类中有 run 方法
        # 将进程添加到字典中
        Service_Process_Dictionary[module_name] = process
        print(f"{module_name} 服务已启动，进程ID: {process.pid}")
    except ImportError:
        print(f"模块 {module_path} 导入失败，请检查模块路径是否正确。")
        sys.exit(1)
    except AttributeError:
        print(f"模块 {module_path} 中未找到 {module_name} 对应的同名类。")
        sys.exit(1)
    except Exception as e:
        print(f"启动 {module_name} 服务时发生错误: {e}")
        sys.exit(1)

def ShutDown_ALL_Service():
    for module_name, process in Service_Process_Dictionary.items():
        ShutDown_Service(module_name)

def ShutDown_Service(module_name):
    if module_name not in Service_Process_Dictionary:
        print(f"{module_name} 服务未运行。")
        return
    try:
        process = Service_Process_Dictionary[module_name]
        if process.poll() is None:  # 检查进程是否仍在运行
            if platform.system() == 'Windows':
                # Windows 系统发送 CTRL_BREAK_EVENT 信号
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # Unix 系统终止整个进程组
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(5)  # 等待进程终止
        # 从字典中移除进程
        del Service_Process_Dictionary[module_name]
        print(f"{module_name} 服务已关闭。")
    except psutil.NoSuchProcess:
        print(f"进程 {process.pid} 不存在。")
    except Exception as e:
        print(f"关闭 {module_name} 服务时发生错误: {e}")