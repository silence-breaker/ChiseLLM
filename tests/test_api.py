"""
API 连接测试脚本
"""
import sys
sys.path.insert(0, '.')

from src.llm_provider import create_provider
import toml

# 读取 secrets
print("读取配置文件...")
with open('.streamlit/secrets.toml', 'r') as f:
    secrets = toml.load(f)

api_key = secrets['default']['api_key']
base_url = secrets['default']['base_url']
model_name = secrets['default']['model_name']

print(f'测试 API 配置:')
print(f'  Base URL: {base_url}')
print(f'  Model: {model_name}')
print()

# 创建 provider 并测试
print("创建 Provider...")
provider = create_provider(
    provider_type='custom',
    api_key=api_key,
    model_name=model_name,
    base_url=base_url
)

print('发送测试请求: 你好，请回复OK')
response = provider.send_message('你好，请回复OK')
print(f'响应: {response[:200]}')
print()
print('✅ API 连接测试成功！')
