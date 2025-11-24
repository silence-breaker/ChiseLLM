"""
ChiseLLM 反射环境 (Reflection Environment) v2.1

这个模块实现了核心的 reflect() 函数,用于自动化测试 LLM 生成的 Chisel 代码。

核心功能:
1. 接收 Chisel/Scala 代码文件或字符串
2. 自动编译 (Scala compilation)
3. 自动阐述 (Chisel elaboration to Verilog)
4. 自动仿真 (Verilator simulation with C++ testbench)
5. 返回详细的"体检报告"并保存到文件

新特性 (v2.1):
- ⚡ 使用 Mill 构建工具替代 sbt (更快、更现代)
- 支持自定义模块名称
- 支持自定义 testbench 路径
- 自动保存 Verilog 到 tests/related_Verilog.v
- 自动保存详细日志到 tests/result.json

Mill vs sbt 对比:
- Mill 编译速度更快 (特别是增量编译)
- Mill 配置更简洁 (build.sc vs build.sbt)
- Mill 是 Scala 社区推荐的现代构建工具

作者: ChiseLLM Project
日期: 2025-11-24
"""

import subprocess
import tempfile
import os
import shutil
import json
import re
from pathlib import Path
from typing import Optional
from datetime import datetime


def _log(message: str, silent: bool = False):
    """辅助函数: 条件性打印日志"""
    if not silent:
        print(message)


def reflect(
    chisel_code_string: str, 
    module_name: str,
    testbench_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    verilog_file: Optional[str] = None,
    result_file: Optional[str] = None,
    silent: bool = False  # 新增: 静默模式开关
) -> dict:
    """
    反射函数: 接收 Chisel/Scala 代码字符串, 返回包含"体检报告"的字典。
    
    Args:
        chisel_code_string (str): LLM 生成的 Chisel/Scala 代码
        module_name (str): 模块名称(必须与代码中的 class 名称一致)
        testbench_path (str, optional): C++ testbench 文件路径。如果为 None,仅进行编译和阐述
        output_dir (str, optional): 输出目录路径(用于保存 Verilog 和日志)。如果为 None,不保存
        verilog_file (str, optional): Verilog 输出文件名(默认: "related_Verilog.v")
        result_file (str, optional): 结果 JSON 文件名(默认: "result.json")
        silent (bool, optional): 是否启用静默模式(不打印进度信息)。默认 False
        
    Returns:
        dict: 体检报告,包含以下字段:
            - compiled (bool): 是否成功编译
            - elaborated (bool): 是否成功阐述为 Verilog
            - sim_passed (bool/None): 仿真测试是否通过(None 表示未测试)
            - error_log (str): 错误日志 (如果有)
            - generated_verilog (str): 生成的 Verilog 代码 (如果成功)
            - full_stdout (str): 完整的标准输出
            - full_stderr (str): 完整的标准错误输出
            - stage (str): 当前阶段 ("compilation", "elaboration", "simulation", "passed", "exception")
            - timestamp (str): 测试时间戳
            - module_name (str): 模块名称
    """
    
    # 初始化标准"体检报告"
    result = {
        "compiled": False,
        "elaborated": False,
        "sim_passed": None,  # None 表示未测试
        "error_log": None,
        "generated_verilog": None,
        "full_stdout": None,
        "full_stderr": None,
        "stage": "initialization",
        "timestamp": datetime.now().isoformat(),
        "module_name": module_name
    }
    
    # 创建临时工作目录
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # --- 步骤 1: 编译与阐述 ---
            verilog_file_path = run_compile_and_elaborate(
                temp_dir, chisel_code_string, module_name, result, silent
            )
            
            # 如果编译或阐述失败,提前返回
            if not verilog_file_path:
                # 保存结果到输出目录(如果指定)
                if output_dir:
                    result_path = _save_results(result, output_dir, result_file)
                    _log(f"✗ 失败于阶段: {result['stage']}", silent)
                    _log(f"✓ 日志已保存到: {result_path}", silent)
                return result
            
            # 如果成功阐述,保存 Verilog 文件
            if output_dir and result["elaborated"]:
                verilog_path = _save_verilog(result["generated_verilog"], output_dir, verilog_file)
                _log(f"✓ Verilog 已保存到: {verilog_path}", silent)
            
            # --- 步骤 2: 仿真 (可选) ---
            # 只有提供了 testbench 才执行仿真
            if testbench_path:
                if not os.path.exists(testbench_path):
                    result["error_log"] = f"Testbench file not found: {testbench_path}"
                    result["stage"] = "simulation"
                else:
                    run_simulation(temp_dir, verilog_file_path, module_name, 
                                 testbench_path, result, silent)
                    result["stage"] = "passed" if result["sim_passed"] else "simulation"
            else:
                # 没有 testbench,仿真阶段跳过
                result["stage"] = "passed"
                _log("ℹ 未提供 testbench,跳过仿真阶段", silent)
            
        except Exception as e:
            result["error_log"] = f"Python Exception: {str(e)}"
            result["stage"] = "exception"
        
        finally:
            # 读取日志文件 (如果存在)
            _read_logs(temp_dir, result)
            
            # 保存结果到输出目录(如果指定)
            if output_dir:
                result_path = _save_results(result, output_dir, result_file)
                _log(f"✓ 测试报告已保存到: {result_path}", silent)
    
    return result


def run_compile_and_elaborate(
    temp_dir: str, 
    code_str: str, 
    module_name: str,
    result_dict: dict,
    silent: bool = False
) -> Optional[str]:
    """
    步骤 1: 编译和阐述 Chisel 代码 (使用 Mill 构建工具)
    
    这个函数会:
    1. 创建一个最小的 Mill 项目结构 (build.sc)
    2. 将用户代码包装在一个 harness 中
    3. 执行 mill chiselmodule.run 来编译和阐述代码
    4. 分析结果,区分编译错误和阐述错误
    
    Args:
        temp_dir (str): 临时工作目录路径
        code_str (str): 用户的 Chisel 代码
        module_name (str): 模块名称
        result_dict (dict): 结果字典 (会被修改)
        silent (bool): 是否静默模式
        
    Returns:
        str: 成功时返回 Verilog 文件路径; 失败时返回 None
    """
    
    result_dict["stage"] = "compilation"
    
    # 1. 创建 build.sc (定义 Chisel 依赖 - Mill 构建配置)
    build_sc_content = """import mill._
import mill.scalalib._

object chiselmodule extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  def ivyDeps = Agg(
    ivy"org.chipsalliance::chisel:6.0.0"
  )
  
  def scalacOptions = Seq(
    "-Xsource:2.13",
    "-language:reflectiveCalls",
    "-deprecation",
    "-feature",
    "-Xcheckinit"
  )
  
  def scalacPluginIvyDeps = Agg(
    ivy"org.chipsalliance:::chisel-plugin:6.0.0"
  )
}
"""
    with open(os.path.join(temp_dir, "build.sc"), "w") as f:
        f.write(build_sc_content)
    
    # 2. 创建标准的 Mill 项目目录结构
    # Mill 默认使用 <module>/src/ 作为源码目录
    scala_dir = os.path.join(temp_dir, "chiselmodule", "src")
    os.makedirs(scala_dir, exist_ok=True)
    
    # 3. 创建 Scala 源文件 (用户代码 + Harness)
    # Harness 负责将 Chisel 模块转换成 Verilog
    scala_code_content = f"""import chisel3._
import circt.stage.ChiselStage
import java.io.PrintWriter
import java.io.File

// ========== LLM 生成的代码开始 ==========
{code_str}
// ========== LLM 生成的代码结束 ==========

// Harness: 自动将模块转换成 Verilog
object VerilogEmitter extends App {{
  // 创建输出目录
  new File("generated_verilog").mkdirs()
  
  // 生成 SystemVerilog
  val verilog = ChiselStage.emitSystemVerilog(
    new {module_name}(),
    firtoolOpts = Array("-disable-all-randomization", "-strip-debug-info")
  )
  
  // 写入文件
  val writer = new PrintWriter(new File("generated_verilog/{module_name}.v"))
  writer.write(verilog)
  writer.close()
}}
"""
    
    scala_file_path = os.path.join(scala_dir, f"{module_name}.scala")
    with open(scala_file_path, "w") as f:
        f.write(scala_code_content)
    
    # 4. 执行 mill run (编译 + 阐述)
    stdout_log = os.path.join(temp_dir, 'mill_stdout.log')
    stderr_log = os.path.join(temp_dir, 'mill_stderr.log')
    
    # 设置环境变量,配置 Mill 缓存
    # Mill 的缓存机制更简洁，默认使用 ~/.cache/mill 和项目目录下的 out/
    # 优化: 使用用户主目录下的缓存，避免重复下载依赖
    user_home = os.path.expanduser("~")
    mill_cache_dir = os.path.join(user_home, ".cache", "mill")
    os.makedirs(mill_cache_dir, exist_ok=True)
    
    env = os.environ.copy()
    # Mill 使用 COURSIER_CACHE 来配置依赖缓存位置
    env['COURSIER_CACHE'] = mill_cache_dir
    env['MILL_WORKSPACE_DIR'] = temp_dir
    # 避免交互式提示
    env['CI'] = 'true'
    
    _log("⏳ 编译和阐述中 (使用 Mill)...", silent)
    
    with open(stdout_log, 'w') as f_out, open(stderr_log, 'w') as f_err:
        try:
            process = subprocess.run(
                ["mill", "chiselmodule.run"],
                cwd=temp_dir,
                stdout=f_out,
                stderr=f_err,
                env=env,
                timeout=120  # 120秒超时(Mill 比 sbt 更快，第一次运行需要下载依赖)
            )
        except subprocess.TimeoutExpired:
            result_dict["error_log"] = "Compilation timeout (exceeded 120 seconds)"
            return None
    
    # 5. 分析结果
    if process.returncode != 0:
        # 失败: 需要区分编译错误和阐述错误
        with open(stderr_log, 'r') as f:
            stderr_content = f.read()
        
        # 检查是否是 Scala 编译错误
        if "[error]" in stderr_content and ".scala:" in stderr_content:
            result_dict["compiled"] = False
            result_dict["stage"] = "compilation"
            result_dict["error_log"] = f"Compilation Error:\n{stderr_content}"
            _log("✗ 编译失败", silent)
        else:
            # 编译通过,但 Chisel 阐述失败
            result_dict["compiled"] = True
            result_dict["elaborated"] = False
            result_dict["stage"] = "elaboration"
            result_dict["error_log"] = f"Elaboration Error:\n{stderr_content}"
            _log("✓ 编译成功", silent)
            _log("✗ 阐述失败", silent)
        
        return None
    
    # 6. 成功!
    result_dict["compiled"] = True
    result_dict["elaborated"] = True
    result_dict["stage"] = "elaboration"
    
    _log("✓ 编译成功", silent)
    _log("✓ 阐述成功", silent)
    
    # 读取生成的 Verilog 文件
    verilog_file = os.path.join(temp_dir, "generated_verilog", f"{module_name}.v")
    
    try:
        with open(verilog_file, 'r') as f:
            result_dict["generated_verilog"] = f.read()
    except IOError as e:
        result_dict["error_log"] = f"Failed to read generated Verilog: {e}"
        return None
    
    return verilog_file


def run_simulation(
    temp_dir: str, 
    verilog_file_path: str, 
    module_name: str,
    testbench_path: str,
    result_dict: dict,
    silent: bool = False
) -> None:
    """
    步骤 2: 使用 Verilator 编译和运行 C++ testbench
    
    这个函数会:
    1. 复制用户提供的 C++ testbench
    2. 使用 Verilator 将 Verilog 转换为 C++
    3. 编译生成的 C++ 代码
    4. 运行可执行文件并检查测试结果
    
    Args:
        temp_dir (str): 临时工作目录路径
        verilog_file_path (str): Verilog 文件路径
        module_name (str): 模块名称
        testbench_path (str): C++ testbench 文件路径
        result_dict (dict): 结果字典 (会被修改)
    """
    
    result_dict["stage"] = "simulation"
    
    # 1. 复制 testbench 文件
    tb_filename = os.path.basename(testbench_path)
    tb_dest_path = os.path.join(temp_dir, tb_filename)
    shutil.copy(testbench_path, tb_dest_path)
    
    _log("⏳ Verilator 编译中...", silent)
    
    # 2. 运行 Verilator (Verilog -> C++)
    verilator_cmd = [
        "verilator",
        "-cc",                  # 生成 C++ 代码
        "-Wno-UNUSED",          # 忽略未使用信号的警告
        "-Wno-lint",            # 忽略 lint 警告
        "--exe",                # 创建可执行文件
        tb_dest_path,           # C++ testbench
        verilog_file_path       # Verilog 文件
    ]
    
    process = subprocess.run(
        verilator_cmd,
        cwd=temp_dir,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if process.returncode != 0:
        result_dict["error_log"] = f"Verilator Error:\n{process.stderr}"
        _log("✗ Verilator 编译失败", silent)
        return
    
    _log("✓ Verilator 编译成功", silent)
    _log("⏳ C++ 编译中...", silent)
    
    # 3. 编译 C++ (使用 make)
    obj_dir = os.path.join(temp_dir, "obj_dir")
    make_cmd = [
        "make",
        "-C", obj_dir,
        "-f", f"V{module_name}.mk",
        f"V{module_name}"
    ]
    
    process = subprocess.run(
        make_cmd,
        cwd=temp_dir,
        capture_output=True,
        text=True,
        timeout=60
    )
    
    if process.returncode != 0:
        result_dict["error_log"] = f"Make Error:\n{process.stderr}"
        _log("✗ C++ 编译失败", silent)
        return
    
    _log("✓ C++ 编译成功", silent)
    _log("⏳ 运行仿真...", silent)
    
    # 4. 运行可执行文件
    exe_path = os.path.join(obj_dir, f"V{module_name}")
    
    process = subprocess.run(
        [exe_path],
        cwd=temp_dir,
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if process.returncode != 0:
        result_dict["error_log"] = f"Simulation Runtime Error:\n{process.stderr}"
        result_dict["sim_passed"] = False
        _log("✗ 仿真运行时错误", silent)
        return
    
    # 5. 检查 testbench 输出
    sim_output = process.stdout
    if "TEST PASSED" in sim_output or "PASS" in sim_output:
        result_dict["sim_passed"] = True
        _log("✓ 仿真测试通过", silent)
    else:
        result_dict["sim_passed"] = False
        result_dict["error_log"] = f"Simulation Test Failed:\n{sim_output}"
        _log("✗ 仿真测试失败", silent)


def _read_logs(temp_dir: str, result_dict: dict) -> None:
    """
    辅助函数: 读取日志文件到结果字典
    
    Args:
        temp_dir (str): 临时目录路径
        result_dict (dict): 结果字典 (会被修改)
    """
    # 读取 stderr 日志
    try:
        stderr_log = os.path.join(temp_dir, 'mill_stderr.log')
        with open(stderr_log, 'r') as f:
            result_dict['full_stderr'] = f.read()
    except IOError:
        pass  # 文件不存在也没关系
    
    # 读取 stdout 日志
    try:
        stdout_log = os.path.join(temp_dir, 'mill_stdout.log')
        with open(stdout_log, 'r') as f:
            result_dict['full_stdout'] = f.read()
    except IOError:
        pass


def _save_results(result_dict: dict, output_dir: str, filename: Optional[str] = None) -> str:
    """
    辅助函数: 保存测试结果到 JSON 文件
    
    Args:
        result_dict (dict): 结果字典
        output_dir (str): 输出目录路径
        filename (str, optional): 输出文件名(默认: "result.json")
        
    Returns:
        str: 保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    if filename is None:
        filename = "result.json"
    result_file = os.path.join(output_dir, filename)
    
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)
    
    return result_file


def _save_verilog(verilog_content: str, output_dir: str, filename: Optional[str] = None) -> str:
    """
    辅助函数: 保存 Verilog 代码到文件
    
    Args:
        verilog_content (str): Verilog 代码内容
        output_dir (str): 输出目录路径
        filename (str, optional): 输出文件名(默认: "related_Verilog.v")
        
    Returns:
        str: 保存的文件路径
    """
    os.makedirs(output_dir, exist_ok=True)
    if filename is None:
        filename = "related_Verilog.v"
    verilog_file = os.path.join(output_dir, filename)
    
    with open(verilog_file, 'w', encoding='utf-8') as f:
        f.write(verilog_content)
    
    return verilog_file


def extract_module_name_from_code(code_str: str) -> Optional[str]:
    """
    辅助函数: 从 Chisel 代码中提取模块名称
    
    Args:
        code_str (str): Chisel/Scala 代码
        
    Returns:
        str: 模块名称,如果找不到返回 None
    """
    # 尝试匹配 "class ModuleName extends Module"
    match = re.search(r'class\s+(\w+)\s+extends\s+Module', code_str)
    if match:
        return match.group(1)
    return None


def extract_module_name_from_file(file_path: str) -> Optional[str]:
    """
    辅助函数: 从 Scala 文件中提取模块名称
    
    Args:
        file_path (str): Scala 文件路径
        
    Returns:
        str: 模块名称,如果找不到返回 None
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    return extract_module_name_from_code(code)
