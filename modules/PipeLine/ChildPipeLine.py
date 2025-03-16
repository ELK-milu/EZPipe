import queue
from typing import Dict, Any
from modules.PipeLine.BasePipeLine import PipeLine

# 添加多输出支持
class MultiOutputPipeLine(PipeLine):
    def get_all_outputs(self, user: str) -> Dict[str, Any]:
        """获取各模块中间结果"""
        return {
            module.__name__: module().GetOutPut(user)
            for module in self.modules
        }

# 添加超时机制
class TimeoutPipeLine(PipeLine):
    def Output(self, user: str, timeout: float = 10.0) -> Any:
        try:
            return super().Output(user).get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("获取输出超时")