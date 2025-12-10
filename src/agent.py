"""
ChiseLLM Agent - 使用统一的 LLM Provider 接口

重构版本，支持多种 LLM API。
"""

import re
import time
from src.llm_provider import LLMProvider, create_provider
from src.reflect_env import reflect


class ChiselAgent:
    """Chisel 代码生成 Agent"""
    
    def __init__(self, provider: LLMProvider):
        """
        初始化 ChiselAgent
        
        Args:
            provider: LLM Provider 实例 (通过 create_provider 创建)
        """
        self.provider = provider
    
    @classmethod
    def from_config(
        cls,
        provider_type: str,
        api_key: str,
        model_name: str = None,
        base_url: str = None
    ) -> "ChiselAgent":
        """
        从配置创建 ChiselAgent (便捷方法)
        
        Args:
            provider_type: Provider 类型 (gemini, openai, qwen, deepseek, claude, custom)
            api_key: API Key
            model_name: 模型名称 (可选)
            base_url: API Base URL (仅对 custom 类型必需)
        
        Returns:
            ChiselAgent 实例
        """
        provider = create_provider(
            provider_type=provider_type,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url
        )
        return cls(provider=provider)

    def extract_code(self, text: str) -> str:
        """从 LLM 响应中提取 Scala/Chisel 代码"""
        match = re.search(r"```scala(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def infer_module_name(self, code: str) -> str:
        """从代码中推断模块名称"""
        match = re.search(r"class\s+(\w+)\s+extends\s+Module", code)
        if match:
            return match.group(1)
        return "TestModule"

    def run_loop(self, user_request: str, max_retries: int = 3):
        """
        核心生成-修复闭环
        
        Yields:
            dict: 包含 status, msg, code, result, raw_response 等字段
        """
        
        # 1. 首次生成
        yield {"status": "generating", "msg": "正在调用 LLM 生成代码..."}
        
        try:
            content = self.provider.send_message(user_request)
        except Exception as e:
            yield {"status": "error", "msg": f"API 调用失败: {str(e)}"}
            return

        for attempt in range(1, max_retries + 1):
            code = self.extract_code(content)
            module_name = self.infer_module_name(code)
            
            # 2. 反射验证
            yield {"status": "reflecting", "msg": f"正在验证模块 `{module_name}` (第 {attempt} 次尝试)..."}
            
            result = reflect(
                chisel_code_string=code,
                module_name=module_name,
                testbench_path=None,
                silent=True
            )

            # 3. 成功判定
            if result['elaborated']: 
                yield {"status": "success", "code": code, "result": result, "raw_response": content}
                return
            
            # 4. 失败处理
            error_msg = result['error_log'] if result['error_log'] else "Unknown Error"
            short_error = error_msg[:2000] + "..." if len(error_msg) > 2000 else error_msg
            
            yield {"status": "fixing", "msg": f"发现错误 (阶段: {result['stage']})，正在让 LLM 自愈..."}
            
            feedback = f"""
            你生成的代码在 {result['stage']} 阶段验证失败。
            错误日志如下:
            {short_error}
            
            请分析错误原因，并修复代码。请输出完整的修复后代码。
            """
            
            # 将错误反馈发回给模型
            try:
                content = self.provider.send_message(feedback)
            except Exception as e:
                yield {"status": "error", "msg": f"修复过程 API 调用失败: {str(e)}"}
                return

        # 在循环结束后，把最后一次的 result 和 code 也传出去
        yield {
            "status": "failed", 
            "msg": "达到最大重试次数，修复失败。请查看右侧验证报告。", 
            "result": result, 
            "code": code
        }