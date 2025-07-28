# 启动服务

import os, uvicorn, logging
from vllm import LLM, SamplingParams
from vllm.entrypoints.openai.api_server import build_app

# 如果你想换模型，在这里改
MODEL = os.getenv("MODEL", "microsoft/DialoGPT-small")   # 小模型快下载
llm_engine = LLM(model=MODEL, tensor_parallel_size=1)    # 单卡即可

# 构建 FastAPI 应用
app = build_app(llm_engine)

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )