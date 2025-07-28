# vLLM 简介
> vLLM 不支持原生 windows 系统.

## vLLM 是什么？一句话概括
vLLM 是一个把大模型推理做成“高性能、低成本、易落地”的开源引擎——它能让 Llama-3-70B 这样的巨兽在单张 A100 上跑出 10× 于传统框架的 **QPS**，并且一条命令就能开成兼容 OpenAI 的 API 服务。

## 1. 诞生背景
- **发起方**：UC Berkeley Sky Computing Lab（2023 开源）。
- **初衷**：解决 LLM 部署的三大痛点——==**GPU 内存浪费、请求延迟高、吞吐量低**==。

## 2. 技术核心：PagedAttention
- **原理**：把 KV-Cache 拆成固定大小的“页”，像操作系统一样动态映射，内存碎片降低 3-5 倍，==**显存利用率提升 3-5 倍**==。
- **效果**：同样显存，==**并发量提升 10×**==；同样并发，==显存节省 60%==。

> 一句话总结：
> vLLM = PagedAttention + 连续批处理 + 量化/并行

## 3. 关键特性速览

| 特性           | 一句话说明                                                         |
|----------------|--------------------------------------------------------------------|
| 连续批处理     | 请求随到随算，避免“整批等末尾”                                     |
| 分布式并行     | 原生支持张量并行 & 流水线并行，70B 可跨 8×A100 线性扩展            |
| 量化友好       | 内置 GPTQ/AWQ/FP8，INT4 下 70B 能在 24 GB 显存跑                   |
| 多 LoRA        | 同一张卡同时加载 N 个 LoRA 权重，服务多租户                        |
| OpenAI 兼容    | vllm serve 即开即用，SDK 无需改一行代码                            |

## 4. vLLM 的创新点

### 显存层：PagedAttention（≠ 单纯分页）
- **传统做法**：一次性为每个序列申请连续的 KV Cache 区域 → 序列长度未知 → 只能按最大长度预留 → 80% 以上显存被浪费。
- **vLLM 做法**：把 KV Cache 切成固定大小的 block，用逻辑→物理映射表（Block Table）动态分配；
  - 同一块物理显存可被不同序列共享（prompt 相同前缀时）；
  - 当序列分叉时，再触发 copy-on-write 复制新块；
  - 显存碎片从 50% 降到 <4%。
- 这不仅是“分页”，而是引入了**引用计数 + 写时复制 + 共享**的完整内存管理策略。

### 调度层：Token-level 微调度器
- **连续批处理（Continuous Batching）**：
  - 传统框架要等整批序列都结束才换下一批；vLLM 每生成一个 token 就重新评估显存，把新请求或已完成的序列即时塞进 GPU，吞吐量提升 8–24×。
- **抢占/恢复机制**：
  - 显存吃紧时，vLLM 可以把后到请求的 KV block 换出到 CPU（类似 OS swap），完成后换回来，保证高优先级请求先完成。

### 执行层：定制化 CUDA Kernel & 并行
- 自研 PagedAttention CUDA kernel，原生支持非连续地址 gather/scatter；
- 支持 Tensor Parallel + Pipeline Parallel，70B 模型可在多卡线性扩展；
- 集成 FlashAttention-2、GPTQ/AWQ 量化、LoRA 热插拔等工程优化。

# 5.最小demo示例
## 📁 项目目录
```
vllm-mini-demo/
├── app.py               # 启动服务
├── client.py            # 客户端调用示例
├── requirements.txt     # 依赖
├── .env.example         # 可选：放模型路径
└── README.md            # 本页缩减版
```

## 1️⃣ requirements.txt
```Text
vllm>=0.4.2          # 主框架
openai>=1.0          # 客户端 SDK
python-dotenv>=1.0   # 读取 .env（可选）
```

一键安装依赖：
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 2️⃣ app.py （3 行核心，其余是日志）
```python
# app.py
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
```

## 3️⃣ client.py （1 行调用）
```python
# client.py
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

resp = client.chat.completions.create(
    model="microsoft/DialoGPT-small",
    messages=[{"role": "user", "content": "用一句话介绍 vLLM"}],
    max_tokens=50
)
print(resp.choices[0].message.content)
```

## 4️⃣ 启动 & 验证
```bash
# 1. 启动服务（首次会自动下载模型）
python app.py
# 2. 另开终端
python client.py
```
终端会输出 vLLM 生成的回答，例如：
vLLM 是一个高性能、易部署的大模型推理引擎。

## 5️⃣ 体验并发（可选）
```bash
# 50 并发请求，看吞吐量
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"microsoft/DialoGPT-small","messages":[{"role":"user","content":"Hi"}],"max_tokens":32}' \
  &  # 复制多条即可
```

## 6️⃣ 一键脚本（懒人版）
```bash
git clone https://github.com/yourname/vllm-mini-demo.git
cd vllm-mini-demo
python app.py
```