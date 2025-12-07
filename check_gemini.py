import google.generativeai as genai
import os

# ⚠️⚠️⚠️ 请务必在这里填入你的 API Key
api_key = "AIzaSyBBdAG3a9Ng9djcpFkCLITX_SMIDltnx4U" 

genai.configure(api_key=api_key)

print("正在查询可用模型列表...")
try:
    available_models = []
    for m in genai.list_models():
        # 我们只关心能生成文本的模型
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ 发现可用模型: {m.name}")
            available_models.append(m.name)
            
    if not available_models:
        print("❌ 未找到任何支持 generateContent 的模型。请检查 API Key 是否开通了 Generative Language API。")
except Exception as e:
    print(f"❌ 查询失败: {e}")