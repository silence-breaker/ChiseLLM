"""
ChiseLLM 多 API Provider 统一接口

支持的 API 类型：
- Google Gemini (google-generativeai SDK)
- OpenAI / Qwen / DeepSeek (OpenAI 兼容格式)
- Anthropic Claude (anthropic SDK)

作者: ChiseLLM Project
日期: 2025-12-09
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
import time


# ==================== 系统提示词 ====================
CHISEL_SYSTEM_PROMPT = """你是一位 Chisel 硬件设计专家。你的任务是根据用户需求编写 Chisel 代码。
【严重警告：版本与语法约束】
1. 必须使用 Chisel 6.0.0 和 Scala 2.13.12 语法。
2. 必须导入: `import chisel3._` 和 `import chisel3.util._`
3. 模块必须继承 `Module`。
4. IO 必须包裹在 `IO(...)` 中，例如 `val io = IO(...)`。
5. 所有代码必须包含在一个 Markdown 代码块中 (```scala ... ```)。
6. 仅输出 Module 定义，不要包含 package 声明。
"""


# ==================== Provider 配置 ====================
PROVIDER_CONFIGS = {
    "gemini": {
        "name": "Google Gemini",
        "models": ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"],
        "default_model": "gemini-2.0-flash-exp",
        "requires_base_url": False,
    },
    "openai": {
        "name": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "requires_base_url": False,
    },
    "qwen": {
        "name": "Qwen (通义千问)",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max"],
        "default_model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "requires_base_url": False,
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": ["deepseek-chat", "deepseek-coder"],
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "requires_base_url": False,
    },
    "claude": {
        "name": "Anthropic Claude",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "default_model": "claude-3-5-sonnet-20241022",
        "requires_base_url": False,
    },
    "custom": {
        "name": "自定义 OpenAI 兼容",
        "models": [],
        "default_model": "",
        "requires_base_url": True,
    },
}


# ==================== 抽象基类 ====================
class LLMProvider(ABC):
    """LLM Provider 抽象基类"""
    
    def __init__(self, api_key: str, model_name: str, system_prompt: str = CHISEL_SYSTEM_PROMPT):
        self.api_key = api_key
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.history: List[Dict[str, str]] = []
    
    @abstractmethod
    def send_message(self, message: str) -> str:
        """发送消息并返回响应"""
        pass
    
    def reset_chat(self):
        """重置对话历史"""
        self.history = []
    
    def _handle_rate_limit(self, retry_count: int = 3, wait_seconds: int = 5):
        """处理速率限制的通用方法"""
        for i in range(retry_count):
            try:
                return True
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    if i < retry_count - 1:
                        time.sleep(wait_seconds)
                        continue
                raise e
        return False


# ==================== Gemini Provider ====================
class GeminiProvider(LLMProvider):
    """Google Gemini Provider (使用原生 SDK)"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        super().__init__(api_key, model_name)
        
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=self.system_prompt
        )
        self.chat = self.model.start_chat(history=[])
    
    def send_message(self, message: str) -> str:
        try:
            response = self.chat.send_message(message)
            return response.text
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
                response = self.chat.send_message(message)
                return response.text
            raise e
    
    def reset_chat(self):
        super().reset_chat()
        self.chat = self.model.start_chat(history=[])


# ==================== OpenAI 兼容 Provider ====================
class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 Provider (支持 OpenAI, Qwen, DeepSeek, 自定义)"""
    
    def __init__(
        self, 
        api_key: str, 
        model_name: str,
        base_url: str = "https://api.openai.com/v1"
    ):
        super().__init__(api_key, model_name)
        self.base_url = base_url
        
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        
        # 初始化历史
        self.history = [{"role": "system", "content": self.system_prompt}]
    
    def send_message(self, message: str) -> str:
        self.history.append({"role": "user", "content": message})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.history
            )
            assistant_message = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.history
                )
                assistant_message = response.choices[0].message.content
                self.history.append({"role": "assistant", "content": assistant_message})
                return assistant_message
            raise e
    
    def reset_chat(self):
        super().reset_chat()
        self.history = [{"role": "system", "content": self.system_prompt}]


# ==================== Claude Provider ====================
class ClaudeProvider(LLMProvider):
    """Anthropic Claude Provider"""
    
    def __init__(self, api_key: str, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(api_key, model_name)
        
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def send_message(self, message: str) -> str:
        self.history.append({"role": "user", "content": message})
        
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                system=self.system_prompt,
                messages=self.history
            )
            assistant_message = response.content[0].text
            self.history.append({"role": "assistant", "content": assistant_message})
            return assistant_message
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=4096,
                    system=self.system_prompt,
                    messages=self.history
                )
                assistant_message = response.content[0].text
                self.history.append({"role": "assistant", "content": assistant_message})
                return assistant_message
            raise e


# ==================== 工厂函数 ====================
def create_provider(
    provider_type: str,
    api_key: str,
    model_name: Optional[str] = None,
    base_url: Optional[str] = None
) -> LLMProvider:
    """
    创建 LLM Provider 实例
    
    Args:
        provider_type: Provider 类型 (gemini, openai, qwen, deepseek, claude, custom)
        api_key: API Key
        model_name: 模型名称 (可选，默认使用该 Provider 的默认模型)
        base_url: API Base URL (仅对 custom 类型必需)
    
    Returns:
        LLMProvider 实例
    """
    config = PROVIDER_CONFIGS.get(provider_type)
    if not config:
        raise ValueError(f"Unknown provider type: {provider_type}")
    
    # 确定模型名称
    if not model_name:
        model_name = config["default_model"]
    
    # 根据类型创建 Provider
    if provider_type == "gemini":
        return GeminiProvider(api_key=api_key, model_name=model_name)
    
    elif provider_type == "claude":
        return ClaudeProvider(api_key=api_key, model_name=model_name)
    
    elif provider_type in ["openai", "qwen", "deepseek"]:
        url = base_url or config.get("base_url", "https://api.openai.com/v1")
        return OpenAICompatibleProvider(api_key=api_key, model_name=model_name, base_url=url)
    
    elif provider_type == "custom":
        if not base_url:
            raise ValueError("Custom provider requires base_url")
        return OpenAICompatibleProvider(api_key=api_key, model_name=model_name, base_url=base_url)
    
    else:
        raise ValueError(f"Unsupported provider type: {provider_type}")


def get_available_providers() -> Dict[str, dict]:
    """获取所有可用的 Provider 配置"""
    return PROVIDER_CONFIGS
