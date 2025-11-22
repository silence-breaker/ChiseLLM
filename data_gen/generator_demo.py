import random
import json
import os
import sys
from jinja2 import Template
from tqdm import tqdm  # 进度条库，建议 pip install tqdm

# ==========================================
# 0. 环境配置与导入
# ==========================================

# 动态将上一级目录的 src 加入路径，以便导入 reflect_env
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

# Level 1: 基础类型定义
# 注意：我们使用 Chisel 6.0 语法
TEMPLATE_VAR_DEF = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val out = Output({{ type_class }}({{ width }}.W))
  })
  // Task: Define a {{ type_class }} {{ kind }} named '{{ var_name }}'
  val {{ var_name }} = {{ kind }}({{ type_class }}({{ width }}.W))
  
  {% if kind == "Reg" %}
  // Reg 必须初始化或被赋值
  {{ var_name }} := 0.U
  {% elif kind == "Wire" %}
  // Wire 必须被驱动
  {{ var_name }} := 0.U
  {% endif %}

  io.out := {{ var_name }}
}
"""

# Level 2: 简单算术逻辑
TEMPLATE_ARITHMETIC = """
import chisel3._

class {{ module_name }} extends Module {
  val io = IO(new Bundle {
    val {{ in_a }} = Input(UInt({{ width }}.W))
    val {{ in_b }} = Input(UInt({{ width }}.W))
    val {{ out_res }} = Output(UInt({{ width }}.W))
  })
  
  // Logic: {{ op_name }}
  io.{{ out_res }} := io.{{ in_a }} {{ op_symbol }} io.{{ in_b }}
}
"""

# ==========================================
# 2. 生成逻辑 (Generation Logic)
# ==========================================

def generate_level1_sample(index):
    """生成 Level 1 (语法基础) 样本"""
    kinds = ["Wire", "Reg"]
    types = ["UInt", "SInt"]
    width = random.randint(2, 64)
    var_name = f"var_{random.randint(100, 999)}"
    module_name = f"TestModule_L1_{index}"
    
    selected_kind = random.choice(kinds)
    selected_type = random.choice(types)

    # 1. 渲染代码
    t = Template(TEMPLATE_VAR_DEF)
    code = t.render(
        module_name=module_name,
        type_class=selected_type,
        width=width,
        kind=selected_kind,
        var_name=var_name
    )

    # 2. 构建 Prompt
    instruction = f"Write a Chisel module named '{module_name}' that defines a {width}-bit {selected_type} {selected_kind} named '{var_name}'."

    return {
        "module_name": module_name, # 用于 reflect 验证
        "entry": {
            "instruction": instruction,
            "input": "",
            "output": code
        }
    }

def generate_level2_sample(index):
    """生成 Level 2 (简单逻辑) 样本"""
    ops = [
        ("+", "addition"),
        ("-", "subtraction"),
        ("&", "bitwise AND"),
        ("|", "bitwise OR"),
        ("^", "bitwise XOR")
    ]
    op_symbol, op_name = random.choice(ops)
    width = random.randint(4, 32)
    
    in_a = "in_a"
    in_b = "in_b"
    out_res = "result"
    module_name = f"TestModule_L2_{index}"

    # 1. 渲染代码
    t = Template(TEMPLATE_ARITHMETIC)
    code = t.render(
        module_name=module_name,
        width=width,
        in_a=in_a,
        in_b=in_b,
        out_res=out_res,
        op_symbol=op_symbol,
        op_name=op_name
    )

    # 2. 构建 Prompt
    instruction = f"Implement a Chisel module '{module_name}' that performs {op_name} on two {width}-bit inputs."

    return {
        "module_name": module_name,
        "entry": {
            "instruction": instruction,
            "input": "",
            "output": code
        }
    }

# ==========================================
# 3. 验证与主程序
# ==========================================

def validate_code(code, module_name):
    """
    使用 reflect_env 进行验证
    关键点：
    1. testbench_path=None -> 跳过仿真
    2. output_dir=None -> 不保存任何文件到磁盘
    """
    try:
        result = reflect(
            chisel_code_string=code,
            module_name=module_name,
            testbench_path=None,
            output_dir=None, # 内存中验证，无痕模式
            verilog_file=None,
            result_file=None
        )
        # 只要编译和阐述通过，stage 就会是 'passed' (因为没有 testbench)
        # 或者我们显式检查 result['compiled'] 和 result['elaborated']
        return result['compiled'] and result['elaborated']
        
    except Exception as e:
        print(f"\n⚠️ 验证过程发生异常: {e}")
        return False

def main():
    # 目标：生成 100 条通过验证的样本 (实际请改为 5000+)
    TARGET_VALID_SAMPLES = 100 
    valid_dataset = []
    
    print(f"🚀 开始生成数据，目标: {TARGET_VALID_SAMPLES} 条有效样本...")
    print("⏳ 验证过程可能较慢（每条需调用 sbt），请耐心等待...")

    pbar = tqdm(total=TARGET_VALID_SAMPLES)
    
    idx = 0
    attempts = 0
    
    while len(valid_dataset) < TARGET_VALID_SAMPLES:
        attempts += 1
        
        # 50% 概率生成 Level 1，50% 概率生成 Level 2
        if random.random() < 0.5:
            sample_data = generate_level1_sample(idx)
        else:
            sample_data = generate_level2_sample(idx)
            
        code = sample_data["entry"]["output"]
        mod_name = sample_data["module_name"]
        
        # === 核心步骤：调用 reflect_env 清洗数据 ===
        if validate_code(code, mod_name):
            valid_dataset.append(sample_data["entry"])
            pbar.update(1)
            idx += 1
        else:
            # 如果验证失败，可以打印出来看看为什么（调试用）
            # print(f"\n❌ Sample {idx} failed validation.")
            pass

    pbar.close()
    
    # 保存结果
    output_dir = os.path.join(parent_dir, "dataset")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "chisel_sft_dataset.jsonl")
    
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in valid_dataset:
            f.write(json.dumps(entry) + "\n")
            
    print(f"\n✅ 成功！已生成 {len(valid_dataset)} 条有效数据。")
    print(f"📊 尝试总次数: {attempts} (通过率: {len(valid_dataset)/attempts:.1%})")
    print(f"💾 数据集已保存至: {output_file}")

if __name__ == "__main__":
    main()