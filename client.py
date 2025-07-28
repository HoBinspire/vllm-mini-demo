# 客户端调用示例

from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy")

resp = client.chat.completions.create(
    model="microsoft/DialoGPT-small",
    messages=[{"role": "user", "content": "用一句话介绍 vLLM"}],
    max_tokens=50
)
print(resp.choices[0].message.content)