#!/usr/bin/env python3
"""
专门生成现有数据集缺失的样本类型（多进程加速版）
目标: Enum, PopCount, Reverse, Fill, Log2, PriorityEncoder, OHToUInt, UIntToOH, Mux1H

根据分析，现有 10000 条数据集:
- Cat(): 550 条 ✅
- Enum(): 0 条 ❌
- PopCount: 0 条 ❌
- 其他 util: 0 条 ❌
"""

import sys
import os
import json
import random
import multiprocessing
from datetime import datetime
from tqdm import tqdm

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from reflect_env import reflect
from jinja2 import Template

# ==========================================
# 1. 缺失的模板定义
# ==========================================

# FSM 使用 Enum list 解构 (这是失败案例的关键!)
TEMPLATE_FSM_ENUM_LIST = """
import chisel3._
import chisel3.util._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val toggle = Input(Bool())
    val state = Output(Bool())
  })
  
  // Define states using Enum list destructuring
  val sOff :: sOn :: Nil = Enum(2)
  val stateReg = RegInit(sOff)
  
  // State transition logic
  switch (stateReg) {
    is (sOff) {
      when (io.toggle) {
        stateReg := sOn
      }
    }
    is (sOn) {
      when (io.toggle) {
        stateReg := sOff
      }
    }
  }
  
  io.state := stateReg === sOn
}
"""

# 3 状态 FSM
TEMPLATE_FSM_ENUM_3STATE = """
import chisel3._
import chisel3.util._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val start = Input(Bool())
    val done = Input(Bool())
    val idle = Output(Bool())
    val busy = Output(Bool())
    val complete = Output(Bool())
  })
  
  // Define 3 states using Enum list destructuring
  val sIdle :: sBusy :: sDone :: Nil = Enum(3)
  val stateReg = RegInit(sIdle)
  
  // State transition logic
  switch (stateReg) {
    is (sIdle) {
      when (io.start) {
        stateReg := sBusy
      }
    }
    is (sBusy) {
      when (io.done) {
        stateReg := sDone
      }
    }
    is (sDone) {
      stateReg := sIdle
    }
  }
  
  io.idle := stateReg === sIdle
  io.busy := stateReg === sBusy
  io.complete := stateReg === sDone
}
"""

# 4 状态 FSM
TEMPLATE_FSM_ENUM_4STATE = """
import chisel3._
import chisel3.util._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val req = Input(Bool())
    val ack = Input(Bool())
    val state = Output(UInt(2.W))
  })
  
  // Define 4 states using Enum list destructuring
  val sIdle :: sRequest :: sWait :: sComplete :: Nil = Enum(4)
  val stateReg = RegInit(sIdle)
  
  switch (stateReg) {
    is (sIdle) {
      when (io.req) { stateReg := sRequest }
    }
    is (sRequest) {
      stateReg := sWait
    }
    is (sWait) {
      when (io.ack) { stateReg := sComplete }
    }
    is (sComplete) {
      stateReg := sIdle
    }
  }
  
  io.state := stateReg
}
"""

# PopCount - 计算置位位数
TEMPLATE_POPCOUNT = """
import chisel3._
import chisel3.util.PopCount

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val count = Output(UInt({{ count_width }}.W))
  })
  
  // Count the number of set bits using PopCount
  io.count := PopCount(io.in)
}
"""

# Reverse - 位翻转
TEMPLATE_REVERSE = """
import chisel3._
import chisel3.util.Reverse

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // Reverse the bit order
  io.out := Reverse(io.in)
}
"""

# Fill - 位复制
TEMPLATE_FILL = """
import chisel3._
import chisel3.util.Fill

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ total_width }}.W))
  })
  
  // Replicate the input {{ times }} times
  io.out := Fill({{ times }}, io.in)
}
"""

# Log2 - 对数计算
TEMPLATE_LOG2 = """
import chisel3._
import chisel3.util.Log2

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ log_width }}.W))
  })
  
  // Calculate floor(log2(in))
  io.out := Log2(io.in)
}
"""

# PriorityEncoder - 优先级编码器
TEMPLATE_PRIORITY_ENCODER = """
import chisel3._
import chisel3.util.PriorityEncoder

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ enc_width }}.W))
  })
  
  // Find position of least significant set bit
  io.out := PriorityEncoder(io.in)
}
"""

# OHToUInt - 独热码转二进制
TEMPLATE_OH_TO_UINT = """
import chisel3._
import chisel3.util.OHToUInt

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val oneHot = Input(UInt({{ width }}.W))
    val binary = Output(UInt({{ enc_width }}.W))
  })
  
  // Convert one-hot encoding to binary
  io.binary := OHToUInt(io.oneHot)
}
"""

# UIntToOH - 二进制转独热码
TEMPLATE_UINT_TO_OH = """
import chisel3._
import chisel3.util.UIntToOH

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val binary = Input(UInt({{ enc_width }}.W))
    val oneHot = Output(UInt({{ width }}.W))
  })
  
  // Convert binary to one-hot encoding
  io.oneHot := UIntToOH(io.binary)
}
"""

# Mux1H - 独热码选择器
TEMPLATE_MUX1H = """
import chisel3._
import chisel3.util.Mux1H

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val sel = Input(UInt(4.W))
    val in0 = Input(UInt({{ width }}.W))
    val in1 = Input(UInt({{ width }}.W))
    val in2 = Input(UInt({{ width }}.W))
    val in3 = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // One-hot multiplexer
  io.out := Mux1H(Seq(
    io.sel(0) -> io.in0,
    io.sel(1) -> io.in1,
    io.sel(2) -> io.in2,
    io.sel(3) -> io.in3
  ))
}
"""

# 移位寄存器使用 Cat (确保模型学会 import)
TEMPLATE_SHIFT_REG_CAT = """
import chisel3._
import chisel3.util.Cat

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(Bool())
    val out = Output(UInt({{ depth }}.W))
  })
  
  val shiftReg = RegInit(0.U({{ depth }}.W))
  
  // Shift using Cat: concatenate new bit with existing bits
  shiftReg := Cat(shiftReg({{ depth_minus_2 }}:0), io.in)
  
  io.out := shiftReg
}
"""

# ==========================================
# 2. 指令模板
# ==========================================

INSTRUCTIONS = {
    "fsm_enum_2state": [
        "Write an FSM that switches states when toggle is asserted.",
        "Create a two-state toggle FSM using Enum.",
        "Implement a flip-flop style state machine with Enum list destructuring.",
        "Design a simple on/off state machine using chisel3.util.Enum.",
        "Build a toggling FSM that alternates between two states.",
    ],
    "fsm_enum_3state": [
        "Create a 3-state FSM (Idle, Busy, Done) using Enum.",
        "Implement a state machine with idle, processing, and complete states.",
        "Design a task controller FSM with three states using Enum list.",
        "Write a 3-state workflow FSM: idle -> busy -> done -> idle.",
        "Build a simple protocol FSM with Enum destructuring.",
    ],
    "fsm_enum_4state": [
        "Create a 4-state request/acknowledge FSM using Enum.",
        "Implement a handshake protocol state machine with 4 states.",
        "Design a request-wait-ack-complete FSM using chisel3.util.Enum.",
        "Write a 4-state controller using Enum list destructuring.",
        "Build a multi-stage FSM with request and acknowledge signals.",
    ],
    "popcount": [
        "Count the number of set bits in a {width}-bit input.",
        "Implement a population count module for {width}-bit values.",
        "Create a bit counter using PopCount for {width} bits.",
        "Design a module that counts ones in a {width}-bit number.",
        "Write a Chisel module to count set bits using PopCount.",
    ],
    "reverse": [
        "Reverse the bit order of a {width}-bit input.",
        "Create a bit reversal module for {width}-bit values.",
        "Implement a mirror function for {width} bits using Reverse.",
        "Design a module that flips bit positions in a {width}-bit number.",
        "Write a bit-order reverser for {width}-bit signals.",
    ],
    "fill": [
        "Replicate a {width}-bit input {times} times.",
        "Create a bit replicator that copies {width} bits {times} times.",
        "Implement sign extension by filling {width} bits {times} times.",
        "Design a module using Fill to replicate bits.",
        "Write a bit duplicator using chisel3.util.Fill.",
    ],
    "log2": [
        "Calculate the log2 of a {width}-bit input.",
        "Find the bit position of the highest set bit in {width} bits.",
        "Implement a log2 calculator for {width}-bit values.",
        "Create a module to compute floor(log2(x)) for {width}-bit x.",
        "Design a highest-bit finder using Log2.",
    ],
    "priority_encoder": [
        "Find the position of the first set bit in {width} bits.",
        "Implement a priority encoder for {width}-bit input.",
        "Create a lowest-set-bit finder for {width}-bit values.",
        "Design a module using PriorityEncoder for {width} bits.",
        "Write a first-one detector using chisel3.util.",
    ],
    "oh_to_uint": [
        "Convert a {width}-bit one-hot code to binary.",
        "Implement one-hot to binary decoder for {width} bits.",
        "Create a one-hot decoder using OHToUInt.",
        "Design a module that converts one-hot encoding to unsigned.",
        "Write a one-hot to binary converter for {width}-bit input.",
    ],
    "uint_to_oh": [
        "Convert a binary number to {width}-bit one-hot encoding.",
        "Implement binary to one-hot encoder.",
        "Create a one-hot encoder using UIntToOH.",
        "Design a module that produces {width}-bit one-hot output.",
        "Write a binary to one-hot converter.",
    ],
    "mux1h": [
        "Create a one-hot multiplexer for {width}-bit inputs.",
        "Implement a 4-way one-hot selector using Mux1H.",
        "Design a one-hot MUX for {width}-bit data.",
        "Write a selector using chisel3.util.Mux1H.",
        "Build a one-hot encoded multiplexer.",
    ],
    "shift_cat": [
        "Implement a {depth}-bit shift register using Cat.",
        "Create a serial-in parallel-out register with Cat concatenation.",
        "Design a shift register that uses Cat for bit shifting.",
        "Write a {depth}-stage shift register using chisel3.util.Cat.",
        "Build a SIPO register using bit concatenation.",
    ],
}

# ==========================================
# 3. 生成函数
# ==========================================

def get_instruction(category, **kwargs):
    """获取随机指令"""
    template = random.choice(INSTRUCTIONS[category])
    return template.format(**kwargs)

def generate_fsm_enum(index):
    """生成 Enum FSM 样本"""
    variant = random.choice(["2state", "3state", "4state"])
    prefixes = ["Auto", "Smart", "Fast", "Quick", "Simple"]
    
    if variant == "2state":
        nouns = ["ToggleFSM", "Flipper", "PingPong", "Alternator"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        t = Template(TEMPLATE_FSM_ENUM_LIST)
        code = t.render(module_name=module_name).strip()
        instruction = get_instruction("fsm_enum_2state")
    elif variant == "3state":
        nouns = ["TaskFSM", "WorkflowCtrl", "ProcessFSM", "StateMgr"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        t = Template(TEMPLATE_FSM_ENUM_3STATE)
        code = t.render(module_name=module_name).strip()
        instruction = get_instruction("fsm_enum_3state")
    else:  # 4state
        nouns = ["HandshakeFSM", "ProtocolCtrl", "ReqAckFSM", "MultiStageFSM"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        t = Template(TEMPLATE_FSM_ENUM_4STATE)
        code = t.render(module_name=module_name).strip()
        instruction = get_instruction("fsm_enum_4state")
    
    return module_name, instruction, code

def generate_popcount(index):
    """生成 PopCount 样本"""
    width = random.choice([4, 8, 16, 32])
    count_width = (width - 1).bit_length() + 1
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["PopCounter", "BitCounter", "OnesCount", "SetBitCount"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_POPCOUNT)
    code = t.render(module_name=module_name, width=width, count_width=count_width).strip()
    instruction = get_instruction("popcount", width=width)
    
    return module_name, instruction, code

def generate_reverse(index):
    """生成 Reverse 样本"""
    width = random.choice([4, 8, 16, 32])
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["BitReverser", "Reverser", "BitFlip", "MirrorBits"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_REVERSE)
    code = t.render(module_name=module_name, width=width).strip()
    instruction = get_instruction("reverse", width=width)
    
    return module_name, instruction, code

def generate_fill(index):
    """生成 Fill 样本"""
    width = random.choice([4, 8, 16])
    times = random.choice([2, 4, 8])
    total_width = width * times
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["BitFill", "Replicator", "BitExpand", "Duplicator"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_FILL)
    code = t.render(module_name=module_name, width=width, times=times, total_width=total_width).strip()
    instruction = get_instruction("fill", width=width, times=times)
    
    return module_name, instruction, code

def generate_log2(index):
    """生成 Log2 样本"""
    width = random.choice([8, 16, 32])
    log_width = (width - 1).bit_length()
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["Log2Calc", "BitPosition", "HighBitFinder", "Log2Unit"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_LOG2)
    code = t.render(module_name=module_name, width=width, log_width=log_width).strip()
    instruction = get_instruction("log2", width=width)
    
    return module_name, instruction, code

def generate_priority_encoder(index):
    """生成 PriorityEncoder 样本"""
    width = random.choice([4, 8, 16])
    enc_width = (width - 1).bit_length()
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["PriorityEnc", "LowBitFinder", "PrioEncoder", "FirstOne"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_PRIORITY_ENCODER)
    code = t.render(module_name=module_name, width=width, enc_width=enc_width).strip()
    instruction = get_instruction("priority_encoder", width=width)
    
    return module_name, instruction, code

def generate_oh_to_uint(index):
    """生成 OHToUInt 样本"""
    width = random.choice([4, 8, 16])
    enc_width = (width - 1).bit_length()
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["OHDecoder", "OneHotToBin", "OHConverter", "OneHotDec"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_OH_TO_UINT)
    code = t.render(module_name=module_name, width=width, enc_width=enc_width).strip()
    instruction = get_instruction("oh_to_uint", width=width)
    
    return module_name, instruction, code

def generate_uint_to_oh(index):
    """生成 UIntToOH 样本"""
    width = random.choice([4, 8, 16])
    enc_width = (width - 1).bit_length()
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["OHEncoder", "BinToOneHot", "OHGenerator", "OneHotEnc"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_UINT_TO_OH)
    code = t.render(module_name=module_name, width=width, enc_width=enc_width).strip()
    instruction = get_instruction("uint_to_oh", width=width)
    
    return module_name, instruction, code

def generate_mux1h(index):
    """生成 Mux1H 样本"""
    width = random.choice([8, 16, 32])
    
    prefixes = ["Util", "Bit", "Logic", "Fast"]
    nouns = ["Mux1H", "OneHotMux", "OHSelector", "OneHotSwitch"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_MUX1H)
    code = t.render(module_name=module_name, width=width).strip()
    instruction = get_instruction("mux1h", width=width)
    
    return module_name, instruction, code

def generate_shift_cat(index):
    """生成使用 Cat 的移位寄存器样本"""
    depth = random.choice([4, 8, 16])
    
    prefixes = ["Cycle", "Data", "Sync", "Fast"]
    nouns = ["ShiftPipe", "CatShift", "BitShifter", "ConcatReg"]
    module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
    
    t = Template(TEMPLATE_SHIFT_REG_CAT)
    code = t.render(module_name=module_name, depth=depth, depth_minus_2=depth-2).strip()
    instruction = get_instruction("shift_cat", depth=depth)
    
    return module_name, instruction, code

# ==========================================
# 4. 验证与多进程生成
# ==========================================

# 生成器配置: (名称, 生成函数, 目标数量)
GENERATORS = [
    ("fsm_enum", generate_fsm_enum, 100),      # Enum FSM - 重点补充!
    ("popcount", generate_popcount, 50),
    ("reverse", generate_reverse, 50),
    ("fill", generate_fill, 50),
    ("log2", generate_log2, 50),
    ("priority_encoder", generate_priority_encoder, 50),
    ("oh_to_uint", generate_oh_to_uint, 50),
    ("uint_to_oh", generate_uint_to_oh, 50),
    ("mux1h", generate_mux1h, 50),
    ("shift_cat", generate_shift_cat, 50),    # Cat 移位 - 额外强化
]

def validate_code(code, module_name):
    """验证代码"""
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
        return result['compiled'] and result['elaborated']
    except Exception as e:
        return False

def worker_task(args):
    """多进程工作函数"""
    index, seed, gen_type = args
    random.seed(seed)
    
    # 根据类型选择生成器
    gen_map = {
        "fsm_enum": generate_fsm_enum,
        "popcount": generate_popcount,
        "reverse": generate_reverse,
        "fill": generate_fill,
        "log2": generate_log2,
        "priority_encoder": generate_priority_encoder,
        "oh_to_uint": generate_oh_to_uint,
        "uint_to_oh": generate_uint_to_oh,
        "mux1h": generate_mux1h,
        "shift_cat": generate_shift_cat,
    }
    
    gen_func = gen_map.get(gen_type)
    if not gen_func:
        return None
    
    try:
        module_name, instruction, code = gen_func(index)
        
        if validate_code(code, module_name):
            return {
                "instruction": instruction,
                "input": "",
                "output": code,
                "type": gen_type
            }
        return None
    except Exception as e:
        return None

def main():
    print("=" * 60)
    print("🔧 生成缺失的 chisel3.util 样本 (多进程加速)")
    print("=" * 60)
    
    # 计算总目标数
    total_target = sum(count for _, _, count in GENERATORS)
    print(f"📊 总目标样本数: {total_target}")
    
    # 自动检测 CPU 核心数，但限制最大值避免内存压力
    num_processes = min(multiprocessing.cpu_count(), 4)
    if len(sys.argv) > 1:
        try:
            num_processes = int(sys.argv[1])
        except:
            pass
    
    print(f"⚡ 启用多进程加速: {num_processes} workers")
    print("⏳ JVM 预热中，请稍候...")
    
    # 构建任务列表：为每种类型生成足够的任务
    tasks = []
    base_seed = random.randint(0, 100000)
    task_index = 0
    
    for gen_name, _, target_count in GENERATORS:
        # 多生成一些以应对验证失败
        for i in range(int(target_count * 1.5)):
            tasks.append((task_index, base_seed + task_index, gen_name))
            task_index += 1
    
    # 打乱任务顺序，使不同类型交错执行
    random.shuffle(tasks)
    
    # 统计各类型已生成数量
    type_counts = {name: 0 for name, _, _ in GENERATORS}
    type_targets = {name: count for name, _, count in GENERATORS}
    
    all_samples = []
    
    # 创建进程池
    print(f"🔧 创建进程池 (workers={num_processes})...")
    pool = multiprocessing.Pool(processes=num_processes)
    
    # 使用 tqdm 显示进度
    pbar = tqdm(total=total_target, desc="生成进度", dynamic_ncols=True)
    
    try:
        # 使用 imap_unordered 获取结果
        for result in pool.imap_unordered(worker_task, tasks):
            if result is not None:
                gen_type = result.pop("type")
                
                # 检查该类型是否已达到目标
                if type_counts[gen_type] < type_targets[gen_type]:
                    type_counts[gen_type] += 1
                    all_samples.append(result)
                    pbar.update(1)
                    
                    # 更新进度条描述
                    done = sum(type_counts.values())
                    pbar.set_postfix({"done": done, "rate": f"{len(all_samples)}/{done}"})
            
            # 检查是否全部完成
            if all(type_counts[name] >= type_targets[name] for name in type_counts):
                break
                
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，保存已生成的数据...")
    finally:
        pbar.close()
        pool.terminate()
        pool.join()
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"dataset/chisel_util_supplement_{timestamp}.jsonl"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    print(f"\n" + "=" * 60)
    print(f"✅ 补充数据集已保存: {output_file}")
    print(f"📦 总样本数: {len(all_samples)}")
    print("=" * 60)
    
    # 统计各类型
    print("\n📊 各类型生成统计:")
    for gen_name, _, target in GENERATORS:
        actual = type_counts[gen_name]
        status = "✅" if actual >= target else "⚠️"
        print(f"  {status} {gen_name}: {actual}/{target}")
    
    return output_file

if __name__ == "__main__":
    main()
