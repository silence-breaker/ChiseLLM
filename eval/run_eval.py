#!/usr/bin/env python3
"""
ChiseLLM 模型评估器

基于预生成的测试集评估模型的 Chisel 代码生成能力。
利用反射环境验证生成代码的编译/阐述正确性。

使用方法:
    # 评估本地模型
    python run_eval.py --eval-set eval_set.jsonl --model Qwen/Qwen2.5-Coder-14B-Instruct
    
    # 评估 API 服务
    python run_eval.py --eval-set eval_set.jsonl --api http://localhost:8000/v1
    
    # 仅统计已有结果
    python run_eval.py --results eval_results.json --stats-only
"""

import json
import os
import sys
import re
import tempfile
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def load_eval_set(path: str) -> List[Dict[str, Any]]:
    """加载评估测试集"""
    cases = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))
    return cases


def extract_scala_code(text: str) -> str:
    """从模型输出中提取 Scala/Chisel 代码
    
    增强版：支持处理不使用 Markdown 代码块的模型输出（SFT 后常见）
    """
    # 优先匹配 ```scala 代码块
    patterns = [
        r'```scala\s*(.*?)```',
        r'```chisel\s*(.*?)```',
        r'```\s*(import chisel3\..*?)```',
        r'```\s*(class \w+.*?)```',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[0].strip()
    
    # [兜底策略] SFT 微调后模型通常直接输出代码，不使用 Markdown
    # 如果文本包含 Chisel 特征，认为整段就是代码
    if "import chisel3" in text and "extends Module" in text:
        # 找到第一个 import 语句的位置
        lines = text.split('\n')
        code_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import '):
                code_start = i
                break
        
        if code_start == -1:
            # 如果没找到 import，从第一个 class 开始
            for i, line in enumerate(lines):
                if 'class ' in line and 'extends Module' in line:
                    code_start = i
                    break
        
        if code_start != -1:
            # 从起点开始，追踪大括号配对找到结束位置
            brace_count = 0
            code_end = len(lines)
            found_opening = False
            
            for i in range(code_start, len(lines)):
                line = lines[i]
                brace_count += line.count('{') - line.count('}')
                
                # 标记是否已经遇到过左大括号
                if '{' in line:
                    found_opening = True
                
                # 如果已经遇到左大括号，且配对归零，说明模块结束
                if found_opening and brace_count == 0:
                    code_end = i + 1
                    break
            
            extracted = '\n'.join(lines[code_start:code_end]).strip()
            if extracted:
                return extracted
        
        # 如果提取失败，返回整段文本（可能整个输出就是代码）
        return text.strip()
    
    # 如果没有明显的 Chisel 特征，尝试查找任何 import/class 组合
    if "import chisel3" in text or ("class " in text and "Module" in text):
        return text.strip()
    
    return text  # 返回原文，让编译器报错


def verify_with_reflect_env(
    scala_code: str,
    module_name: str,
    require_compile: bool = True,
    require_elaborate: bool = True,
    require_simulate: bool = False,
    testbench: Optional[str] = None,
    timeout: int = 120
) -> Dict[str, Any]:
    """
    使用反射环境验证代码
    
    通过子进程调用 chisel-llm 环境中的 reflect_env，
    解决 chisel-train 环境中缺少 Mill/Chisel 依赖的问题。
    
    Returns:
        {
            "success": bool,
            "stage": "compilation" | "elaboration" | "simulation" | "passed",
            "error_log": str,
            "verilog": str  # 如果成功生成
        }
    """
    import subprocess
    
    # 创建临时文件保存 Scala 代码
    with tempfile.NamedTemporaryFile(mode='w', suffix='.scala', delete=False) as f:
        f.write(scala_code)
        scala_path = f.name
    
    # 创建临时文件保存结果
    result_path = scala_path.replace('.scala', '_result.json')
    
    try:
        # 构建验证脚本（在 chisel-llm 环境中执行）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        verify_script = f'''
import sys
import json
sys.path.insert(0, "{project_root}/src")
from reflect_env import reflect

result = reflect(
    chisel_code_string=open("{scala_path}").read(),
    module_name="{module_name}",
    testbench_path=None,
    output_dir=None,
    verilog_file=None,
    result_file=None,
    silent=True
)

# 转换结果格式
output = {{
    "success": result.get("compiled", False) and result.get("elaborated", False),
    "compiled": result.get("compiled", False),
    "elaborated": result.get("elaborated", False),
    "stage": "passed" if (result.get("compiled") and result.get("elaborated")) else 
             ("compilation" if not result.get("compiled") else "elaboration"),
    "error_log": result.get("error_log", ""),
    "verilog": result.get("verilog", "")
}}

with open("{result_path}", "w") as f:
    json.dump(output, f)
'''
        
        # 通过 conda run 在 chisel-llm 环境中执行
        cmd = [
            "conda", "run", "-n", "chisel-llm", "--no-capture-output",
            "python", "-c", verify_script
        ]
        
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root
        )
        
        # 读取结果
        if os.path.exists(result_path):
            with open(result_path, 'r') as f:
                result = json.load(f)
            return result
        else:
            return {
                "success": False,
                "stage": "setup",
                "error_log": f"验证脚本执行失败:\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stage": "timeout",
            "error_log": f"验证超时 ({timeout}s)"
        }
    except Exception as e:
        return {
            "success": False,
            "stage": "exception",
            "error_log": str(e)
        }
    finally:
        # 清理临时文件
        for path in [scala_path, result_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass


class ModelInterface:
    """模型接口抽象基类"""
    
    def generate(self, instruction: str, input_text: str = "") -> str:
        raise NotImplementedError


class TransformersModel(ModelInterface):
    """使用 transformers 库的本地模型"""
    
    def __init__(self, model_name: str, quantization: str = "4bit"):
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        import torch
        
        print(f"正在加载模型: {model_name} ({quantization} 量化)...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, trust_remote_code=True
        )
        
        load_kwargs = {
            "dtype": torch.bfloat16,
            "device_map": "auto",
            "trust_remote_code": True,
        }
        
        if quantization == "4bit":
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4"
            )
        elif quantization == "8bit":
            load_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=True
            )
        
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
        print("模型加载完成!")
    
    def generate(self, instruction: str, input_text: str = "") -> str:
        if input_text:
            user_content = f"{instruction}\n\nInput:\n{input_text}"
        else:
            user_content = instruction
        
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant specialized in Chisel hardware description language. Generate clean, compilable Chisel code. Only output the code without explanations."
            },
            {"role": "user", "content": user_content}
        ]
        
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=1024,
            temperature=0.1,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id,
        )
        
        generated = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )
        return generated


class APIModel(ModelInterface):
    """通过 OpenAI 兼容 API 调用的模型"""
    
    def __init__(self, api_base: str, model_name: str = "default", api_key: str = "EMPTY"):
        import requests
        self.api_base = api_base.rstrip('/')
        self.model_name = model_name
        self.api_key = api_key
        self.session = requests.Session()
        
        # 测试连接
        try:
            resp = self.session.get(f"{self.api_base}/models", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                if models:
                    self.model_name = models[0].get("id", model_name)
                print(f"API 连接成功，使用模型: {self.model_name}")
        except Exception as e:
            print(f"警告: 无法连接到 API - {e}")
    
    def generate(self, instruction: str, input_text: str = "") -> str:
        if input_text:
            user_content = f"{instruction}\n\nInput:\n{input_text}"
        else:
            user_content = instruction
        
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant specialized in Chisel hardware description language. Generate clean, compilable Chisel code. Only output the code without explanations."
                },
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 1024,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        resp = self.session.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120
        )
        resp.raise_for_status()
        
        return resp.json()["choices"][0]["message"]["content"]


def evaluate_single_case(
    case: Dict[str, Any],
    model: ModelInterface,
    verify: bool = True
) -> Dict[str, Any]:
    """评估单个测试用例"""
    result = {
        "id": case["id"],
        "level": case["level"],
        "category": case["category"],
        "instruction": case["instruction"],
    }
    
    try:
        # 生成代码
        raw_output = model.generate(case["instruction"], case.get("input", ""))
        result["raw_output"] = raw_output
        
        # 提取代码
        extracted_code = extract_scala_code(raw_output)
        result["extracted_code"] = extracted_code
        
        if verify:
            # 获取模块名
            module_name = case.get("test_config", {}).get("module_name")
            if not module_name:
                # 尝试从代码中提取
                match = re.search(r'class\s+(\w+)', extracted_code)
                module_name = match.group(1) if match else "Unknown"
            
            # 验证代码
            verify_result = verify_with_reflect_env(
                scala_code=extracted_code,
                module_name=module_name,
                require_compile=case.get("test_config", {}).get("require_compile", True),
                require_elaborate=case.get("test_config", {}).get("require_elaborate", True),
            )
            
            result["verify_result"] = verify_result
            result["passed"] = verify_result["success"]
            result["failed_stage"] = verify_result.get("stage") if not verify_result["success"] else None
        else:
            result["passed"] = None
            result["verify_result"] = None
        
    except Exception as e:
        result["error"] = str(e)
        result["passed"] = False
        result["failed_stage"] = "exception"
    
    return result


def run_evaluation(
    eval_set: List[Dict[str, Any]],
    model: ModelInterface,
    verify: bool = True,
    max_workers: int = 1,
    progress_callback=None
) -> List[Dict[str, Any]]:
    """运行完整评估"""
    results = []
    total = len(eval_set)
    
    if max_workers == 1:
        # 串行执行
        for i, case in enumerate(eval_set):
            result = evaluate_single_case(case, model, verify)
            results.append(result)
            
            if progress_callback:
                progress_callback(i + 1, total, result)
    else:
        # 并行执行（注意：GPU 模型可能不支持真正的并行）
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(evaluate_single_case, case, model, verify): case
                for case in eval_set
            }
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                results.append(result)
                
                if progress_callback:
                    progress_callback(i + 1, total, result)
    
    return results


def compute_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算评估统计"""
    stats = {
        "total": len(results),
        "passed": 0,
        "failed": 0,
        "by_level": {},
        "by_category": {},
        "by_failed_stage": {},
    }
    
    for r in results:
        level = r.get("level", "unknown")
        category = r.get("category", "unknown")
        passed = r.get("passed", False)
        
        # 初始化
        if level not in stats["by_level"]:
            stats["by_level"][level] = {"total": 0, "passed": 0}
        if category not in stats["by_category"]:
            stats["by_category"][category] = {"total": 0, "passed": 0}
        
        # 计数
        stats["by_level"][level]["total"] += 1
        stats["by_category"][category]["total"] += 1
        
        if passed:
            stats["passed"] += 1
            stats["by_level"][level]["passed"] += 1
            stats["by_category"][category]["passed"] += 1
        else:
            stats["failed"] += 1
            stage = r.get("failed_stage", "unknown")
            stats["by_failed_stage"][stage] = stats["by_failed_stage"].get(stage, 0) + 1
    
    # 计算通过率
    stats["pass_rate"] = stats["passed"] / stats["total"] if stats["total"] > 0 else 0
    
    for level_stats in stats["by_level"].values():
        level_stats["pass_rate"] = (
            level_stats["passed"] / level_stats["total"]
            if level_stats["total"] > 0 else 0
        )
    
    for cat_stats in stats["by_category"].values():
        cat_stats["pass_rate"] = (
            cat_stats["passed"] / cat_stats["total"]
            if cat_stats["total"] > 0 else 0
        )
    
    return stats


def print_statistics(stats: Dict[str, Any]):
    """打印统计报告"""
    print("\n" + "=" * 60)
    print("评估结果统计")
    print("=" * 60)
    
    print(f"\n总体通过率: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.1%})")
    
    print("\n按难度级别:")
    for level, level_stats in sorted(stats["by_level"].items()):
        bar = "█" * int(level_stats["pass_rate"] * 20) + "░" * (20 - int(level_stats["pass_rate"] * 20))
        print(f"  {level:20s} {bar} {level_stats['passed']:2d}/{level_stats['total']:2d} ({level_stats['pass_rate']:.0%})")
    
    print("\n按类别:")
    for cat, cat_stats in sorted(stats["by_category"].items()):
        bar = "█" * int(cat_stats["pass_rate"] * 10) + "░" * (10 - int(cat_stats["pass_rate"] * 10))
        print(f"  {cat:20s} {bar} {cat_stats['passed']:2d}/{cat_stats['total']:2d} ({cat_stats['pass_rate']:.0%})")
    
    if stats["by_failed_stage"]:
        print("\n失败阶段分布:")
        for stage, count in sorted(stats["by_failed_stage"].items(), key=lambda x: -x[1]):
            print(f"  {stage:20s}: {count}")


def main():
    parser = argparse.ArgumentParser(description="ChiseLLM 模型评估器")
    
    # 数据源
    parser.add_argument("--eval-set", "-e", type=str,
                        help="评估测试集路径 (JSONL)")
    parser.add_argument("--results", "-r", type=str,
                        help="已有结果文件 (用于 --stats-only)")
    
    # 模型选择
    parser.add_argument("--model", "-m", type=str,
                        default="Qwen/Qwen2.5-Coder-14B-Instruct",
                        help="Hugging Face 模型名称")
    parser.add_argument("--api", type=str,
                        help="API 端点 (如 http://localhost:8000/v1)")
    parser.add_argument("--quantization", "-q", type=str,
                        choices=["none", "4bit", "8bit"],
                        default="4bit",
                        help="量化方式")
    
    # 评估选项
    parser.add_argument("--no-verify", action="store_true",
                        help="跳过编译验证（仅生成代码）")
    parser.add_argument("--limit", "-n", type=int,
                        help="限制评估用例数量")
    parser.add_argument("--levels", type=str, nargs="+",
                        help="仅评估指定级别")
    
    # 输出
    parser.add_argument("--output", "-o", type=str,
                        help="结果输出路径")
    parser.add_argument("--stats-only", action="store_true",
                        help="仅统计已有结果")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细输出")
    
    args = parser.parse_args()
    
    # 仅统计模式
    if args.stats_only:
        if not args.results:
            print("错误: --stats-only 需要指定 --results")
            sys.exit(1)
        
        with open(args.results, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        stats = compute_statistics(data.get("results", data))
        print_statistics(stats)
        return
    
    # 加载评估集
    if not args.eval_set:
        print("错误: 请指定评估测试集 (--eval-set)")
        sys.exit(1)
    
    print("=" * 60)
    print("ChiseLLM 模型评估")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试集: {args.eval_set}")
    
    eval_set = load_eval_set(args.eval_set)
    print(f"加载 {len(eval_set)} 条测试用例")
    
    # 过滤级别
    if args.levels:
        eval_set = [c for c in eval_set if any(l in c["level"] for l in args.levels)]
        print(f"过滤后: {len(eval_set)} 条 (级别: {args.levels})")
    
    # 限制数量
    if args.limit:
        eval_set = eval_set[:args.limit]
        print(f"限制为前 {args.limit} 条")
    
    # 初始化模型
    if args.api:
        model = APIModel(args.api)
    else:
        model = TransformersModel(args.model, args.quantization)
    
    # 进度回调
    def progress_callback(current, total, result):
        status = "✅" if result.get("passed") else "❌"
        stage = result.get("failed_stage", "passed")
        level = result.get("level", "L?")
        category = result.get("category", "unknown")[:15]
        print(f"[{current}/{total}] {level} | {category:15s} | {result['id']:20s} {status} ({stage})")
    
    # 运行评估（默认显示进度）
    print("\n开始评估...")
    print("提示: 模型首次生成需要预热，第一个样本可能较慢 (~30-60秒)\n")
    results = run_evaluation(
        eval_set,
        model,
        verify=not args.no_verify,
        progress_callback=progress_callback  # 默认启用进度显示
    )
    
    # 计算统计
    stats = compute_statistics(results)
    print_statistics(stats)
    
    # 保存结果
    output_path = args.output
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            os.path.dirname(__file__),
            f"eval_results_{timestamp}.json"
        )
    
    output_data = {
        "metadata": {
            "eval_set": args.eval_set,
            "model": args.model if not args.api else args.api,
            "timestamp": datetime.now().isoformat(),
            "verify": not args.no_verify,
        },
        "statistics": stats,
        "results": results,
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
