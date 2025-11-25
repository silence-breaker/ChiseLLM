#!/usr/bin/env python3
"""
ChiseLLM 评估测试集生成器 (带验证)

生成用于评估模型 Chisel 代码生成能力的测试集。
所有参考代码都会通过反射环境验证，确保正确性。

使用方法:
    python eval/generate_eval_set.py                    # 生成并验证
    python eval/generate_eval_set.py -o my_eval.jsonl   # 指定输出路径
    python eval/generate_eval_set.py --no-verify        # 跳过验证（调试用）
    python eval/generate_eval_set.py -j 4               # 4 进程并行验证
"""

import json
import os
import sys
import re
import random
import multiprocessing
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# 尝试导入 tqdm，如果不可用则提供简单替代
try:
    from tqdm import tqdm  # type: ignore
except ImportError:
    def tqdm(iterable, **kwargs):  # type: ignore
        """简单的 tqdm 替代"""
        desc = kwargs.get('desc', '')
        total = kwargs.get('total', None)
        if total is None:
            try:
                total = len(iterable)  # type: ignore
            except TypeError:
                total = '?'
        for i, item in enumerate(iterable, 1):
            print(f"\r{desc}: {i}/{total}", end='', flush=True)
            yield item
        print()  # 换行

# ============================================================================
# 环境配置
# ============================================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
src_dir = os.path.join(parent_dir, 'src')
sys.path.insert(0, src_dir)

# 尝试导入反射环境
REFLECT_AVAILABLE = False
reflect = None  # type: ignore  # 显式声明，避免"可能未绑定"警告

try:
    from reflect_env import reflect as _reflect  # type: ignore
    reflect = _reflect
    REFLECT_AVAILABLE = True
except ImportError:
    print("⚠️ 警告: 无法导入 reflect_env，将跳过验证")

# ============================================================================
# 错误日志
# ============================================================================

def init_error_log() -> str:
    """初始化错误日志文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(parent_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"eval_gen_errors_{timestamp}.log")


def log_error(log_file: str, case_id: str, module_name: str, error_info: str):
    """记录验证失败的用例"""
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Case ID: {case_id} | Module: {module_name}\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Error: {error_info}\n")
    except Exception:
        pass


# ============================================================================
# Level 1: 基础语法 (Wire, Reg, IO 定义)
# ============================================================================

L1_TEMPLATES = [
    # Passthrough 模块
    {
        "category": "passthrough",
        "variants": [
            {"width": 1, "name": "Bit"},
            {"width": 8, "name": "Byte"},
            {"width": 16, "name": "HalfWord"},
            {"width": 32, "name": "Word"},
            {"width": 64, "name": "DoubleWord"},
        ],
        "instruction_template": "Write a Chisel module named `Passthrough{name}` with a {width}-bit input `in` and a {width}-bit output `out`. The output should be directly connected to the input.",
        "reference_template": '''import chisel3._

class Passthrough{name} extends Module {{
  val io = IO(new Bundle {{
    val in  = Input(UInt({width}.W))
    val out = Output(UInt({width}.W))
  }})
  
  io.out := io.in
}}
'''
    },
    # Wire 定义与赋值
    {
        "category": "wire_assign",
        "variants": [
            {"width": 8, "value": "0", "name": "Zero"},
            {"width": 8, "value": "255", "name": "Max"},
            {"width": 16, "value": "1234", "name": "Const"},
            {"width": 32, "value": "\"hDEADBEEF\"", "name": "Magic"},  # 使用十六进制字符串
        ],
        "instruction_template": "Write a Chisel module named `Wire{name}` that declares a {width}-bit Wire and assigns it the constant value {value}. Output this wire as `out`.",
        "reference_template": '''import chisel3._

class Wire{name} extends Module {{
  val io = IO(new Bundle {{
    val out = Output(UInt({width}.W))
  }})
  
  val temp = Wire(UInt({width}.W))
  temp := {value}.U
  io.out := temp
}}
'''
    },
    # Reg 定义
    {
        "category": "reg_init",
        "variants": [
            {"width": 8, "init": 0, "name": "Zero"},
            {"width": 8, "init": 100, "name": "Hundred"},
            {"width": 16, "init": 0xFFFF, "name": "AllOnes"},
        ],
        "instruction_template": "Write a Chisel module named `Reg{name}` with a {width}-bit register initialized to {init}. The register value should be output as `out`.",
        "reference_template": '''import chisel3._

class Reg{name} extends Module {{
  val io = IO(new Bundle {{
    val out = Output(UInt({width}.W))
  }})
  
  val reg = RegInit({init}.U({width}.W))
  io.out := reg
}}
'''
    },
]

# ============================================================================
# Level 2: 组合逻辑 (算术、逻辑、多路选择)
# ============================================================================

L2_TEMPLATES = [
    # 加法器
    {
        "category": "adder",
        "variants": [
            {"width_in": 8, "width_out": 9, "name": "8bit"},
            {"width_in": 16, "width_out": 17, "name": "16bit"},
            {"width_in": 32, "width_out": 33, "name": "32bit"},
        ],
        "instruction_template": "Write a Chisel module named `Adder{name}` that takes two {width_in}-bit unsigned inputs `a` and `b`, and outputs their sum as `sum`. The output should be {width_out} bits wide to avoid overflow.",
        "reference_template": '''import chisel3._

class Adder{name} extends Module {{
  val io = IO(new Bundle {{
    val a   = Input(UInt({width_in}.W))
    val b   = Input(UInt({width_in}.W))
    val sum = Output(UInt({width_out}.W))
  }})
  
  io.sum := io.a +& io.b
}}
'''
    },
    # 2选1多路选择器
    {
        "category": "mux2",
        "variants": [
            {"width": 8, "name": "8bit"},
            {"width": 16, "name": "16bit"},
            {"width": 32, "name": "32bit"},
        ],
        "instruction_template": "Write a Chisel module named `Mux2to1_{name}` with a 1-bit select input `sel`, two {width}-bit data inputs `a` and `b`, and a {width}-bit output `out`. When `sel` is true, output `a`; otherwise output `b`.",
        "reference_template": '''import chisel3._

class Mux2to1_{name} extends Module {{
  val io = IO(new Bundle {{
    val sel = Input(Bool())
    val a   = Input(UInt({width}.W))
    val b   = Input(UInt({width}.W))
    val out = Output(UInt({width}.W))
  }})
  
  io.out := Mux(io.sel, io.a, io.b)
}}
'''
    },
    # 比较器
    {
        "category": "comparator",
        "variants": [
            {"width": 8, "op": "equal to", "op_sym": "===", "name": "Eq8"},
            {"width": 8, "op": "greater than", "op_sym": ">", "name": "Gt8"},
            {"width": 8, "op": "less than", "op_sym": "<", "name": "Lt8"},
            {"width": 16, "op": "equal to", "op_sym": "===", "name": "Eq16"},
        ],
        "instruction_template": "Write a Chisel module named `Comparator{name}` that compares two {width}-bit unsigned inputs `a` and `b`. Output a Bool `result` that is true when `a` is {op} `b`.",
        "reference_template": '''import chisel3._

class Comparator{name} extends Module {{
  val io = IO(new Bundle {{
    val a      = Input(UInt({width}.W))
    val b      = Input(UInt({width}.W))
    val result = Output(Bool())
  }})
  
  io.result := io.a {op_sym} io.b
}}
'''
    },
    # 位操作
    {
        "category": "bitwise",
        "variants": [
            {"width": 8, "op": "AND", "op_sym": "&", "name": "And8"},
            {"width": 8, "op": "OR", "op_sym": "|", "name": "Or8"},
            {"width": 8, "op": "XOR", "op_sym": "^", "name": "Xor8"},
            {"width": 16, "op": "AND", "op_sym": "&", "name": "And16"},
        ],
        "instruction_template": "Write a Chisel module named `Bitwise{name}` that performs bitwise {op} on two {width}-bit inputs `a` and `b`, outputting the result as `out`.",
        "reference_template": '''import chisel3._

class Bitwise{name} extends Module {{
  val io = IO(new Bundle {{
    val a   = Input(UInt({width}.W))
    val b   = Input(UInt({width}.W))
    val out = Output(UInt({width}.W))
  }})
  
  io.out := io.a {op_sym} io.b
}}
'''
    },
]

# ============================================================================
# Level 3: 时序逻辑 (计数器、移位寄存器、简单FSM)
# ============================================================================

L3_TEMPLATES = [
    # 计数器
    {
        "category": "counter",
        "variants": [
            {"width": 4, "name": "4bit"},
            {"width": 8, "name": "8bit"},
            {"width": 8, "name": "Mod100"},
        ],
        "instruction_template": "Write a Chisel module named `Counter{name}` that implements a {width}-bit counter. It should have an enable input `en`. When enabled, the counter increments each clock cycle. The current count is output as `count`.",
        "reference_template": '''import chisel3._

class Counter{name} extends Module {{
  val io = IO(new Bundle {{
    val en    = Input(Bool())
    val count = Output(UInt({width}.W))
  }})
  
  val counter = RegInit(0.U({width}.W))
  
  when(io.en) {{
    counter := counter + 1.U
  }}
  
  io.count := counter
}}
'''
    },
    # 移位寄存器
    {
        "category": "shift_register",
        "variants": [
            {"stages": 4, "width": 1, "name": "4stage"},
            {"stages": 8, "width": 1, "name": "8stage"},
            {"stages": 4, "width": 8, "name": "4stage_8bit"},
        ],
        "instruction_template": "Write a Chisel module named `ShiftReg{name}` that implements a {stages}-stage shift register with {width}-bit data width. It should have an input `in` and output `out`. Each clock cycle, data shifts through the stages.",
        "reference_template": '''import chisel3._

class ShiftReg{name} extends Module {{
  val io = IO(new Bundle {{
    val in  = Input(UInt({width}.W))
    val out = Output(UInt({width}.W))
  }})
  
  val regs = Reg(Vec({stages}, UInt({width}.W)))
  
  regs(0) := io.in
  for (i <- 1 until {stages}) {{
    regs(i) := regs(i - 1)
  }}
  
  io.out := regs({stages} - 1)
}}
'''
    },
    # 边沿检测器 - Rising
    {
        "category": "edge_detector",
        "variants": [
            {"name": "Rising"},
        ],
        "instruction_template": "Write a Chisel module named `{name}Edge` that detects a rising edge on the input signal `in`. Output `detected` should be high for one clock cycle when a rising edge is detected.",
        "reference_template": '''import chisel3._

class {name}Edge extends Module {{
  val io = IO(new Bundle {{
    val in       = Input(Bool())
    val detected = Output(Bool())
  }})
  
  val prev = RegNext(io.in, false.B)
  io.detected := io.in && !prev
}}
'''
    },
    # 边沿检测器 - Falling
    {
        "category": "edge_detector",
        "variants": [
            {"name": "Falling"},
        ],
        "instruction_template": "Write a Chisel module named `{name}Edge` that detects a falling edge on the input signal `in`. Output `detected` should be high for one clock cycle when a falling edge is detected.",
        "reference_template": '''import chisel3._

class {name}Edge extends Module {{
  val io = IO(new Bundle {{
    val in       = Input(Bool())
    val detected = Output(Bool())
  }})
  
  val prev = RegNext(io.in, false.B)
  io.detected := !io.in && prev
}}
'''
    },
    # 简单FSM
    {
        "category": "fsm_simple",
        "variants": [
            {"name": "OnOff"},
        ],
        "instruction_template": "Write a Chisel module named `FSM{name}` implementing a 2-state FSM with states OFF and ON. Input `toggle` transitions between states. Output `state` indicates current state (0=OFF, 1=ON).",
        "reference_template": '''import chisel3._
import chisel3.util._

class FSM{name} extends Module {{
  val io = IO(new Bundle {{
    val toggle = Input(Bool())
    val state  = Output(Bool())
  }})
  
  val sOff :: sOn :: Nil = Enum(2)
  val stateReg = RegInit(sOff)
  
  switch(stateReg) {{
    is(sOff) {{
      when(io.toggle) {{
        stateReg := sOn
      }}
    }}
    is(sOn) {{
      when(io.toggle) {{
        stateReg := sOff
      }}
    }}
  }}
  
  io.state := (stateReg === sOn)
}}
'''
    },
]

# ============================================================================
# Level 4: 进阶模块 (参数化、接口协议)
# ============================================================================

L4_TEMPLATES = [
    # 参数化加法器
    {
        "category": "parameterized",
        "variants": [
            {"name": "Adder", "default_width": 8},
        ],
        "instruction_template": "Write a parameterized Chisel module named `ParamAdder` that takes a width parameter. It should have two inputs `a` and `b` of the parameterized width, and output `sum` with width+1 bits.",
        "reference_template": '''import chisel3._

class ParamAdder(width: Int = {default_width}) extends Module {{
  val io = IO(new Bundle {{
    val a   = Input(UInt(width.W))
    val b   = Input(UInt(width.W))
    val sum = Output(UInt((width + 1).W))
  }})
  
  io.sum := io.a +& io.b
}}
'''
    },
    # Valid 接口
    {
        "category": "valid_interface",
        "variants": [
            {"width": 8, "name": "8bit"},
        ],
        "instruction_template": "Write a Chisel module named `ValidReg{name}` with a Valid interface input containing {width}-bit data. When valid is asserted, store the data in a register and output it.",
        "reference_template": '''import chisel3._
import chisel3.util._

class ValidReg{name} extends Module {{
  val io = IO(new Bundle {{
    val in  = Flipped(Valid(UInt({width}.W)))
    val out = Output(UInt({width}.W))
  }})
  
  val reg = RegInit(0.U({width}.W))
  
  when(io.in.valid) {{
    reg := io.in.bits
  }}
  
  io.out := reg
}}
'''
    },
]


# ============================================================================
# 验证函数
# ============================================================================

def validate_code(code: str, module_name: str, case_id: str, log_file: str) -> bool:
    """
    使用反射环境验证代码
    
    Returns:
        True 如果编译和阐述都通过
    """
    if not REFLECT_AVAILABLE or reflect is None:
        return True  # 跳过验证
    
    try:
        result = reflect(
            chisel_code_string=code,
            module_name=module_name,
            testbench_path=None,
            output_dir=None,
            verilog_file=None,
            result_file=None,
            silent=True
        )
        
        if result['compiled'] and result['elaborated']:
            return True
        else:
            error_stage = "compilation" if not result['compiled'] else "elaboration"
            error_info = f"Stage: {error_stage}\n"
            if 'error_log' in result:
                error_info += f"Error Log:\n{result['error_log']}\n"
            error_info += f"\nCode:\n{code}\n"
            log_error(log_file, case_id, module_name, error_info)
            return False
            
    except Exception as e:
        error_info = f"Exception: {str(e)}\nCode:\n{code}\n"
        log_error(log_file, case_id, module_name, error_info)
        return False


def validate_case_worker(args: Tuple) -> Optional[Dict[str, Any]]:
    """多进程验证工作函数"""
    case, log_file = args
    
    code = case["reference_code"]
    module_name = case["test_config"]["module_name"]
    case_id = case["id"]
    
    if validate_code(code, module_name, case_id, log_file):
        return case
    return None


# ============================================================================
# 测试用例生成
# ============================================================================

def generate_test_cases(templates: List[Dict], level: str, start_id: int) -> List[Dict[str, Any]]:
    """从模板生成测试用例"""
    cases = []
    case_id = start_id
    
    for template in templates:
        category = template["category"]
        
        for variant in template["variants"]:
            # 格式化指令和参考代码
            instruction = template["instruction_template"].format(**variant)
            reference = template["reference_template"].format(**variant)
            
            # 提取模块名
            match = re.search(r'class\s+(\w+)', reference)
            module_name = match.group(1) if match else f"Module_{case_id}"
            
            case = {
                "id": f"{level}_{case_id:03d}",
                "level": level,
                "category": category,
                "instruction": instruction,
                "input": "",
                "reference_code": reference,
                "test_config": {
                    "require_compile": True,
                    "require_elaborate": True,
                    "require_simulate": False,
                    "module_name": module_name
                }
            }
            cases.append(case)
            case_id += 1
    
    return cases


def generate_all_cases(levels: List[str]) -> List[Dict[str, Any]]:
    """生成所有测试用例"""
    all_cases = []
    
    level_templates = {
        "L1": (L1_TEMPLATES, "L1-Basic"),
        "L2": (L2_TEMPLATES, "L2-Combinational"),
        "L3": (L3_TEMPLATES, "L3-Sequential"),
        "L4": (L4_TEMPLATES, "L4-Advanced"),
    }
    
    id_counter = 1
    for level in levels:
        if level in level_templates:
            templates, level_name = level_templates[level]
            cases = generate_test_cases(templates, level_name, id_counter)
            all_cases.extend(cases)
            id_counter += len(cases)
    
    return all_cases


def generate_eval_set(
    output_path: str,
    levels: List[str] = ["L1", "L2", "L3", "L4"],
    shuffle: bool = False,
    seed: int = 42,
    verify: bool = True,
    num_workers: int = 1
) -> Dict[str, Any]:
    """
    生成评估测试集
    
    Args:
        output_path: 输出文件路径
        levels: 要包含的难度级别
        shuffle: 是否打乱顺序
        seed: 随机种子
        verify: 是否验证参考代码
        num_workers: 并行验证的进程数
    
    Returns:
        生成统计信息
    """
    # 生成所有用例
    all_cases = generate_all_cases(levels)
    total_generated = len(all_cases)
    
    print(f"生成了 {total_generated} 条测试用例")
    
    # 验证
    valid_cases = []
    if verify and REFLECT_AVAILABLE:
        log_file = init_error_log()
        print(f"📝 错误日志: {log_file}")
        print("正在验证参考代码...")
        
        if num_workers == 1:
            # 串行验证
            for case in tqdm(all_cases, desc="验证"):
                result = validate_case_worker((case, log_file))
                if result:
                    valid_cases.append(result)
        else:
            # 并行验证
            work_items = [(case, log_file) for case in all_cases]
            with multiprocessing.Pool(num_workers) as pool:
                results = list(tqdm(
                    pool.imap(validate_case_worker, work_items),
                    total=len(work_items),
                    desc=f"验证 ({num_workers} workers)"
                ))
            valid_cases = [r for r in results if r is not None]
    else:
        valid_cases = all_cases
        if verify and not REFLECT_AVAILABLE:
            print("⚠️ reflect_env 不可用，跳过验证")
    
    # 统计
    stats = {
        "total_generated": total_generated,
        "total_valid": len(valid_cases),
        "validation_rate": len(valid_cases) / total_generated if total_generated > 0 else 0,
        "by_level": {},
        "by_category": {}
    }
    
    for case in valid_cases:
        level = case["level"]
        cat = case["category"]
        
        if level not in stats["by_level"]:
            stats["by_level"][level] = 0
        stats["by_level"][level] += 1
        
        if cat not in stats["by_category"]:
            stats["by_category"][cat] = 0
        stats["by_category"][cat] += 1
    
    # 打乱顺序
    if shuffle:
        random.seed(seed)
        random.shuffle(valid_cases)
    
    # 写入文件
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for case in valid_cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="生成 ChiseLLM 评估测试集 (带验证)")
    parser.add_argument("--output", "-o", type=str, 
                        default=None,
                        help="输出文件路径 (默认: eval/eval_set_<timestamp>.jsonl)")
    parser.add_argument("--levels", "-l", type=str, nargs="+",
                        default=["L1", "L2", "L3", "L4"],
                        choices=["L1", "L2", "L3", "L4"],
                        help="要包含的难度级别")
    parser.add_argument("--shuffle", action="store_true",
                        help="打乱测试用例顺序")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子")
    parser.add_argument("--no-verify", action="store_true",
                        help="跳过反射环境验证")
    parser.add_argument("-j", "--workers", type=int, default=1,
                        help="并行验证的进程数")
    
    args = parser.parse_args()
    
    # 默认输出路径
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(current_dir, f"eval_set_{timestamp}.jsonl")
    
    print("=" * 60)
    print("ChiseLLM 评估测试集生成器 (带验证)")
    print("=" * 60)
    print(f"输出路径: {args.output}")
    print(f"难度级别: {args.levels}")
    print(f"验证模式: {'关闭' if args.no_verify else '开启'}")
    print(f"并行进程: {args.workers}")
    print()
    
    stats = generate_eval_set(
        output_path=args.output,
        levels=args.levels,
        shuffle=args.shuffle,
        seed=args.seed,
        verify=not args.no_verify,
        num_workers=args.workers
    )
    
    print()
    print("=" * 60)
    print("生成统计")
    print("=" * 60)
    print(f"生成: {stats['total_generated']} 条")
    print(f"验证通过: {stats['total_valid']} 条 ({stats['validation_rate']:.1%})")
    print()
    print("按级别:")
    for level, count in sorted(stats["by_level"].items()):
        print(f"  {level}: {count}")
    print()
    print("按类别:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"  {cat}: {count}")
    print()
    print(f"✅ 测试集已保存到: {args.output}")


if __name__ == "__main__":
    main()
