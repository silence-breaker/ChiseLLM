from openai import OpenAI
import os

# 把你的 API Key 填在下面
api_key = "AIzaSyBBdAG3a9Ng9djcpFkCLITX_SMIDltnx4U" # ⚠️ 请在这里填入你的 Google API Key

# ⚠️ 注意这里最后的斜杠 /
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

print(f"Testing Gemini API...")
print(f"Base URL: {base_url}")

client = OpenAI(
    api_key=api_key,
    base_url=base_url
)

try:
    response = client.chat.completions.create(
        model="gemini-1.5-flash",
        messages=[{"role": "user", "content": "Hello, are you working?"}],
    )
    print("✅ Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print("❌ Failed.")
    print(e)