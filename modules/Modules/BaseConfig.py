from typing import Any
from pydantic import BaseModel

# 本来打算用这个代替pipelineAPI的入参，但是想想算了，后续有需要再重构吧
class BaseConfig(BaseModel):
    streamly: bool = False
    user: str
    Input: Any  # 允许子类通过继承扩展字段