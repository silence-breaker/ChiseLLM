
import re
import time  # ✅ 新增
import google.generativeai as genai
from src.reflect_env import reflect
# 系统提示词 (保持不变)
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
    def __init__(self, api_key, model_name="gemini-1.5-flash"):
        # 配置 Google API
        genai.configure(api_key=api_key)
        
        # 初始化模型 (支持系统提示词)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT
        )
        
        # 初始化聊天历史
        self.chat = self.model.start_chat(history=[])

    def extract_code(self, text):
        match = re.search(r"```scala(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def infer_module_name(self, code):
        match = re.search(r"class\s+(\w+)\s+extends\s+Module", code)
        if match:
            return match.group(1)
        return "TestModule"

    def run_loop(self, user_request, max_retries=3):
        """核心生成-修复闭环"""
        
  # ... 在 run_loop 函数内部 ...
        
        # 1. 首次生成
        yield {"status": "generating", "msg": "正在调用 Gemini 原生接口生成代码..."}
        
        try:
            # ✅ 新增：简单的重试机制
            try:
                response = self.chat.send_message(user_request)
            except Exception as e:
                if "429" in str(e):
                    yield {"status": "generating", "msg": "触发限流，正在冷却 5 秒..."}
                    time.sleep(5) # 休息一下
                    response = self.chat.send_message(user_request) # 再试一次
                else:
                    raise e # 其他错误直接抛出

            content = response.text
        except Exception as e:
            yield {"status": "error", "msg": f"Google API 调用失败: {str(e)}"}
            return

        for attempt in range(1, max_retries + 1):
            code = self.extract_code(content)
            module_name = self.infer_module_name(code)
            
            # 2. 反射验证
            yield {"status": "reflecting", "msg": f"正在验证模块 `{module_name}` (第 {attempt} 次尝试)..."}
            
            result = reflect(
                chisel_code_string=code,
                module_name=module_name,
                testbench_path=None
            )

            # 3. 成功判定
            if result['elaborated']: 
                yield {"status": "success", "code": code, "result": result, "raw_response": content}
                return
            
            # 4. 失败处理
            error_msg = result['error_log'] if result['error_log'] else "Unknown Error"
            short_error = error_msg[:2000] + "..." if len(error_msg) > 2000 else error_msg
            
            yield {"status": "fixing", "msg": f"发现错误 (阶段: {result['stage']})，正在让 Gemini 自愈..."}
            
            feedback = f"""
            你生成的代码在 {result['stage']} 阶段验证失败。
            错误日志如下:
            {short_error}
            
            请分析错误原因，并修复代码。请输出完整的修复后代码。
            """
            
            # 将错误反馈发回给模型 (Gemini 会自动维护 history)
            try:
                response = self.chat.send_message(feedback)
                content = response.text
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