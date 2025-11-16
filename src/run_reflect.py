#!/usr/bin/env python3
"""
ChiseLLM 反射环境命令行工具

使用方式:
    python run_reflect.py --file <scala_file> [--testbench <cpp_file>] [--output <dir>]

示例:
    # 仅编译和阐述(不运行仿真)
    python run_reflect.py --file my_adder.scala
    
    # 完整测试(包含仿真)
    python run_reflect.py --file my_adder.scala --testbench tb_adder.cpp
    
    # 指定输出目录
    python run_reflect.py --file my_adder.scala --testbench tb_adder.cpp --output tests
    
    # 手动指定模块名
    python run_reflect.py --file my_adder.scala --module MyAdder

作者: ChiseLLM Project
日期: 2025-11-16
"""

import argparse
import sys
import os
from pathlib import Path

# 将 src 目录添加到 Python 路径
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from reflect_env import reflect, extract_module_name_from_file


def main():
    parser = argparse.ArgumentParser(
        description='ChiseLLM 反射环境 - 自动化测试 Chisel 代码',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --file my_adder.scala
  %(prog)s --file my_adder.scala --testbench tb_adder.cpp
  %(prog)s --file my_adder.scala --testbench tb_adder.cpp --output tests
  %(prog)s --file my_adder.scala --module MyAdder
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        required=True,
        type=str,
        help='Chisel/Scala 源文件路径 (必需)'
    )
    
    parser.add_argument(
        '--testbench', '-t',
        type=str,
        default=None,
        help='C++ testbench 文件路径 (可选,如果不提供则仅进行编译和阐述)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='tests',
        help='输出目录路径 (默认: tests/)'
    )
    
    parser.add_argument(
        '--module', '-m',
        type=str,
        default=None,
        help='模块名称 (可选,如果不提供则自动从代码中提取)'
    )
    
    parser.add_argument(
        '--verilog', '-v',
        type=str,
        default=None,
        help='Verilog 输出文件名 (默认: related_Verilog.v)'
    )
    
    parser.add_argument(
        '--result', '-r',
        type=str,
        default=None,
        help='结果 JSON 文件名 (默认: result.json)'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='不保存结果文件 (仅输出到控制台)'
    )
    
    args = parser.parse_args()
    
    # 验证输入文件
    if not os.path.exists(args.file):
        print(f"❌ 错误: 找不到文件 '{args.file}'")
        sys.exit(1)
    
    # 验证 testbench 文件(如果提供)
    if args.testbench and not os.path.exists(args.testbench):
        print(f"❌ 错误: 找不到 testbench 文件 '{args.testbench}'")
        sys.exit(1)
    
    # 读取代码文件
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            code = f.read()
    except Exception as e:
        print(f"❌ 错误: 无法读取文件 '{args.file}': {e}")
        sys.exit(1)
    
    # 确定模块名称
    if args.module:
        module_name = args.module
        print(f"ℹ 使用指定的模块名: {module_name}")
    else:
        module_name = extract_module_name_from_file(args.file)
        if not module_name:
            print(f"❌ 错误: 无法从文件中提取模块名称")
            print("   请使用 --module 参数手动指定模块名称")
            sys.exit(1)
        print(f"ℹ 自动检测到模块名: {module_name}")
    
    # 确定输出目录
    output_dir = None if args.no_save else args.output
    
    # 打印测试信息
    print("=" * 60)
    print("ChiseLLM 反射环境测试")
    print("=" * 60)
    print(f"源文件:     {args.file}")
    print(f"模块名:     {module_name}")
    print(f"Testbench:  {args.testbench if args.testbench else '(未提供,仅编译和阐述)'}")
    print(f"输出目录:   {output_dir if output_dir else '(不保存)'}")
    if args.verilog:
        print(f"Verilog文件: {args.verilog}")
    if args.result:
        print(f"结果文件:   {args.result}")
    print("=" * 60)
    print()
    
    # 执行反射测试
    result = reflect(
        chisel_code_string=code,
        module_name=module_name,
        testbench_path=args.testbench,
        output_dir=output_dir,
        verilog_file=args.verilog,
        result_file=args.result
    )
    
    # 打印结果摘要
    print()
    print("=" * 60)
    print("测试结果摘要")
    print("=" * 60)
    print(f"编译状态:   {'✓ 成功' if result['compiled'] else '✗ 失败'}")
    print(f"阐述状态:   {'✓ 成功' if result['elaborated'] else '✗ 失败'}")
    
    if result['sim_passed'] is not None:
        print(f"仿真状态:   {'✓ 通过' if result['sim_passed'] else '✗ 失败'}")
    else:
        print(f"仿真状态:   (未测试)")
    
    print(f"失败阶段:   {result['stage']}")
    print(f"时间戳:     {result['timestamp']}")
    
    # 如果有错误,打印错误摘要
    if result['error_log']:
        print()
        print("错误信息摘要:")
        print("-" * 60)
        # 只打印前 500 个字符
        error_preview = result['error_log'][:500]
        print(error_preview)
        if len(result['error_log']) > 500:
            print("...")
            print(f"(完整错误信息共 {len(result['error_log'])} 字符,已保存到 result.json)")
    
    print("=" * 60)
    
    # 根据结果设置退出码
    if result['stage'] == 'passed':
        print("✓ 所有测试通过!")
        sys.exit(0)
    else:
        print(f"✗ 测试失败于阶段: {result['stage']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
