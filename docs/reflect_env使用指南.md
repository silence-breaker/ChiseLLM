# reflect_env.py 使用指南 (v2.1)

## 简介

`reflect_env.py` 是 ChiseLLM 项目的核心模块,提供了自动化测试 Chisel 代码的完整功能。v2.1 版本在 v2.0 基础上增加了自定义输出文件名的功能。

## 核心概念

**"反射"(Reflection)** 的含义:
- 你给它一段 Chisel 代码(字符串或文件)
- 它返回这段代码的"质量报告"(字典)
- 就像镜子反射光一样,它"反射"代码的质量状态

**关键特性** (v2.1):
- ✅ 支持自定义模块名称
- ✅ 支持自定义 testbench 文件
- ✅ 支持自定义 Verilog 输出文件名 ⭐新增
- ✅ 支持自定义结果 JSON 文件名 ⭐新增
- ✅ 自动保存 Verilog 和测试报告
- ✅ 命令行工具 `run_reflect.py`
- ✅ 全自动化,无需手动操作
- ✅ 完整的错误反馈

## 快速开始

### 命令行方式 (推荐)

最简单的使用方式是通过命令行工具:

```bash
# 1. 仅编译和阐述(生成 Verilog)
python src/run_reflect.py --file my_module.scala

# 2. 完整测试(包含仿真)
python src/run_reflect.py --file my_module.scala --testbench tb_my_module.cpp

# 3. 指定输出目录
python src/run_reflect.py --file my_module.scala --testbench tb.cpp --output tests

# 4. 自定义输出文件名 ⭐新增
python src/run_reflect.py --file my_module.scala --verilog my_design.v --result my_test.json
```

**示例输出**:
```
ℹ 自动检测到模块名: SimpleAdder
============================================================
ChiseLLM 反射环境测试
============================================================
源文件:   tests/test_adder.scala
模块名:   SimpleAdder
Testbench: tests/tb_simple_adder.cpp
输出目录: tests
============================================================

⏳ 编译和阐述中...
✓ 编译成功
✓ 阐述成功
✓ Verilog 已保存到: tests/related_Verilog.v
⏳ Verilator 编译中...
✓ Verilator 编译成功
⏳ C++ 编译中...
✓ C++ 编译成功
⏳ 运行仿真...
✓ 仿真测试通过
✓ 测试报告已保存到: tests/result.json

============================================================
测试结果摘要
============================================================
编译状态:   ✓ 成功
阐述状态:   ✓ 成功
仿真状态:   ✓ 通过
失败阶段:   passed
时间戳:     2025-11-16T21:39:27.188659
============================================================
✓ 所有测试通过!
```

### Python API 方式

如果需要在 Python 代码中调用:

### Python API 方式

如果需要在 Python 代码中调用:

```python
from src.reflect_env import reflect

# 读取你的 Chisel 代码
with open('my_adder.scala', 'r') as f:
    code = f.read()

# 调用 reflect 函数
result = reflect(
    chisel_code_string=code,
    module_name="MyAdder",
    testbench_path="tb_my_adder.cpp",  # 可选
    output_dir="tests",                 # 可选
    verilog_file="my_adder.v",         # 可选 ⭐新增
    result_file="my_adder_test.json"   # 可选 ⭐新增
)

# 查看结果
if result['stage'] == 'passed':
    print("✓ 测试通过!")
    print(f"Verilog: tests/my_adder.v")
    print(f"日志: tests/my_adder_test.json")
else:
    print(f"✗ 失败于: {result['stage']}")
    print(f"错误: {result['error_log']}")
```

## 命令行工具详解

## 命令行工具详解

### 基本用法

```bash
python src/run_reflect.py --file <scala_file> [选项]
```

### 命令行参数

| 参数 | 简写 | 必需 | 说明 |
|------|------|------|------|
| `--file` | `-f` | 是 | Chisel/Scala 源文件路径 |
| `--testbench` | `-t` | 否 | C++ testbench 文件路径 |
| `--output` | `-o` | 否 | 输出目录(默认: `tests/`) |
| `--module` | `-m` | 否 | 模块名称(默认自动检测) |
| `--verilog` | `-v` | 否 | Verilog 输出文件名(默认: `related_Verilog.v`) ⭐新增 |
| `--result` | `-r` | 否 | 结果 JSON 文件名(默认: `result.json`) ⭐新增 |
| `--no-save` | - | 否 | 不保存文件,仅输出到控制台 |

### 使用场景

**场景 1: 仅验证代码能否编译和阐述**

```bash
python src/run_reflect.py --file my_design.scala
```

这会:
- ✅ 编译 Scala 代码
- ✅ 阐述为 Verilog
- ✅ 保存 Verilog 到 `tests/related_Verilog.v`
- ✅ 保存报告到 `tests/result.json`
- ⏭ 跳过仿真

**场景 2: 完整测试(包含仿真)**

```bash
python src/run_reflect.py --file my_design.scala --testbench my_tb.cpp
```

这会执行完整的测试流程:
1. 编译
2. 阐述
3. Verilator 编译
4. C++ 编译
5. 运行仿真
6. 保存所有结果

**场景 3: 指定输出目录**

```bash
python src/run_reflect.py --file my_design.scala --output my_tests
```

结果会保存到 `my_tests/` 目录。

**场景 4: 手动指定模块名**

```bash
python src/run_reflect.py --file my_design.scala --module MyCustomModule
```

当自动检测失败时使用。

**场景 5: 自定义输出文件名** ⭐新增

```bash
python src/run_reflect.py --file my_design.scala \
    --testbench my_tb.cpp \
    --verilog my_custom_design.v \
    --result my_test_result.json
```

这会:
- ✅ 将 Verilog 保存为 `tests/my_custom_design.v`
- ✅ 将测试报告保存为 `tests/my_test_result.json`

**场景 6: 批量测试不同设计**

```bash
# 为每个设计使用独立的输出文件
python src/run_reflect.py --file adder.scala --verilog adder.v --result adder_result.json
python src/run_reflect.py --file counter.scala --verilog counter.v --result counter_result.json
python src/run_reflect.py --file alu.scala --verilog alu.v --result alu_result.json
```

## Python API 详解

## Python API 详解

### reflect() 函数签名

```python
def reflect(
    chisel_code_string: str, 
    module_name: str,
    testbench_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    verilog_file: Optional[str] = None,
    result_file: Optional[str] = None
) -> dict
```

**参数**:

- `chisel_code_string` (str): Chisel/Scala 代码字符串
- `module_name` (str): 模块名称(必须与代码中的 class 名称一致)
- `testbench_path` (str, 可选): C++ testbench 文件路径。如果为 None,仅进行编译和阐述
- `output_dir` (str, 可选): 输出目录路径。如果为 None,不保存文件
- `verilog_file` (str, 可选): Verilog 输出文件名(默认: "related_Verilog.v") ⭐新增
- `result_file` (str, 可选): 结果 JSON 文件名(默认: "result.json") ⭐新增

**返回值** (dict):

| 字段 | 类型 | 说明 |
|------|------|------|
| `compiled` | bool | Scala 编译是否成功 |
| `elaborated` | bool | Chisel 阐述是否成功 |
| `sim_passed` | bool/None | 仿真是否通过(None 表示未测试) |
| `error_log` | str \| None | 错误日志(如果有) |
| `generated_verilog` | str \| None | 生成的 Verilog 代码 |
| `full_stdout` | str \| None | 完整的标准输出 |
| `full_stderr` | str \| None | 完整的标准错误输出 |
| `stage` | str | 当前阶段("compilation", "elaboration", "simulation", "passed", "exception") |
| `timestamp` | str | 测试时间戳(ISO 格式) |
| `module_name` | str | 模块名称 |

## 工作流程

```
你的代码字符串
    ↓
创建临时目录
    ↓
生成 build.sbt (配置 Chisel 6.0 + 编译器插件)
    ↓
生成 Scala 源文件 (你的代码 + Harness)
    ↓
执行 sbt run
    ├─ Scala 编译 (scalac)
    └─ Chisel 阐述 (生成 Verilog)
    ↓
Verilator 编译 (Verilog → C++)
    ↓
编译 C++ (make)
    ↓
运行可执行文件 (testbench)
    ↓
分析输出 (查找 "TEST PASSED")
    ↓
返回测试报告
    ↓
删除临时目录
```

## 详细使用示例

### 示例1: 成功的代码

```python
from src.reflect_env import reflect

code = """import chisel3._
class TestModule extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(4.W))
    val b = Input(UInt(4.W))
    val c = Output(UInt(4.W))
  })
  io.c := io.a + io.b
}"""

result = reflect(code)

# 输出:
# {
#   "compiled": True,
#   "elaborated": True,
#   "sim_passed": True,
#   "error_log": None,
#   "generated_verilog": "module TestModule(...",
#   ...
# }

if result['sim_passed']:
    print("✅ 测试通过!")
    print("生成的 Verilog:")
    print(result['generated_verilog'])
```

### 示例2: 编译错误

```python
code = """import chisel3._
class TestModule extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(4.W))
    val b = Input(UInt(4.W))
    val c = Output(UInt(4.W))
  })
  io.c := io.a + io.b +  // 语法错误: 缺少右操作数
}"""

result = reflect(code)

# 输出:
# {
#   "compiled": False,
#   "elaborated": False,
#   "sim_passed": False,
#   "error_log": "Compilation Error:\n[error] /tmp/.../TestModule.scala:...",
#   ...
# }

if not result['compiled']:
    print("❌ 编译失败!")
    print("错误信息:")
    print(result['error_log'])
```

### 示例3: 逻辑错误

```python
code = """import chisel3._
class TestModule extends Module {
  val io = IO(new Bundle {
    val a = Input(UInt(4.W))
    val b = Input(UInt(4.W))
    val c = Output(UInt(4.W))
  })
  val wrong = Wire(UInt(3.W))  // 只有3位
  wrong := io.a + io.b         // 但加法结果可能需要5位
  io.c := wrong                // 结果被截断
}"""

result = reflect(code)

# 输出:
# {
#   "compiled": True,
#   "elaborated": True,
#   "sim_passed": False,
#   "error_log": "Simulation Test Failed:\nTEST FAILED: 0 + 8 => 0 (expected 8)\n...",
#   ...
# }

if result['compiled'] and result['elaborated'] and not result['sim_passed']:
    print("❌ 逻辑错误!")
    print("代码编译和阐述成功,但仿真失败")
    print(result['error_log'])
```

## 使用场景

### 场景1: 单次测试

```python
from src.reflect_env import reflect

code = load_chisel_code_from_somewhere()
result = reflect(code)

if result['sim_passed']:
    save_verilog(result['generated_verilog'])
else:
    log_error(result['error_log'])
```

### 场景2: 批量测试

```python
from src.reflect_env import reflect

codes = [code1, code2, code3, ...]
results = []

for i, code in enumerate(codes):
    print(f"测试 {i+1}/{len(codes)}...")
    result = reflect(code)
    results.append(result)

# 统计
pass_count = sum(r['sim_passed'] for r in results)
print(f"通过率: {pass_count}/{len(codes)} = {pass_count/len(codes)*100:.1f}%")
```

### 场景3: LLM 反馈循环

```python
from src.reflect_env import reflect

def llm_generate(prompt):
    """LLM 生成代码"""
    # 这里调用你的 LLM
    return generated_code

def llm_fix(code, error):
    """LLM 修复代码"""
    prompt = f"""
    这段代码有错误:
    {code}
    
    错误信息:
    {error}
    
    请修复这段代码。
    """
    return llm_generate(prompt)

# 首次生成
code = llm_generate("写一个4位加法器")
result = reflect(code)

# 迭代修复
max_attempts = 5
for attempt in range(max_attempts):
    if result['sim_passed']:
        print(f"✅ 第 {attempt+1} 次尝试成功!")
        break
    
    print(f"❌ 第 {attempt+1} 次尝试失败,尝试修复...")
    code = llm_fix(code, result['error_log'])
    result = reflect(code)
else:
    print(f"❌ 经过 {max_attempts} 次尝试仍然失败")
```

### 场景4: 教学演示

```python
from src.reflect_env import reflect

# 演示常见错误
examples = {
    "语法错误": """
        class TestModule extends Module {
          val io = IO(new Bundle {
            val a = Input(UInt(4.W))
          })
          io.c := io.a +  // 缺少操作数
        }
    """,
    "类型错误": """
        class TestModule extends Module {
          val io = IO(new Bundle {
            val a = Input(UInt(4.W))
            val c = Output(Bool())
          })
          io.c := io.a  // 类型不匹配
        }
    """,
}

for name, code in examples.items():
    print(f"\n=== {name} ===")
    result = reflect(code)
    print(f"编译: {result['compiled']}")
    print(f"错误: {result['error_log'][:200]}...")
```

## 错误处理

### 错误类型判断

```python
result = reflect(code)

if not result['compiled']:
    print("这是一个 Scala 编译错误")
    # 通常是语法错误、类型错误、缺少 import 等
    
elif not result['elaborated']:
    print("这是一个 Chisel 阐述错误")
    # 通常是 Chisel 运行时错误、位宽问题等
    
elif not result['sim_passed']:
    print("这是一个功能逻辑错误")
    # 代码能编译和阐述,但功能不正确
    
else:
    print("代码完全正确!")
```

### 获取详细错误信息

```python
result = reflect(code)

if result['error_log']:
    # 简短错误摘要
    print("错误摘要:", result['error_log'][:200])
    
    # 完整的编译输出
    if result['full_stdout']:
        print("完整输出:", result['full_stdout'])
    
    # 完整的错误输出
    if result['full_stderr']:
        print("错误输出:", result['full_stderr'])
```

## 限制和注意事项

### 当前限制

1. **模块名必须是 TestModule**
   ```scala
   // ✅ 正确
   class TestModule extends Module { ... }
   
   // ❌ 错误
   class MyAdder extends Module { ... }
   ```

2. **接口固定为 4 位加法器**
   ```scala
   // ✅ 正确
   val io = IO(new Bundle {
     val a = Input(UInt(4.W))
     val b = Input(UInt(4.W))
     val c = Output(UInt(4.W))
   })
   
   // ❌ 不支持其他接口
   ```

3. **一次只能测试一个模块**
   - 不支持并发测试
   - 每次调用 `reflect()` 都是独立的

### 性能考虑

- **首次运行**: 约 10 秒(需要下载依赖)
- **后续运行**: 约 4-5 秒
- **建议**: 对于大量测试,考虑批处理和缓存

### 环境要求

- 必须在配置好的 conda 环境中运行
- 需要系统安装: Java, sbt, Verilator, g++
- 确保有足够的磁盘空间用于临时文件

## 高级用法

### 提取生成的 Verilog

```python
result = reflect(code)

if result['sim_passed']:
    verilog = result['generated_verilog']
    
    # 保存到文件
    with open('output.v', 'w') as f:
        f.write(verilog)
    
    # 或进行进一步处理
    lines = verilog.split('\n')
    print(f"生成的 Verilog 有 {len(lines)} 行")
```

### 自定义超时

当前实现中编译超时设置为 180 秒,如需修改可以编辑 `reflect_env.py`:

```python
# 在 run_compile_and_elaborate 函数中
process = subprocess.run(
    ["sbt", "run"],
    ...
    timeout=180  # 修改这里
)
```

### 调试模式

查看完整的编译过程:

```python
result = reflect(code)

print("=== STDOUT ===")
print(result['full_stdout'])

print("\n=== STDERR ===")
print(result['full_stderr'])
```

## 常见问题 (FAQ)

**Q: 为什么第一次运行很慢?**  
A: sbt 需要下载 Scala 和 Chisel 依赖,首次运行约需 10 秒。后续运行会快很多。

**Q: 可以测试其他类型的模块吗?**  
A: 可以!v2.0+ 版本支持任意 Chisel 模块,只需提供相应的 testbench。

**Q: 如何知道我的代码哪里错了?**  
A: 查看 `result['error_log']`,它包含详细的错误信息和行号。

**Q: 临时文件会被清理吗?**  
A: 是的,`reflect()` 使用 `tempfile.TemporaryDirectory()`,函数返回后会自动删除所有临时文件。

**Q: 可以并发调用 reflect() 吗?**  
A: 可以,每次调用使用独立的临时目录,互不干扰。但注意系统资源限制。

**Q: 支持哪些 Chisel 版本?**  
A: 当前使用 Chisel 6.0.0。理论上支持 Chisel 3.x/5.x/6.x,但未经充分测试。

## 总结

`reflect_env.py` 提供了一个强大而简单的接口来测试 Chisel 代码:

✅ **简单**: 只需传入代码字符串  
✅ **自动**: 全流程自动化,无需手动操作  
✅ **详细**: 提供完整的错误信息和生成代码  
✅ **可靠**: 自动清理,不留垃圾文件

它是 ChiseLLM 项目的基石,为后续的 LLM 训练和自我修复提供了关键的反馈机制。

## 参考资料

- [Chisel 官方文档](https://www.chisel-lang.org/)
- [Verilator 文档](https://verilator.org/)
- [第一阶段完成总结](./第一阶段完成总结.md)
- [AI-Chisel 科研指南](./AIChisel-Verilog科研指南.md)

## v2.1 更新日志 (2025-11-16)

### 新功能
- ✨ 支持自定义 Verilog 输出文件名 (`--verilog` 参数)
- ✨ 支持自定义结果 JSON 文件名 (`--result` 参数)
- 💡 更灵活的文件管理,方便批量测试

### 改进
- 📝 优化了命令行输出,显示自定义文件名信息
- 🔧 完善了 API 文档

---

**文档版本**: 2.1  
**更新日期**: 2025年11月16日
