from typing import Any
from pydantic import BaseModel

class BaseConfig(BaseModel):
    streamly: bool = False
    user: str
    Input: Any  # 允许子类通过继承扩展字段