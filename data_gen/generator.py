import random
import json
import os
import sys
import multiprocessing
from contextlib import redirect_stdout, redirect_stderr
from jinja2 import Template
from tqdm import tqdm

# ==========================================
# 0. 环境配置与导入
# ==========================================

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
src_dir = os.path.join(parent_dir, 'src')
sys.path.insert(0, src_dir)

try:
    from reflect_env import reflect
    print(f"✅ 成功导入 reflect_env (路径: {src_dir})")
except ImportError:
    print(f"❌ 错误: 无法导入 reflect_env。请确保 src/reflect_env.py 存在。")
    sys.exit(1)

# ==========================================
# 1. 定义 Jinja2 模板 (Templates)
# ==========================================

# --- Level 1: 基础类型定义 (60%) ---

TEMPLATE_BASIC_TYPE = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val out = Output({{ type_class }}({{ width }}.W))
  })
  // Task: Define a {{ type_class }} {{ kind }} named '{{ var_name }}'
  val {{ var_name }} = {{ kind }}({{ type_class }}({{ width }}.W))
  
  {% if kind == "Reg" %}
  {{ var_name }} := 0.U.asTypeOf({{ var_name }})
  {% elif kind == "Wire" %}
  {{ var_name }} := 0.U.asTypeOf({{ var_name }})
  {% endif %}

  io.out := {{ var_name }}
}
"""

TEMPLATE_VEC = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val out = Output(Vec({{ size }}, {{ type_class }}({{ width }}.W)))
  })
  // Task: Define a Vec of {{ size }} {{ type_class }}s
  val {{ var_name }} = Wire(Vec({{ size }}, {{ type_class }}({{ width }}.W)))
  
  for (i <- 0 until {{ size }}) {
    {{ var_name }}(i) := 0.U.asTypeOf({{ type_class }}({{ width }}.W))
  }

  io.out := {{ var_name }}
}
"""

TEMPLATE_BUNDLE = """
import chisel3._

class MyBundle_{{ index }} extends Bundle {
  val field1 = UInt({{ width }}.W)
  val field2 = Bool()
}

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val out = Output(new MyBundle_{{ index }})
  })
  
  val {{ var_name }} = Wire(new MyBundle_{{ index }})
  {{ var_name }}.field1 := 123.U
  {{ var_name }}.field2 := true.B
  
  io.out := {{ var_name }}
}
"""

# --- Level 2: 基础组合逻辑 (30%) ---

TEMPLATE_ARITHMETIC = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt({{ width }}.W))
    val b = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // Logic: {{ op_name }}
  io.out := io.a {{ op_symbol }} io.b
}
"""

TEMPLATE_MUX = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val sel = Input(Bool())
    val a = Input(UInt({{ width }}.W))
    val b = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // Logic: 2-to-1 Mux
  io.out := Mux(io.sel, io.a, io.b)
}
"""

TEMPLATE_WHEN = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val cond = Input(Bool())
    val a = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  io.out := 0.U
  
  when (io.cond) {
    io.out := io.a
  } .otherwise {
    io.out := 0.U
  }
}
"""

# --- Level 3: 简单时序逻辑 (10%) ---

TEMPLATE_COUNTER = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val en = Input(Bool())
    val out = Output(UInt({{ width }}.W))
  })
  
  val cnt = RegInit(0.U({{ width }}.W))
  
  when (io.en) {
    cnt := cnt + 1.U
  }
  
  io.out := cnt
}
"""

TEMPLATE_SHIFT_REG = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  val r1 = RegNext(io.in)
  val r2 = RegNext(r1)
  
  io.out := r2
}
"""

# ==========================================
# 2. 生成函数
# ==========================================

def generate_level1(index):
    """Level 1: 语法肌肉记忆 (Wire, Reg, Vec, Bundle)"""
    subtype = random.choice(["basic", "vec", "bundle"])
    width = random.randint(2, 32)
    
    # 语义化命名词库
    prefixes = ["Simple", "Basic", "My", "Test", "Local", "Global"]
    
    if subtype == "basic":
        kind = random.choice(["Wire", "Reg"])
        type_class = random.choice(["UInt", "SInt", "Bool"])
        if type_class == "Bool": width = 1
        
        # 命名策略: [Prefix][Type][Kind] e.g. SimpleUIntReg
        base_name = f"{type_class}{kind}" if random.random() > 0.5 else kind
        module_name = f"{random.choice(prefixes)}{base_name}_{index}"
        
        var_name = f"v_{random.randint(100, 999)}"
        
        t = Template(TEMPLATE_BASIC_TYPE)
        code = t.render(module_name=module_name, type_class=type_class, width=width, kind=kind, var_name=var_name)
        instruction = f"Define a {width}-bit {type_class} {kind} named '{var_name}'."
        
    elif subtype == "vec":
        size = random.randint(2, 8)
        
        # 命名策略: [Prefix][Noun] e.g. BasicDataBus
        nouns = ["Vec", "Array", "Bus", "Buffer"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        var_name = f"vec_{random.randint(100, 999)}"
        
        t = Template(TEMPLATE_VEC)
        code = t.render(module_name=module_name, size=size, type_class="UInt", width=width, var_name=var_name)
        instruction = f"Define a Wire Vec of {size} UInts, each {width}-bit wide."
        
    else: # bundle
        # 命名策略: [Prefix][Noun] e.g. CustomPacket
        nouns = ["Bundle", "Packet", "Struct", "Interface"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        var_name = f"blob_{random.randint(100, 999)}"
        
        t = Template(TEMPLATE_BUNDLE)
        code = t.render(module_name=module_name, index=index, width=width, var_name=var_name)
        instruction = f"Define a Bundle with a {width}-bit UInt and a Bool, then instantiate it."

    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

def generate_level2(index):
    """Level 2: 基础组合逻辑 (Arithmetic, Mux, When)"""
    subtype = random.choice(["arith", "mux", "when"])
    width = random.randint(4, 32)
    
    prefixes = ["Fast", "Simple", "Bitwise", "Math", "Logic"]
    
    if subtype == "arith":
        ops = [("+", "addition"), ("-", "subtraction"), ("&", "bitwise AND"), ("|", "bitwise OR"), ("^", "bitwise XOR")]
        op_symbol, op_name = random.choice(ops)
        
        # 命名策略: 根据操作符决定核心名词
        op_map = {
            "+": ["Adder", "Sum", "Plus"],
            "-": ["Subtractor", "Diff", "Minus"],
            "&": ["AndGate", "Mask"],
            "|": ["OrGate", "Merge"],
            "^": ["XorGate", "Parity"]
        }
        base = random.choice(op_map.get(op_symbol, ["ALU"]))
        module_name = f"{random.choice(prefixes)}{base}_{index}"
        
        t = Template(TEMPLATE_ARITHMETIC)
        code = t.render(module_name=module_name, width=width, op_symbol=op_symbol, op_name=op_name)
        instruction = f"Implement a module performing {op_name} on two {width}-bit inputs."
        
    elif subtype == "mux":
        # 命名策略: Mux 相关
        nouns = ["Mux", "Selector", "Switch", "Chooser"]
        module_name = f"{random.choice(['Data', 'Signal', 'Path'])}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_MUX)
        code = t.render(module_name=module_name, width=width)
        instruction = f"Implement a 2-to-1 Multiplexer for {width}-bit signals."
        
    else: # when
        # 命名策略: 逻辑控制相关
        nouns = ["Controller", "Logic", "Flow", "Decider"]
        module_name = f"{random.choice(['Status', 'Cond', 'Branch'])}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_WHEN)
        code = t.render(module_name=module_name, width=width)
        instruction = f"Use 'when' to assign output based on a condition."

    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

def generate_level3(index):
    """Level 3: 简单时序逻辑 (Counter, ShiftReg)"""
    subtype = random.choice(["counter", "shift"])
    width = random.randint(4, 16)
    
    prefixes = ["Cycle", "Event", "Pulse", "Data", "Sync"]
    
    if subtype == "counter":
        # 命名策略: 计数器相关
        nouns = ["Counter", "Timer", "Ticker", "Watchdog"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_COUNTER)
        code = t.render(module_name=module_name, width=width)
        instruction = f"Implement a {width}-bit counter with enable signal."
        
    else: # shift
        # 命名策略: 移位寄存器相关
        nouns = ["ShiftReg", "DelayLine", "Pipeline", "Buffer"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_SHIFT_REG)
        code = t.render(module_name=module_name, width=width)
        instruction = f"Implement a 2-stage shift register."

    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

# ==========================================
# 3. 验证与主循环
# ==========================================

def validate_code(code, module_name):
    try:
        result = reflect(
            chisel_code_string=code,
            module_name=module_name,
            testbench_path=None,
            output_dir=None,
            verilog_file=None,
            result_file=None,
            silent=True  # 开启静默模式，避免干扰 tqdm 进度条
        )
        return result['compiled'] and result['elaborated']
    except Exception as e:
        return False

def worker_task(args):
    """多进程工作函数"""
    index, seed = args
    # 每个进程需要独立的随机种子
    random.seed(seed)
    
    try:
        r = random.random()
        if r < 0.6:
            sample = generate_level1(index)
        elif r < 0.9:
            sample = generate_level2(index)
        else:
            sample = generate_level3(index)
            
        if validate_code(sample["entry"]["output"], sample["module_name"]):
            return sample["entry"]
        return None
    except Exception as e:
        # 如果需要调试，可以取消注释下面这行
        # print(f"Worker {index} failed: {e}")
        return None

def main():
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(line_buffering=True)  # type: ignore
            sys.stderr.reconfigure(line_buffering=True)  # type: ignore
    except (AttributeError, TypeError):
        # 如果 reconfigure 不可用，忽略错误
        pass
    
    # 默认生成 100 条用于测试，实际使用时可改为 10000
    TARGET_COUNT = 100
    if len(sys.argv) > 1:
        try:
            TARGET_COUNT = int(sys.argv[1])
        except:
            pass
            
    # 自动检测 CPU 核心数
    # 优化策略: 
    # 1. sbt/JVM 非常吃内存，并行度过高会导致内存溢出或 Swap，反而变慢
    # 2. 编译是 CPU 密集型，保留一半核心给系统和其他进程响应
    cpu_count = os.cpu_count() or 4
    # 默认使用一半的核心，且至少为 1
    default_workers = max(1, cpu_count // 2)
    
    # 允许通过命令行参数指定 worker 数量: python generator.py [count] [workers]
    num_processes = default_workers
    if len(sys.argv) > 2:
        try:
            num_processes = int(sys.argv[2])
        except:
            pass
    
    print(f"🚀 启动 Chisel 合成数据引擎 (Target: {TARGET_COUNT})", flush=True)
    print(f"⚡ 启用多进程加速: {num_processes} workers", flush=True)
    print("📊 课程分布: Level 1 (60%) | Level 2 (30%) | Level 3 (10%)", flush=True)
    print("⏳ 正在初始化并行工作进程 (JVM 预热可能需要几十秒，期间进度条可能不会更新，请耐心等待)...", flush=True)
    
    valid_dataset = []
    
    # 关键修复: 使用 dynamic_ncols=True 适配终端, mininterval=0.5 提高刷新率
    pbar = tqdm(total=TARGET_COUNT, miniters=1, dynamic_ncols=True, mininterval=0.5)
    
    # 创建进程池
    print(f"🔧 创建进程池 (workers={num_processes})...", flush=True)
    pool = multiprocessing.Pool(processes=num_processes)
    print(f"✅ 进程池已创建", flush=True)
    
    # 提交任务：根据经验，模板生成的代码通过率很高 (>90%)
    # 设置 1.5 倍冗余即可，避免生成过多的任务列表
    redundancy_factor = 1.5
    total_tasks = int(TARGET_COUNT * redundancy_factor)
    tasks = [(i, random.randint(0, 1000000000)) for i in range(total_tasks)]
    
    attempts = 0
    try:
        # chunksize=1 确保结果一出来就更新，而不是攒一批
        for result in pool.imap_unordered(worker_task, tasks, chunksize=1):
            attempts += 1
            if result:
                valid_dataset.append(result)
                pbar.update(1)
            
            # 实时更新状态：显示尝试次数和当前通过率
            pbar.set_postfix({
                "attempts": attempts, 
                "rate": f"{len(valid_dataset)/attempts:.1%}"
            })
                
            if len(valid_dataset) >= TARGET_COUNT:
                # 达到目标后立即终止进程池，避免等待剩余任务
                pool.terminate()
                break
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，正在保存已生成的数据...")
        pool.terminate()
    finally:
        pool.join()  # 等待所有子进程真正退出（释放资源）
        pbar.close()
    
    output_dir = os.path.join(parent_dir, "dataset")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "chisel_sft_dataset.jsonl")
    
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in valid_dataset:
            f.write(json.dumps(entry) + "\n")
            
    print(f"✅ 数据集生成完毕: {output_file}")
    print(f"📦 总有效样本数: {len(valid_dataset)}")

if __name__ == "__main__":
    main()
