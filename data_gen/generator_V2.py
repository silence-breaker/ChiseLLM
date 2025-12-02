import random
import json
import os
import sys
import multiprocessing
from contextlib import redirect_stdout, redirect_stderr
from jinja2 import Template
from tqdm import tqdm
from datetime import datetime

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
# 0.5 错误日志管理
# ==========================================

ERROR_LOG_FILE = None

def init_error_log():
    """初始化错误日志文件"""
    global ERROR_LOG_FILE
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = os.path.join(parent_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    ERROR_LOG_FILE = os.path.join(log_dir, f"generation_errors_{timestamp}.log")
    
def log_error(log_file, index, module_name, error_info):
    """记录验证失败的样本信息"""
    if log_file:  # 使用传入的参数，而非全局变量
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Index: {index} | Module: {module_name}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write(f"Error: {error_info}\n")
        except:
            pass

# ==========================================
# 1. 指令多样性池 (Instruction Pool)
# ==========================================

INSTRUCTION_TEMPLATES = {
    "basic_type": [
        "Define a {width}-bit {type_class} {kind} named '{var_name}'.",
        "Create a {kind} of type {type_class} with {width} bits, call it '{var_name}'.",
        "I need a {width}-bit {type_class} {kind} variable '{var_name}'.",
        "Implement a {kind} named '{var_name}' that holds a {width}-bit {type_class}.",
        "Write code to declare a {type_class} {kind} '{var_name}' with width {width}."
    ],
    "vec": [
        "Define a Wire Vec of {size} UInts, each {width}-bit wide.",
        "Create a vector containing {size} elements of {width}-bit UInts.",
        "I need a Vec with {size} UInt({width}.W) elements.",
        "Implement a {size}-element vector where each element is {width} bits.",
        "Write a Vec declaration with {size} {width}-bit unsigned integers."
    ],
    "bundle": [
        "Define a Bundle with a {width}-bit UInt and a Bool, then instantiate it.",
        "Create a custom Bundle containing a UInt({width}.W) and a Bool.",
        "I need a Bundle structure with a {width}-bit integer field and a boolean field.",
        "Implement a Bundle that packages a {width}-bit UInt and a Bool together.",
        "Write a Bundle definition with field1 as {width}-bit UInt and field2 as Bool."
    ],
    "arithmetic": [
        "Implement a module performing {op_name} on two {width}-bit inputs.",
        "Create a {width}-bit {op_name} circuit.",
        "I need a module that computes {op_name} for {width}-bit operands.",
        "Write an {op_name} unit for {width}-bit signals.",
        "Build a {width}-bit {op_name} logic block."
    ],
    "mux": [
        "Implement a 2-to-1 Multiplexer for {width}-bit signals.",
        "Create a {width}-bit Mux that selects between two inputs.",
        "I need a 2-to-1 Mux for {width}-bit data paths.",
        "Write a multiplexer that chooses between two {width}-bit signals.",
        "Build a {width}-bit selector circuit (2-to-1 Mux)."
    ],
    "when": [
        "Use 'when' to assign output based on a condition.",
        "Create a conditional assignment using 'when' statement.",
        "I need conditional logic implemented with 'when'.",
        "Write a module that uses 'when' for conditional output.",
        "Implement conditional behavior using Chisel's 'when' syntax."
    ],
    "counter": [
        "Implement a {width}-bit counter with enable signal.",
        "Create a {width}-bit counter that increments when enabled.",
        "I need a {width}-bit up-counter with an enable input.",
        "Write a counter module with {width} bits and enable control.",
        "Build a {width}-bit counter that counts up on enable."
    ],
    "shift_reg": [
        "Implement a 2-stage shift register.",
        "Create a 2-stage pipeline register.",
        "I need a shift register with 2 delay stages.",
        "Write a 2-cycle delay line using registers.",
        "Build a 2-stage shift register chain."
    ],
    "cat": [
        "Concatenate two {width}-bit signals into a {total_width}-bit output.",
        "Use Cat to combine two {width}-bit inputs.",
        "I need to concatenate two {width}-bit signals.",
        "Write a module that uses Cat to merge two {width}-bit signals.",
        "Build a bit concatenation circuit for two {width}-bit inputs."
    ],
    "slice": [
        "Extract bits {high} to {low} from a {width}-bit input.",
        "Create a bit slicer that extracts bits [{high}:{low}] from {width}-bit signal.",
        "I need to slice bits {high} down to {low} from a {width}-bit input.",
        "Write a module that extracts a bit range from a {width}-bit signal.",
        "Implement bit extraction for range [{high}:{low}] from {width} bits."
    ],
    "mux_case": [
        "Implement a {num_cases}-way multiplexer using MuxCase.",
        "Create a priority multiplexer with {num_cases} cases.",
        "I need a MuxCase with {num_cases} input options.",
        "Write a priority selector using MuxCase for {num_cases} choices.",
        "Build a {num_cases}-input priority mux with MuxCase."
    ],
    "fsm": [
        "Implement a {num_states}-state FSM.",
        "Create a finite state machine with {num_states} states.",
        "I need an FSM with {num_states} states: {state_names}.",
        "Write a state machine that transitions between {num_states} states.",
        "Build a {num_states}-state FSM using Chisel Enum."
    ],
    "fsm_toggle": [
        "Implement a toggle FSM with ON and OFF states.",
        "Create a 2-state FSM that toggles between ON and OFF.",
        "I need a simple ON/OFF state machine with a toggle input.",
        "Write an FSM that switches states when toggle is asserted.",
        "Build a 2-state toggle FSM using Enum."
    ],
    "shift_cat": [
        "Implement a {stages}-stage shift register using bit concatenation.",
        "Create a {stages}-cycle delay line using Cat.",
        "I need a shift register with {stages} stages using Cat for shifting.",
        "Write a {stages}-stage shift register that uses Cat to shift bits.",
        "Build a shift register using Cat to concatenate bits."
    ],
    "popcount": [
        "Count the number of 1-bits in a {width}-bit input.",
        "Implement a population count for {width}-bit signal.",
        "I need a module that counts set bits in a {width}-bit input.",
        "Write a bit counter using PopCount for {width} bits.",
        "Build a popcount circuit for {width}-bit data."
    ],
    "reverse": [
        "Reverse the bit order of a {width}-bit input.",
        "Implement bit reversal for a {width}-bit signal.",
        "I need to reverse the bits of a {width}-bit input.",
        "Write a module that reverses bit order using Reverse.",
        "Build a {width}-bit bit-reversal circuit."
    ],
    "fill": [
        "Replicate a {width}-bit input {times} times.",
        "Create a bit replicator that copies input {times} times.",
        "I need to duplicate a {width}-bit signal {times} times.",
        "Write a module using Fill to replicate bits.",
        "Build a bit replication circuit with {times}x expansion."
    ],
    "log2": [
        "Compute log2 of a {width}-bit input.",
        "Find the position of the highest set bit in {width}-bit input.",
        "I need to calculate log2 of a {width}-bit signal.",
        "Write a module that computes Log2 for {width} bits.",
        "Build a log2 calculator for {width}-bit data."
    ],
    "priority_encoder": [
        "Implement a priority encoder for {width}-bit input.",
        "Create a circuit that finds the lowest set bit in {width} bits.",
        "I need a priority encoder for a {width}-bit signal.",
        "Write a priority encoder using PriorityEncoder.",
        "Build a {width}-bit priority encoder."
    ],
    "onehot_convert": [
        "Convert one-hot encoding to binary for {width} bits.",
        "Implement one-hot to binary conversion.",
        "I need to decode a {width}-bit one-hot signal to binary.",
        "Write a one-hot decoder using OHToUInt.",
        "Build a one-hot to binary converter."
    ],
    "binary_to_onehot": [
        "Convert binary to one-hot encoding.",
        "Implement binary to one-hot conversion for {enc_width}-bit input.",
        "I need to encode binary to {width}-bit one-hot.",
        "Write a binary to one-hot encoder using UIntToOH.",
        "Build a binary to one-hot converter."
    ],
    "mux1h": [
        "Implement a one-hot multiplexer for {width}-bit data.",
        "Create a Mux1H with 4 inputs of {width} bits each.",
        "I need a one-hot mux for {width}-bit signals.",
        "Write a multiplexer using Mux1H for one-hot selection.",
        "Build a 4-input one-hot multiplexer."
    ]
}

def get_random_instruction(template_key, **kwargs):
    """从指令池中随机选择一个模板并填充参数"""
    templates = INSTRUCTION_TEMPLATES.get(template_key, [])
    if not templates:
        return ""
    template = random.choice(templates)
    return template.format(**kwargs)

# ==========================================
# 2. 定义 Jinja2 模板 (Templates)
# ==========================================

# --- Level 1: 基础类型定义 (50%) ---

TEMPLATE_BASIC_TYPE = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val out = Output({{ type_class }}({% if type_class != 'Bool' %}{{ width }}.W{% endif %}))
  })
  // Task: Define a {{ type_class }} {{ kind }} named '{{ var_name }}'
  val {{ var_name }} = {{ kind }}({{ type_class }}({% if type_class != 'Bool' %}{{ width }}.W{% endif %}))
  
  {% if kind == "Reg" %}
  {{ var_name }} := {% if type_class == 'Bool' %}false.B{% else %}0.U.asTypeOf({{ var_name }}){% endif %}
  {% elif kind == "Wire" %}
  {{ var_name }} := {% if type_class == 'Bool' %}false.B{% else %}0.U.asTypeOf({{ var_name }}){% endif %}
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

// 添加 {{ suffix }} 确保全局唯一性
class MyBundle_{{ index }}_{{ suffix }} extends Bundle {
  val field1 = UInt({{ width }}.W)
  val field2 = Bool()
}

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val out = Output(new MyBundle_{{ index }}_{{ suffix }})
  })
  
  val {{ var_name }} = Wire(new MyBundle_{{ index }}_{{ suffix }})
  {{ var_name }}.field1 := 123.U
  {{ var_name }}.field2 := true.B
  
  io.out := {{ var_name }}
}
"""

# --- Level 2: 基础组合逻辑 (35%) ---

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

# 新增: Cat (位拼接)
TEMPLATE_CAT = """
import chisel3._
import chisel3.util.Cat

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val high = Input(UInt({{ width }}.W))
    val low = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ total_width }}.W))
  })
  
  // Concatenate high and low parts
  io.out := Cat(io.high, io.low)
}
"""

# 新增: Slice (位截取)
TEMPLATE_SLICE = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ slice_width }}.W))
  })
  
  // Extract bits [{{ high }}:{{ low }}]
  io.out := io.in({{ high }}, {{ low }})
}
"""

# 新增: MuxCase (多路条件选择)
TEMPLATE_MUXCASE = """
import chisel3._
import chisel3.util.MuxCase

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val sel = Input(UInt({{ sel_width }}.W))
    val in0 = Input(UInt({{ width }}.W))
    val in1 = Input(UInt({{ width }}.W))
    val in2 = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // Priority-based multiplexing
  io.out := MuxCase(0.U, Seq(
    (io.sel === 0.U) -> io.in0,
    (io.sel === 1.U) -> io.in1,
    (io.sel === 2.U) -> io.in2
  ))
}
"""

# --- Level 3: 时序逻辑与状态机 (15%) ---

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

# 新增: 使用 Cat 的移位寄存器变体 (针对性训练 import chisel3.util.Cat)
TEMPLATE_SHIFT_REG_CAT = """
import chisel3._
import chisel3.util.Cat

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt(1.W))
    val out = Output(UInt(1.W))
  })
  
  // {{ stages }}-stage shift register using Cat
  val reg = RegInit(0.U({{ stages }}.W))
  reg := Cat(reg({{ stages_minus_2 }}, 0), io.in)
  
  io.out := reg({{ stages_minus_1 }})
}
"""

# 新增: FSM (有限状态机) - 使用 Enum 列表解构 (针对性训练)
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

# 新增: FSM (有限状态机)
TEMPLATE_FSM = """
import chisel3._
import chisel3.util._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val start = Input(Bool())
    val done = Output(Bool())
  })
  
  // Define states using ChiselEnum
  object State extends ChiselEnum {
    val sIdle, sBusy, sDone = Value
  }
  import State._
  
  val state = RegInit(sIdle)
  
  // State transition logic
  switch (state) {
    is (sIdle) {
      when (io.start) {
        state := sBusy
      }
    }
    is (sBusy) {
      state := sDone
    }
    is (sDone) {
      state := sIdle
    }
  }
  
  // Output logic
  io.done := state === sDone
}
"""

# ==========================================
# 新增: Level 2.5 - chisel3.util 专项训练
# ==========================================

# 使用 PopCount (计算 1 的个数)
TEMPLATE_POPCOUNT = """
import chisel3._
import chisel3.util.PopCount

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val count = Output(UInt({{ count_width }}.W))
  })
  
  // Count the number of 1s in input
  io.count := PopCount(io.in)
}
"""

# 使用 Reverse (位反转)
TEMPLATE_REVERSE = """
import chisel3._
import chisel3.util.Reverse

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // Reverse bit order
  io.out := Reverse(io.in)
}
"""

# 使用 Fill (位复制)
TEMPLATE_FILL = """
import chisel3._
import chisel3.util.Fill

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ total_width }}.W))
  })
  
  // Replicate input {{ times }} times
  io.out := Fill({{ times }}, io.in)
}
"""

# 使用 Log2 (计算 log2)
TEMPLATE_LOG2 = """
import chisel3._
import chisel3.util.Log2

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ log_width }}.W))
  })
  
  // Compute log2 of input (position of highest 1 bit)
  io.out := Log2(io.in)
}
"""

# 使用 PriorityEncoder (优先编码器)
TEMPLATE_PRIORITY_ENCODER = """
import chisel3._
import chisel3.util.PriorityEncoder

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ enc_width }}.W))
  })
  
  // Priority encoder: returns index of lowest set bit
  io.out := PriorityEncoder(io.in)
}
"""

# 使用 OHToUInt (独热码转二进制)
TEMPLATE_OH_TO_UINT = """
import chisel3._
import chisel3.util.OHToUInt

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ width }}.W))
    val out = Output(UInt({{ enc_width }}.W))
  })
  
  // Convert one-hot encoding to binary
  io.out := OHToUInt(io.in)
}
"""

# 使用 UIntToOH (二进制转独热码)
TEMPLATE_UINT_TO_OH = """
import chisel3._
import chisel3.util.UIntToOH

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val in = Input(UInt({{ enc_width }}.W))
    val out = Output(UInt({{ width }}.W))
  })
  
  // Convert binary to one-hot encoding
  io.out := UIntToOH(io.in)
}
"""

# 使用 Mux1H (独热码多路选择器)
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
  io.out := Mux1H(io.sel, Seq(io.in0, io.in1, io.in2, io.in3))
}
"""

# ==========================================
# 3. 生成函数
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
        code = t.render(module_name=module_name, type_class=type_class, width=width, kind=kind, var_name=var_name).strip()
        instruction = get_random_instruction("basic_type", width=width, type_class=type_class, kind=kind, var_name=var_name)
        
    elif subtype == "vec":
        size = random.randint(2, 8)
        
        # 命名策略: [Prefix][Noun] e.g. BasicDataBus
        nouns = ["Vec", "Array", "Bus", "Buffer"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        var_name = f"vec_{random.randint(100, 999)}"
        
        t = Template(TEMPLATE_VEC)
        code = t.render(module_name=module_name, size=size, type_class="UInt", width=width, var_name=var_name).strip()
        instruction = get_random_instruction("vec", size=size, width=width)
        
    else: # bundle
        # 命名策略: [Prefix][Noun] e.g. CustomPacket
        nouns = ["Bundle", "Packet", "Struct", "Interface"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        var_name = f"blob_{random.randint(100, 999)}"
        suffix = random.randint(1000, 9999)  # 生成随机后缀确保唯一性
        
        t = Template(TEMPLATE_BUNDLE)
        code = t.render(module_name=module_name, index=index, suffix=suffix, width=width, var_name=var_name).strip()
        instruction = get_random_instruction("bundle", width=width)

    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

def generate_level2(index):
    """Level 2: 基础组合逻辑 (Arithmetic, Mux, When, Cat, Slice, MuxCase)"""
    subtype = random.choice(["arith", "mux", "when", "cat", "slice", "muxcase"])
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
        code = t.render(module_name=module_name, width=width, op_symbol=op_symbol, op_name=op_name).strip()
        instruction = get_random_instruction("arithmetic", width=width, op_name=op_name)
        
    elif subtype == "mux":
        # 命名策略: Mux 相关
        nouns = ["Mux", "Selector", "Switch", "Chooser"]
        module_name = f"{random.choice(['Data', 'Signal', 'Path'])}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_MUX)
        code = t.render(module_name=module_name, width=width).strip()
        instruction = get_random_instruction("mux", width=width)
        
    elif subtype == "when":
        # 命名策略: 逻辑控制相关
        nouns = ["Controller", "Logic", "Flow", "Decider"]
        module_name = f"{random.choice(['Status', 'Cond', 'Branch'])}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_WHEN)
        code = t.render(module_name=module_name, width=width).strip()
        instruction = get_random_instruction("when")
    
    elif subtype == "cat":
        # 新增: Cat 位拼接
        nouns = ["Concat", "Merger", "Combiner", "Joiner"]
        module_name = f"{random.choice(['Bit', 'Data', 'Signal'])}{random.choice(nouns)}_{index}"
        
        total_width = width * 2
        t = Template(TEMPLATE_CAT)
        code = t.render(module_name=module_name, width=width, total_width=total_width).strip()
        instruction = get_random_instruction("cat", width=width, total_width=total_width)
    
    elif subtype == "slice":
        # 新增: Slice 位截取
        nouns = ["Slicer", "Extractor", "Range", "BitSelect"]
        module_name = f"{random.choice(['Bit', 'Data', 'Field'])}{random.choice(nouns)}_{index}"
        
        # 确保 high > low 且不超过 width
        low = random.randint(0, width - 2)
        high = random.randint(low + 1, width - 1)
        slice_width = high - low + 1
        
        t = Template(TEMPLATE_SLICE)
        code = t.render(module_name=module_name, width=width, high=high, low=low, slice_width=slice_width).strip()
        instruction = get_random_instruction("slice", width=width, high=high, low=low)
    
    else: # muxcase
        # 新增: MuxCase 多路选择
        nouns = ["PriorityMux", "Selector", "Router", "Switch"]
        module_name = f"{random.choice(['Multi', 'Priority', 'Smart'])}{random.choice(nouns)}_{index}"
        
        sel_width = 2  # 3 个输入需要 2 bit 选择信号
        num_cases = 3
        
        t = Template(TEMPLATE_MUXCASE)
        code = t.render(module_name=module_name, width=width, sel_width=sel_width).strip()
        instruction = get_random_instruction("mux_case", num_cases=num_cases)

    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

def generate_level2_util(index):
    """Level 2.5: chisel3.util 专项训练 (PopCount, Reverse, Fill, Log2, PriorityEncoder, etc.)"""
    subtype = random.choice([
        "popcount", "reverse", "fill", "log2", 
        "priority_encoder", "oh_to_uint", "uint_to_oh", "mux1h"
    ])
    width = random.choice([4, 8, 16, 32])
    
    prefixes = ["Util", "Bit", "Logic", "Fast", "Smart"]
    
    if subtype == "popcount":
        nouns = ["PopCounter", "BitCounter", "OnesCount", "SetBitCount"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        # log2(width) + 1 bits to hold count
        count_width = (width - 1).bit_length() + 1
        
        t = Template(TEMPLATE_POPCOUNT)
        code = t.render(module_name=module_name, width=width, count_width=count_width).strip()
        instruction = get_random_instruction("popcount", width=width)
        
    elif subtype == "reverse":
        nouns = ["BitReverser", "Reverser", "BitFlip", "MirrorBits"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_REVERSE)
        code = t.render(module_name=module_name, width=width).strip()
        instruction = get_random_instruction("reverse", width=width)
        
    elif subtype == "fill":
        nouns = ["BitFill", "Replicator", "BitExpand", "SignExtend"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        times = random.choice([2, 4, 8])
        total_width = width * times
        
        t = Template(TEMPLATE_FILL)
        code = t.render(module_name=module_name, width=width, times=times, total_width=total_width).strip()
        instruction = get_random_instruction("fill", width=width, times=times)
        
    elif subtype == "log2":
        nouns = ["Log2Calc", "BitPosition", "HighBitFinder", "Log2Unit"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        log_width = (width - 1).bit_length()
        
        t = Template(TEMPLATE_LOG2)
        code = t.render(module_name=module_name, width=width, log_width=log_width).strip()
        instruction = get_random_instruction("log2", width=width)
        
    elif subtype == "priority_encoder":
        nouns = ["PriorityEnc", "LowBitFinder", "PrioEncoder", "FirstOne"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        enc_width = (width - 1).bit_length()
        
        t = Template(TEMPLATE_PRIORITY_ENCODER)
        code = t.render(module_name=module_name, width=width, enc_width=enc_width).strip()
        instruction = get_random_instruction("priority_encoder", width=width)
        
    elif subtype == "oh_to_uint":
        nouns = ["OHDecoder", "OneHotToBin", "OHToUInt", "OneHotDec"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        enc_width = (width - 1).bit_length()
        
        t = Template(TEMPLATE_OH_TO_UINT)
        code = t.render(module_name=module_name, width=width, enc_width=enc_width).strip()
        instruction = get_random_instruction("onehot_convert", width=width)
        
    elif subtype == "uint_to_oh":
        nouns = ["OHEncoder", "BinToOneHot", "UIntToOH", "OneHotEnc"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        enc_width = (width - 1).bit_length()
        
        t = Template(TEMPLATE_UINT_TO_OH)
        code = t.render(module_name=module_name, width=width, enc_width=enc_width).strip()
        instruction = get_random_instruction("binary_to_onehot", width=width, enc_width=enc_width)
        
    else:  # mux1h
        nouns = ["Mux1H", "OneHotMux", "OHSelector", "OneHotSwitch"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_MUX1H)
        code = t.render(module_name=module_name, width=width).strip()
        instruction = get_random_instruction("mux1h", width=width)
    
    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

def generate_level3(index):
    """Level 3: 时序逻辑与状态机 (Counter, ShiftReg, FSM) - 含 chisel3.util 变体"""
    # 增加 shift_cat 和 fsm_enum 变体，确保模型学会 import chisel3.util._
    subtype = random.choice(["counter", "shift", "shift_cat", "fsm", "fsm_enum"])
    width = random.randint(4, 16)
    
    prefixes = ["Cycle", "Event", "Pulse", "Data", "Sync"]
    
    if subtype == "counter":
        # 命名策略: 计数器相关
        nouns = ["Counter", "Timer", "Ticker", "Watchdog"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_COUNTER)
        code = t.render(module_name=module_name, width=width).strip()
        instruction = get_random_instruction("counter", width=width)
        
    elif subtype == "shift":
        # 命名策略: 移位寄存器相关 (基础版，不使用 Cat)
        nouns = ["ShiftReg", "DelayLine", "Pipeline", "Buffer"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_SHIFT_REG)
        code = t.render(module_name=module_name, width=width).strip()
        instruction = get_random_instruction("shift_reg")
    
    elif subtype == "shift_cat":
        # 移位寄存器使用 Cat (显式 import chisel3.util._)
        nouns = ["ShiftPipe", "CatShift", "BitShifter", "ConcatReg"]
        module_name = f"{random.choice(prefixes)}{random.choice(nouns)}_{index}"
        
        depth = random.choice([4, 8, 16])
        
        t = Template(TEMPLATE_SHIFT_REG_CAT)
        code = t.render(module_name=module_name, width=width, depth=depth).strip()
        instruction = get_random_instruction("shift_cat", depth=depth)
    
    elif subtype == "fsm":
        # 基础 FSM (ChiselEnum 推导)
        nouns = ["FSM", "StateMachine", "Controller", "Sequencer"]
        module_name = f"{random.choice(['Simple', 'Basic', 'Auto'])}{random.choice(nouns)}_{index}"
        
        num_states = 3
        state_names = "Idle, Busy, Done"
        
        t = Template(TEMPLATE_FSM)
        code = t.render(module_name=module_name).strip()
        instruction = get_random_instruction("fsm", num_states=num_states, state_names=state_names)
    
    else:  # fsm_enum
        # FSM 使用 Enum list 解构 (显式 import chisel3.util._)
        nouns = ["ToggleFSM", "PingPong", "Alternator", "Flipper"]
        module_name = f"{random.choice(['Auto', 'Smart', 'Fast'])}{random.choice(nouns)}_{index}"
        
        t = Template(TEMPLATE_FSM_ENUM_LIST)
        code = t.render(module_name=module_name).strip()
        instruction = get_random_instruction("fsm_toggle")

    return {"module_name": module_name, "entry": {"instruction": instruction, "input": "", "output": code}}

# ==========================================
# 4. 验证与主循环
# ==========================================

def validate_code(code, module_name, index, log_file):
    """验证代码并记录错误"""
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
        
        if result['compiled'] and result['elaborated']:
            return True
        else:
            # 记录验证失败的详细信息
            error_stage = "compilation" if not result['compiled'] else "elaboration"
            error_info = f"Stage: {error_stage}\n"
            if 'error_log' in result:
                error_info += f"Error Log:\n{result['error_log']}\n"
            error_info += f"\nCode:\n{code}\n"
            log_error(log_file, index, module_name, error_info)
            return False
            
    except Exception as e:
        error_info = f"Exception: {str(e)}\nCode:\n{code}\n"
        log_error(log_file, index, module_name, error_info)
        return False

def worker_task(args):
    """多进程工作函数"""
    index, seed, log_file = args  # 解包增加 log_file
    # 每个进程需要独立的随机种子
    random.seed(seed)
    
    try:
        r = random.random()
        # 更新课程分布: Level 1 (45%) | Level 2 (30%) | Level 2.5 util (10%) | Level 3 (15%)
        # Level 2.5 专门训练 chisel3.util 相关的 API (PopCount, Reverse, Fill, Log2, etc.)
        if r < 0.45:
            sample = generate_level1(index)
        elif r < 0.75:
            sample = generate_level2(index)
        elif r < 0.85:
            sample = generate_level2_util(index)  # chisel3.util 专项训练
        else:
            sample = generate_level3(index)
            
        if validate_code(sample["entry"]["output"], sample["module_name"], index, log_file):
            return sample["entry"]
        return None
    except Exception as e:
        # 捕获并记录生成阶段的异常
        log_error(log_file, index, "UNKNOWN", f"Generation Exception: {str(e)}")
        return None

def main():
    # 初始化错误日志
    init_error_log()
    print(f"📝 错误日志文件: {ERROR_LOG_FILE}")
    
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
    
    print(f"🚀 启动 Chisel 合成数据引擎 V3 (Target: {TARGET_COUNT})", flush=True)
    print(f"⚡ 启用多进程加速: {num_processes} workers", flush=True)
    print("📊 课程分布: Level 1 (45%) | Level 2 (30%) | Level 2.5 util (10%) | Level 3 (15%)", flush=True)
    print("✨ V3 新特性: chisel3.util 专项训练 | Cat/Enum/PopCount | FSM 状态机 | 错误日志", flush=True)
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
    tasks = [(i, random.randint(0, 1000000000), ERROR_LOG_FILE) for i in range(total_tasks)]
    
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
    
    # 使用带版本号的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"chisel_sft_dataset_v2_{timestamp}.jsonl")
    
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in valid_dataset:
            f.write(json.dumps(entry) + "\n")
            
    print(f"✅ 数据集生成完毕: {output_file}")
    print(f"📦 总有效样本数: {len(valid_dataset)}")
    print(f"📊 总尝试次数: {attempts}")
    print(f"🎯 通过率: {len(valid_dataset)/attempts:.2%}" if attempts > 0 else "N/A")
    print(f"📝 错误日志: {ERROR_LOG_FILE}")

if __name__ == "__main__":
    main()
