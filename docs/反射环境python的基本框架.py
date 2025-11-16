import subprocess
import tempfile
import os
import shutil
import json

# [关键设计] 我们为第一阶段固定一个“目标模块名”

# 这极大简化了 harness 和 testbench 的编写

TARGET_MODULE_NAME = "TestModule"

# [关键设计] 我们为第一阶段固定一个“Hello, World!”任务

# 我们的目标是让 LLM 编写一个4位加法器

# 这是一个预先写好的 C++ testbench 文件名

CPP_TESTBENCH_FILE = "tb_adder.cpp"

def reflect(chisel_code_string: str) -> dict:
    """
    接收 Chisel/Scala 代码字符串, 返回一个包含 "体检报告" 的字典。
    """

    # 这是我们将返回的标准“体检报告”
    result = {
        "compiled": False,
        "elaborated": False,
        "sim_passed": False,
        "error_log": None,
        "generated_verilog": None,
        "full_stdout": None,
        "full_stderr": None
    }

    # 创建一个安全的临时工作目录
    # 'with' 语句确保了无论成功还是失败，这个目录最后都会被删除
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # --- 步骤 1.1 & 1.2: 编译与阐述 ---
            # run_compile_and_elaborate 会填充 result["compiled"], 
            # result["elaborated"] 和 result["generated_verilog"]
            verilog_file_path = run_compile_and_elaborate(
                temp_dir, chisel_code_string, result
            )

            # 如果上一步失败 (例如编译不通过), 就提前退出
            if not verilog_file_path:
                return result

            # --- 步骤 1.3: 仿真 ---
            # 只有在成功生成 Verilog 后才执行
            run_simulation(
                temp_dir, verilog_file_path, result
            )

        except Exception as e:
            result["error_log"] = f"Python Error: {e}"
        
        finally:
            # 无论如何，都尝试读取日志文件
            # 这里的 'sbt_stderr.log' 等是我们在子函数中生成的
            try:
                with open(os.path.join(temp_dir, 'sbt_stderr.log'), 'r') as f:
                    result['full_stderr'] = f.read()
            except IOError:
                pass # 文件不存在也没关系
                
            try:
                with open(os.path.join(temp_dir, 'sbt_stdout.log'), 'r') as f:
                    result['full_stdout'] = f.read()
            except IOError:
                pass

    return result

def run_compile_and_elaborate(temp_dir, code_str, result_dict):
    """
    [步骤 1.1 & 1.2] 尝试编译和阐述 Chisel 代码。
    如果成功，返回生成的 Verilog 文件路径。
    如果失败，更新 result_dict 并返回 None。
    """
    # 任务 1: 创建一个最小的 sbt 项目结构
    # build.sbt (定义 Chisel 依赖)
    build_sbt_content = f"""
    scalaVersion := "2.13.12"
    libraryDependencies += "org.chipsalliance" %% "chisel" % "5.0.0"
    """
    with open(os.path.join(temp_dir, "build.sbt"), "w") as f:
        f.write(build_sbt_content)

    # 任务 2: 创建 Scala 源文件目录
    scala_dir = os.path.join(temp_dir, "src", "main", "scala")
    os.makedirs(scala_dir)

    # 任务 3: 创建 Scala 代码 (用户代码 + 我们的Harness)
    # [关键] 我们假设 LLM 写的模块叫 TARGET_MODULE_NAME (即 "TestModule")
    scala_code_content = f"""
    import chisel3._
    import chisel3.stage.ChiselStage

    // ---------- LLM 生成的代码从这里开始 ----------
    {code_str}
    // ---------- LLM 生成的代码在这里结束 ----------

    // [关键Harness] 这是一个 "main" 对象，sbt 会运行它
    // 它负责告诉 Chisel 把 "TestModule" 转换成 Verilog
    object VerilogEmitter extends App {{
      (new ChiselStage).emitVerilog(
        new {TARGET_MODULE_NAME}(), 
        Array("--target-dir", "generated_verilog")
      )
    }}
    """
    scala_file_path = os.path.join(scala_dir, f"{TARGET_MODULE_NAME}.scala")
    with open(scala_file_path, "w") as f:
        f.write(scala_code_content)

    # 任务 4: 执行 sbt run (这将自动完成编译和阐述)
    # 我们将 stdout 和 stderr 重定向到日志文件
    stdout_log = os.path.join(temp_dir, 'sbt_stdout.log')
    stderr_log = os.path.join(temp_dir, 'sbt_stderr.log')

    with open(stdout_log, 'w') as f_out, open(stderr_log, 'w') as f_err:
        process = subprocess.run(
            ["sbt", "run"],
            cwd=temp_dir,         # [关键] 在临时目录中执行
            stdout=f_out,
            stderr=f_err,
            timeout=120           # 设置120秒超时
        )

    # 任务 5: 分析结果
    # sbt 在失败时返回非零退出代码
    if process.returncode != 0:
        # 失败了，我们需要区分是“编译失败”还是“阐述失败”
        stderr_content = ""
        with open(stderr_log, 'r') as f:
            stderr_content = f.read()

        if "[error]" in stderr_content and ".scala:" in stderr_content:
            # 这是一个编译错误
            result_dict["compiled"] = False
            result_dict["error_log"] = "Compile Error: " + stderr_content
        else:
            # 编译通过了，但在 Chisel 运行时 (阐述) 失败了
            result_dict["compiled"] = True
            result_dict["elaborated"] = False
            result_dict["error_log"] = "Elaboration Error: " + stderr_content
        
        return None # 失败，返回 None

    # 任务 6: 成功！
    result_dict["compiled"] = True
    result_dict["elaborated"] = True
    
    verilog_file = os.path.join(
        temp_dir, "generated_verilog", f"{TARGET_MODULE_NAME}.v"
    )
    
    # 读取生成的 Verilog 代码存入 result
    try:
        with open(verilog_file, 'r') as f:
            result_dict["generated_verilog"] = f.read()
    except IOError as e:
        result_dict["error_log"] = f"Failed to read Verilog file: {e}"
        return None

    return verilog_file # 成功，返回 Verilog 路径

def run_simulation(temp_dir, verilog_file_path, result_dict):
    """
    [步骤 1.3] 使用 Verilator 编译和运行 C++ testbench。
    """

    # 任务 1: 将我们预先写好的 testbench 复制到临时目录
    # [关键] 你必须在 reflect_env.py 旁边创建一个 tb_adder.cpp 文件
    if not os.path.exists(CPP_TESTBENCH_FILE):
        result_dict["error_log"] = f"Testbench file not found: {CPP_TESTBENCH_FILE}"
        return

    tb_dest_path = os.path.join(temp_dir, CPP_TESTBENCH_FILE)
    shutil.copy(CPP_TESTBENCH_FILE, tb_dest_path)

    # 任务 2: 运行 Verilator (它会把 Verilog -> C++)
    verilator_cmd = [
        "verilator",
        "-cc",                          # 转换成 C++
        "-Wall",                        # 打开所有警告
        "--exe",                        # 创建一个可执行文件
        tb_dest_path,                   # 我们的 C++ testbench
        verilog_file_path               # LLM 生成的 Verilog
    ]
    
    process = subprocess.run(
        verilator_cmd, cwd=temp_dir, capture_output=True, text=True
    )
    
    if process.returncode != 0:
        result_dict["error_log"] = f"Verilator Error: {process.stderr}"
        return

    # 任务 3: 编译 C++ (使用 make)
    # Verilator 会在 obj_dir 中生成一个 Makefile
    obj_dir = os.path.join(temp_dir, "obj_dir")
    make_cmd = [
        "make",
        "-C", obj_dir,
        "-f", f"V{TARGET_MODULE_NAME}.mk"
    ]
    
    process = subprocess.run(
        make_cmd, cwd=temp_dir, capture_output=True, text=True
    )

    if process.returncode != 0:
        result_dict["error_log"] = f"Make Error: {process.stderr}"
        return

    # 任务 4: 运行可执行文件!
    exe_path = os.path.join(obj_dir, f"V{TARGET_MODULE_NAME}")
    
    process = subprocess.run(
        [exe_path], cwd=temp_dir, capture_output=True, text=True
    )

    if process.returncode != 0:
        result_dict["error_log"] = f"Simulation Runtime Error: {process.stderr}"
        return

    # 任务 5: [关键] 检查 testbench 的输出
    sim_output = process.stdout
    if "TEST PASSED" in sim_output:
        result_dict["sim_passed"] = True
    else:
        result_dict["sim_passed"] = False
        result_dict["error_log"] = f"Simulation Failed: {sim_output}"

# --- 这是一个示例，演示如何运行你的函数 ---

if __name__ == "__main__":

    # 示例 1: 正确的4位加法器
    correct_adder_code = f"""
    import chisel3._
    class {TARGET_MODULE_NAME} extends Module {{
      val io = IO(new Bundle {{
        val a = Input(UInt(4.W))
        val b = Input(UInt(4.W))
        val c = Output(UInt(4.W))
      }})
      io.c := io.a + io.b
    }}
    """
    
    print("--- 正在测试 [正确] 的加法器 ---")
    report = reflect(correct_adder_code)
    print(json.dumps(report, indent=2))
    
    
    # 示例 2: 有编译错误的代码 (语法错误)
    compile_error_code = f"""
    import chisel3._
    class {TARGET_MODULE_NAME} extends Module {{
      val io = IO(new Bundle {{
        val a = Input(UInt(4.W))
        val b = Input(UInt(4.W))
        val c = Output(UInt(4.W))
      }})
      io.c := io.a + io.b + // <-- 故意留下的语法错误
    }}
    """
    
    print("\n--- 正在测试 [编译错误] 的代码 ---")
    report = reflect(compile_error_code)
    print(json.dumps(report, indent=2))

    # 示例 3: 有逻辑错误的代码 (阐述/运行时错误)
    # (例如，位宽不匹配)
    elaboration_error_code = f"""
    import chisel3._
    class {TARGET_MODULE_NAME} extends Module {{
      val io = IO(new Bundle {{
        val a = Input(UInt(4.W))
        val b = Input(UInt(4.W))
        val c = Output(UInt(4.W))
      }})
      val wrong_wire = Wire(UInt(3.W))
      wrong_wire := io.a + io.b
      io.c := wrong_wire // <-- 4位信号连到3位wire，然后3位再连到4位
    }}
    """
    
    print("\n--- 正在测试 [阐述错误] 的代码 ---")
    report = reflect(elaboration_error_code)
    print(json.dumps(report, indent=2))
