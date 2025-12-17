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

【复位信号处理 - 极其重要】
⚠️ **禁止同时使用 RegInit 和 io.reset！** 这是一个常见的严重错误！

- `RegInit(0.U)` 会自动连接到模块的**隐式 reset 信号**，无需额外处理
- 如果使用 `RegInit`，**不要**在 IO 中定义 `reset` 输入
- 如果用户要求"同步复位"且想用自定义复位信号，应该用 `Reg` + `when(io.reset)` 逻辑

✅ 正确示例1 (使用隐式复位):
```scala
class MyReg extends Module {
  val io = IO(new Bundle {
    val d = Input(UInt(8.W))
    val q = Output(UInt(8.W))
  })
  val reg = RegInit(0.U(8.W))  // 自动使用隐式 reset
  reg := io.d
  io.q := reg
}
```

✅ 正确示例2 (使用自定义复位信号):
```scala
class MyReg extends Module {
  val io = IO(new Bundle {
    val d = Input(UInt(8.W))
    val q = Output(UInt(8.W))
    val sync_reset = Input(Bool())  // 自定义复位信号
  })
  val reg = Reg(UInt(8.W))  // 注意：用 Reg 而不是 RegInit
  when(io.sync_reset) {
    reg := 0.U
  }.otherwise {
    reg := io.d
  }
  io.q := reg
}
```

❌ 错误示例 (禁止这样写！):
```scala
class MyReg extends Module {
  val io = IO(new Bundle {
    val reset = Input(Bool())  // ❌ 错误！不要与 RegInit 一起使用
    val d = Input(UInt(8.W))
    val q = Output(UInt(8.W))
  })
  val reg = RegInit(0.U(8.W))  // ❌ RegInit 已经有隐式 reset
  when(io.reset) { reg := 0.U }  // ❌ 这会导致混淆
}
```
"""


TESTBENCH_SYSTEM_PROMPT = """你是一位硬件验证专家，擅长为 Chisel/Verilog 模块编写 C++ Testbench (基于 Verilator)。

【Testbench 编写规范 - 必须严格遵守，否则仿真会失败】

⚠️ **禁止事项**:
- 禁止定义 struct、class、typedef
- 禁止使用 `stdendl`，必须用 `std::endl`
- 禁止修改 VCD 文件名，必须是 `waveform.vcd`

✅ **必须遵守**:
1. 主循环必须至少运行 **50 个时钟周期**
2. 时钟必须在每个周期内翻转两次 (0→1→0)
3. 复位阶段至少 5 个时钟周期
4. 测试逻辑直接写在 main 函数中，不要定义额外的结构体

【标准 Testbench 模板 - 严格按此格式，只修改测试逻辑部分】
```cpp
#include "V{MODULE_NAME}.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <iostream>

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(true);
    
    V{MODULE_NAME}* top = new V{MODULE_NAME};
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open("waveform.vcd");
    
    int sim_time = 0;
    int errors = 0;
    
    // ===== 复位阶段 (5个时钟周期) =====
    top->reset = 1;
    for (int i = 0; i < 10; i++) {
        top->clock = (i % 2);
        top->eval();
        tfp->dump(sim_time++);
    }
    top->reset = 0;
    
    // ===== 测试阶段 (至少50个时钟周期) =====
    for (int cycle = 0; cycle < 50; cycle++) {
        // 时钟下降沿
        top->clock = 0;
        // 在这里设置输入信号
        top->eval();
        tfp->dump(sim_time++);
        
        // 时钟上升沿
        top->clock = 1;
        top->eval();
        tfp->dump(sim_time++);
        
        // 在这里检查输出信号
    }
    
    tfp->close();
    delete tfp;
    delete top;
    
    if (errors == 0) {
        std::cout << "TEST PASSED" << std::endl;
        return 0;
    } else {
        std::cout << "TEST FAILED with " << errors << " errors" << std::endl;
        return 1;
    }
}
```

请根据模块的 IO 接口生成简单直接的测试代码。
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
