#!/usr/bin/env python3
"""测试仿真流程"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reflect_env import reflect
import tempfile

chisel_code = '''
import chisel3._

class SimpleCounter(w: Int = 8) extends Module {
  val io = IO(new Bundle {
    val count = Output(UInt(w.W))
  })
  val counter = RegInit(0.U(w.W))
  counter := counter + 1.U
  io.count := counter
}
'''

testbench = '''
#include <verilated.h>
#include <verilated_vcd_c.h>
#include "VSimpleCounter.h"
#include <iostream>

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(true);
    
    VSimpleCounter* top = new VSimpleCounter;
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open("waveform.vcd");
    
    top->clock = 0;
    top->reset = 1;
    top->eval();
    tfp->dump(0);
    
    top->clock = 1;
    top->eval();
    tfp->dump(1);
    
    top->reset = 0;
    
    for (int i = 0; i < 20; i++) {
        top->clock = 0;
        top->eval();
        tfp->dump(i*2 + 2);
        
        top->clock = 1;
        top->eval();
        tfp->dump(i*2 + 3);
    }
    
    tfp->close();
    delete tfp;
    delete top;
    
    std::cout << "TEST PASSED" << std::endl;
    return 0;
}
'''

def main():
    # 创建临时 testbench 文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
        f.write(testbench)
        tb_path = f.name
    
    print(f'Testbench path: {tb_path}')
    
    # 运行反射
    result = reflect(
        chisel_code_string=chisel_code,
        module_name='SimpleCounter',
        testbench_path=tb_path,
        silent=False
    )
    
    # 清理
    os.unlink(tb_path)
    
    print()
    print('=' * 50)
    print(f'Stage: {result["stage"]}')
    print(f'Elaborated: {result["elaborated"]}')
    print(f'Sim passed: {result["sim_passed"]}')
    print(f'VCD content available: {bool(result.get("vcd_content"))}')
    if result.get('vcd_content'):
        print(f'VCD length: {len(result["vcd_content"])} bytes')
        print('VCD preview:')
        print(result["vcd_content"][:500])
    if result.get('error_log'):
        print(f'Error: {result["error_log"][:500]}')

if __name__ == '__main__':
    main()
