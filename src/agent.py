"""
ChiseLLM Agent - 使用统一的 LLM Provider 接口

重构版本，支持多种 LLM API。
新增: 自动生成 Testbench 并进行波形仿真
"""

import re
import time
import tempfile
import os
from src.llm_provider import LLMProvider, create_provider, TESTBENCH_SYSTEM_PROMPT
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
        # 保存原始系统提示词
        self._original_system_prompt = provider.system_prompt
    
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

    def extract_code(self, text: str, lang: str = "scala") -> str:
        """从 LLM 响应中提取代码"""
        pattern = rf"```{lang}(.*?)```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # 尝试通用代码块
        match = re.search(r"```(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def extract_cpp_code(self, text: str) -> str:
        """从 LLM 响应中提取 C++ 代码"""
        # 尝试 cpp 标记
        match = re.search(r"```cpp(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            code = match.group(1).strip()
        else:
            # 尝试 c++ 标记
            match = re.search(r"```c\+\+(.*?)```", text, re.DOTALL | re.IGNORECASE)
            if match:
                code = match.group(1).strip()
            else:
                # 尝试 c 标记
                match = re.search(r"```c(.*?)```", text, re.DOTALL | re.IGNORECASE)
                if match:
                    code = match.group(1).strip()
                else:
                    code = text
        
        # 后处理：修复常见的 LLM 生成错误
        code = self._fix_cpp_common_errors(code)
        return code
    
    def _fix_cpp_common_errors(self, code: str) -> str:
        """修复 LLM 生成 C++ 代码时的常见错误"""
        # 修复 stdendl -> std::endl
        code = re.sub(r'\bstdendl\b', 'std::endl', code)
        # 修复 std:endl -> std::endl (单冒号)
        code = re.sub(r'\bstd:endl\b', 'std::endl', code)
        # 修复 std::end -> std::endl (缺少 l)
        code = re.sub(r'\bstd::end\b(?!l)', 'std::endl', code)
        return code

    def infer_module_name(self, code: str) -> str:
        """从代码中推断模块名称"""
        match = re.search(r"class\s+(\w+)\s+extends\s+Module", code)
        if match:
            return match.group(1)
        return "TestModule"

    def generate_testbench(self, chisel_code: str, module_name: str, verilog_code: str = None, error_feedback: str = None):
        """
        使用 LLM 生成 C++ Testbench
        
        Args:
            chisel_code: Chisel 源代码
            module_name: 模块名称
            verilog_code: 生成的 Verilog 代码 (可选，用于更精确的 testbench)
            error_feedback: 上次生成的错误反馈 (用于修复)
        
        Returns:
            tuple: (testbench_code, raw_response) 或 (None, error_msg)
        """
        # 构建 testbench 生成请求
        if error_feedback:
            # 修复模式
            tb_request = f"""你之前生成的 Testbench 代码编译/运行失败，请根据以下错误信息修复：

【错误日志】:
{error_feedback}

【模块名称】: {module_name}

【Chisel 代码】:
```scala
{chisel_code}
```

请修复 Testbench 代码，确保：
1. 代码能够正确编译
2. 不要定义复杂的 struct 或 class
3. 使用 std::endl 而不是 stdendl
4. VCD 文件命名为 waveform.vcd

请输出完整的修复后 C++ 代码，包含在 ```cpp ... ``` 代码块中。
"""
        else:
            # 首次生成模式
            tb_request = f"""请为以下 Chisel 模块生成一个完整的 C++ Testbench (基于 Verilator)。

【模块名称】: {module_name}

【Chisel 代码】:
```scala
{chisel_code}
```
"""
            if verilog_code:
                tb_request += f"""
【生成的 Verilog 代码】:
```verilog
{verilog_code}
```
"""
            tb_request += """
请生成一个简单直接的 C++ Testbench，要求:
1. 不要定义复杂的 struct 或 class，直接在 main 中写测试逻辑
2. VCD 波形文件命名为 waveform.vcd
3. 使用 std::endl 进行换行
4. 包含复位逻辑和基本测试
5. 输出 TEST PASSED 或 TEST FAILED

请将代码包含在 ```cpp ... ``` 代码块中。
"""
        
        # 临时切换系统提示词
        original_history = self.provider.history.copy()
        self.provider.reset_chat()
        self.provider.system_prompt = TESTBENCH_SYSTEM_PROMPT
        
        try:
            tb_response = self.provider.send_message(tb_request)
            tb_code = self.extract_cpp_code(tb_response)
            return tb_code, tb_response
        except Exception as e:
            return None, str(e)
        finally:
            # 恢复原始状态
            self.provider.system_prompt = self._original_system_prompt
            self.provider.history = original_history

    def run_loop(self, user_request: str, max_retries: int = 3, max_tb_retries: int = 3, auto_testbench: bool = True):
        """
        核心生成-修复-仿真闭环
        
        Args:
            user_request: 用户需求描述
            max_retries: Chisel 代码最大重试次数
            max_tb_retries: Testbench 最大重试次数
            auto_testbench: 是否自动生成 testbench 并进行仿真
        
        Yields:
            dict: 包含 status, msg, code, result, raw_response, testbench_code 等字段
        """
        
        # 1. 首次生成 Chisel 代码
        yield {"status": "generating", "msg": "正在调用 LLM 生成 Chisel 代码..."}
        
        try:
            content = self.provider.send_message(user_request)
        except Exception as e:
            yield {"status": "error", "msg": f"API 调用失败: {str(e)}"}
            return

        # 阶段 1: 编译和阐述循环
        final_code = None
        final_result = None
        
        for attempt in range(1, max_retries + 1):
            code = self.extract_code(content)
            module_name = self.infer_module_name(code)
            
            # 2. 反射验证 (编译 + 阐述)
            yield {"status": "reflecting", "msg": f"正在验证模块 `{module_name}` (第 {attempt} 次尝试)..."}
            
            result = reflect(
                chisel_code_string=code,
                module_name=module_name,
                testbench_path=None,
                silent=True
            )

            # 3. 成功判定 (编译和阐述通过)
            if result['elaborated']:
                final_code = code
                final_result = result
                yield {"status": "elaboration_passed", "msg": f"✅ 模块 `{module_name}` 编译阐述成功！"}
                break
            
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
            
            try:
                content = self.provider.send_message(feedback)
            except Exception as e:
                yield {"status": "error", "msg": f"修复过程 API 调用失败: {str(e)}"}
                return

        # 如果编译阐述失败
        if not final_code or not final_result or not final_result.get('elaborated'):
            yield {
                "status": "failed", 
                "msg": "达到最大重试次数，编译/阐述失败。", 
                "result": result, 
                "code": code
            }
            return
        
        # 阶段 2: 自动生成 Testbench 并仿真 (带修复循环)
        if auto_testbench:
            testbench_code = None
            tb_error_feedback = None
            
            for tb_attempt in range(1, max_tb_retries + 1):
                # 生成或修复 Testbench
                if tb_attempt == 1:
                    yield {"status": "generating_tb", "msg": "正在生成 C++ Testbench..."}
                else:
                    yield {"status": "fixing_tb", "msg": f"正在修复 Testbench (第 {tb_attempt} 次尝试)..."}
                
                tb_code, tb_response = self.generate_testbench(
                    final_code, 
                    module_name, 
                    final_result.get('generated_verilog'),
                    error_feedback=tb_error_feedback
                )
                
                if tb_code is None:
                    yield {"status": "tb_error", "msg": f"Testbench 生成失败: {tb_response}"}
                    # 返回无仿真的结果
                    yield {
                        "status": "success", 
                        "code": final_code, 
                        "result": final_result, 
                        "raw_response": content,
                        "testbench_code": None,
                        "msg": "代码验证成功，但 Testbench 生成失败"
                    }
                    return
                
                yield {"status": "tb_generated", "msg": "Testbench 生成完成，正在编译仿真..."}
                
                # 创建临时 testbench 文件并运行仿真
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
                    f.write(tb_code)
                    tb_path = f.name
                
                try:
                    # 运行 reflect，带上 testbench
                    sim_result = reflect(
                        chisel_code_string=final_code,
                        module_name=module_name,
                        testbench_path=tb_path,
                        silent=True
                    )
                    
                    # 检查仿真结果
                    sim_error = sim_result.get('error_log')
                    sim_stage = sim_result.get('stage')
                    
                    # 判断是否成功
                    if sim_result.get('sim_passed'):
                        # 仿真成功！
                        testbench_code = tb_code
                        final_result['sim_passed'] = True
                        final_result['vcd_content'] = sim_result.get('vcd_content')
                        final_result['testbench_code'] = tb_code
                        yield {"status": "sim_passed", "msg": "✅ 仿真测试通过！"}
                        break
                    elif sim_stage == "passed" or sim_result.get('vcd_content'):
                        # 仿真运行了但测试失败（逻辑错误），仍然保留结果
                        testbench_code = tb_code
                        final_result['sim_passed'] = False
                        final_result['vcd_content'] = sim_result.get('vcd_content')
                        final_result['testbench_code'] = tb_code
                        final_result['sim_error_log'] = sim_error
                        yield {"status": "sim_failed", "msg": f"⚠️ 仿真运行完成但测试失败 (可查看波形)"}
                        break
                    else:
                        # 编译或运行时错误，需要修复
                        tb_error_feedback = sim_error[:3000] if sim_error else "Unknown error"
                        yield {"status": "tb_compile_error", "msg": f"Testbench 编译/运行失败 (第 {tb_attempt} 次)，准备修复..."}
                        
                        if tb_attempt >= max_tb_retries:
                            # 达到最大重试次数
                            testbench_code = tb_code
                            final_result['sim_passed'] = False
                            final_result['sim_error_log'] = sim_error
                            final_result['sim_stage'] = sim_stage
                            final_result['testbench_code'] = tb_code
                            yield {"status": "tb_fix_failed", "msg": f"⚠️ Testbench 修复失败，已达最大重试次数"}
                            break
                        
                finally:
                    # 清理临时文件
                    if os.path.exists(tb_path):
                        os.unlink(tb_path)
            
            final_result['testbench_code'] = testbench_code
        
        # 最终成功
        yield {
            "status": "success", 
            "code": final_code, 
            "result": final_result, 
            "raw_response": content,
            "testbench_code": final_result.get('testbench_code')
        }