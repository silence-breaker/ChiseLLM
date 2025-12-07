import os
import re
import json
from openai import OpenAI
# 引用你现有的反射环境核心函数
from src.reflect_env import reflect 

# 系统提示词：注入版本锁定和语法约束
SYSTEM_PROMPT = """
你是一位 Chisel 硬件设计专家。你的任务是根据用户需求编写 Chisel 代码。
【严重警告：版本与语法约束】
1. 必须使用 Chisel 6.0.0 和 Scala 2.13.12 语法。
2. 必须导入: `import chisel3._` 和 `import chisel3.util._`
3. 模块必须继承 `Module`。
4. IO 必须包裹在 `IO(...)` 中，例如 `val io = IO(...)`。
5. 所有代码必须包含在一个 Markdown 代码块中 (```scala ... ```)。
6. 仅输出 Module 定义，不要包含 package 声明。
"""

class ChiselAgent:
    def __init__(self, api_key, base_url, model_name):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def extract_code(self, text):
        """从回答中提取 scala 代码块"""
        match = re.search(r"```scala(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def infer_module_name(self, code):
        """尝试从代码中正则匹配 class ModuleName"""
        match = re.search(r"class\s+(\w+)\s+extends\s+Module", code)
        if match:
            return match.group(1)
        return "TestModule" # 默认回退名

    def run_loop(self, user_request, max_retries=3):
        """
        核心生成-修复闭环
        """
        # 1. 首次请求
        self.history.append({"role": "user", "content": user_request})
        
        for attempt in range(1, max_retries + 1):
            # --- 阶段 A: 生成 ---
            yield {"status": "generating", "msg": f"正在进行第 {attempt} 次生成 (调用 {self.model_name})..."}
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.history,
                    temperature=0.2 # 代码生成需要低随机性
                )
            except Exception as e:
                yield {"status": "error", "msg": f"API 调用失败: {str(e)}"}
                return

            content = response.choices[0].message.content
            code = self.extract_code(content)
            module_name = self.infer_module_name(code)
            
            # --- 阶段 B: 反射验证 ---
            yield {"status": "reflecting", "msg": f"正在验证模块 `{module_name}` (编译 & 阐述)..."}
            
            # 调用你的核心 reflect 函数
            # 注意：目前我们没有自动生成 testbench，所以 testbench_path=None
            # 这意味着它会验证 "Compile" 和 "Elaborate" (能否转成 Verilog)
            result = reflect(
                chisel_code_string=code,
                module_name=module_name,
                testbench_path=None 
            )

            # --- 阶段 C: 决策 ---
            if result['elaborated']: 
                # 成功：编译和阐述都通过
                yield {"status": "success", "code": code, "result": result, "raw_response": content}
                self.history.append({"role": "assistant", "content": content})
                return
            
            # 失败：准备下一轮修复
            error_msg = result['error_log'] if result['error_log'] else "Unknown Error"
            # 截断过长的错误日志，防止 Prompt 溢出
            short_error = error_msg[:2000] + "..." if len(error_msg) > 2000 else error_msg
            
            yield {"status": "fixing", "msg": f"发现错误 (阶段: {result['stage']})，正在尝试自愈..."}
            
            feedback = f"""
            你生成的代码在 {result['stage']} 阶段验证失败。
            错误日志如下:
            {short_error}
            
            请分析错误原因，并修复代码。请输出完整的修复后代码。
            """
            
            # 将错误反馈加入对话历史
            self.history.append({"role": "assistant", "content": content})
            self.history.append({"role": "user", "content": feedback})

        yield {"status": "failed", "msg": "达到最大重试次数，修复失败。"}