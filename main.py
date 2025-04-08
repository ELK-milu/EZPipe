import asyncio
import uvicorn
from fastapi import FastAPI
from modules.utils.logger import setup_root_logger
from modules.BaseModule import BaseModule
from modules.Modules.LLM.DeepSeek_LLM_Module import DeepSeek_LLM_Module
from modules.Modules.TTS.TTS_Module import TTS_Module

# 初始化全局logger
setup_root_logger()

# 创建FastAPI应用
app = FastAPI()

# 创建模块实例
llm_module = DeepSeek_LLM_Module()
tts_module = TTS_Module()

# 注册模块路由
app.include_router(llm_module.router)
app.include_router(tts_module.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 