import os
from typing import List, Type, Any

from modules.Modules.BaseModule import BaseModule
# PipeLine只应处理调用服务的API模块，不要包含需要长期保持连接的模块，做到即用即拿
class PipeLine:
    def __init__(self, modules: List[Type[BaseModule]]):
        self.modules = [m() for m in modules]  # 创建实例列表
        self._link_instances()
        self.user = None
        # 验证管线连接是否正确
        print(self.Validate())

    def _link_instances(self):
        """连接实例链"""
        for i in range(len(self.modules)-1):
            self.modules[i].next_model = self.modules[i+1]

    def _validate_pipeline(self):
        """内部验证方法"""
        # 1. 检查空管道
        if not self.modules:
            raise ValueError("Pipeline cannot be empty")

        # 2. 检查类型连续性
        for i in range(len(self.modules) - 1):
            curr = self.modules[i]
            next_mod = self.modules[i + 1]

            curr_output = curr.process.__annotations__['return']
            next_input = next_mod.process.__annotations__['input_data']

            if curr_output != next_input:
                raise TypeError(
                    f"Type mismatch: {type(curr).__name__} outputs {curr_output} "
                    f"but {type(next_mod).__name__} expects {next_input}"
                )

    def Validate(self) -> str:
        """验证并返回管道状态"""
        status = []

        # 基础验证
        try:
            self._validate_pipeline()
            status.append("✅ Pipeline validation passed")
        except Exception as e:
            status.append(f"❌ Validation failed: {str(e)}")

        # 管线结构展示
        pipe_structure = " -> ".join(
            [f"{type(inst).__name__}" for inst in self.modules]
        )
        status.append(f"Current pipeline: {pipe_structure}")

        # 详细类型信息
        type_details = []
        for inst in self.modules:
            sig = inst.process.__annotations__
            type_details.append(
                f"{type(inst).__name__} "
                f"(in: {sig['input_data']}, out: {sig['return']})"
            )
        status.append("Type details:\n" + "\n".join(type_details))
        status.append("#################################################")
        return "\n".join(status)

    @classmethod
    def create_pipeline(cls, *modules: Type[BaseModule]) -> 'PipeLine':
        """类方法创建管道实例"""
        return cls(list(modules))  # 将可变参数转换为列表

    def GetService(self, streamly: bool, user: str, input_data: Any):
        """统一服务入口"""
        if not self.modules:
            raise ValueError("Unconfigured pipeline")
        self.user = user
        self.modules[0].GetService(streamly, user, input_data)
        self.WaitForCompletion(user)

    async def Output(self, user: str) -> Any:
        """统一输出入口（修复版本）"""
        return self.modules[-1].GetOutPut(user)

    def Destroy(self):
        """统一销毁资源"""
        for module in self.modules:
            module._cleanup(self.user)

    def WaitForCompletion(self, user: str, timeout: float = None):
        """等待指定用户的所有处理线程完成"""
        for module in self.modules:
            if user in module.user_threads:
                module.user_threads[user].join(timeout)
                if module.user_threads[user].is_alive():
                    raise TimeoutError(f"Module {type(module).__name__} timed out")