"""Quick DeepSeek API connectivity test"""
from openai import OpenAI
import sys

API_KEY = sys.argv[1] if len(sys.argv) > 1 else None
if not API_KEY:
    print("No API key provided")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com", timeout=60)
try:
    r = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": "回复：连接成功"}],
        max_tokens=20,
    )
    print("✅ DeepSeek API 连通:", r.choices[0].message.content)
except Exception as e:
    print("❌ 连接失败:", type(e).__name__, str(e)[:200])
