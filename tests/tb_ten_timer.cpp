#include "verilated.h"
#include "VTenTimer.h"
#include <iostream>

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    VTenTimer* dut = new VTenTimer;
    
    bool pass = true;
    int test_count = 0;
    
    // 初始化信号
    dut->clock = 0;
    dut->reset = 1;
    dut->io_enable = 0;
    dut->io_reset_count = 0;
    dut->eval();
    
    // 释放复位
    dut->reset = 0;
    dut->eval();
    
    std::cout << "=== Test 1: 基本计数测试 (0-9) ===" << std::endl;
    dut->io_enable = 1;
    dut->io_reset_count = 0;
    
    // 初始状态应该是0
    if (dut->io_count != 0) {
        std::cout << "FAILED: Initial count should be 0, got " << (int)dut->io_count << std::endl;
        pass = false;
    }
    
    for (int i = 0; i < 20; i++) {
        // 时钟上升沿
        dut->clock = 1;
        dut->eval();
        
        // 时钟下降沿
        dut->clock = 0;
        dut->eval();
        
        // 在时钟周期后,计数器应该递增
        // 第0个周期后 -> count=1, 第1个周期后 -> count=2, ...
        int expected_count = (i + 1) % 10;
        
        if (dut->io_count != expected_count) {
            std::cout << "FAILED: Cycle " << i 
                      << " - Expected count=" << expected_count 
                      << ", Got=" << (int)dut->io_count << std::endl;
            pass = false;
        }
        
        if (i < 15 && (i % 5 == 0)) {
            std::cout << "  After cycle " << i << ": count=" << (int)dut->io_count 
                      << ", overflow=" << (int)dut->io_overflow << std::endl;
        }
        
        test_count++;
    }
    
    std::cout << "\n=== Test 2: 使能控制测试 ===" << std::endl;
    // 禁用使能,计数应该停止
    dut->io_enable = 0;
    int frozen_count = dut->io_count;
    
    for (int i = 0; i < 5; i++) {
        dut->clock = 1;
        dut->eval();
        dut->clock = 0;
        dut->eval();
        
        if (dut->io_count != frozen_count) {
            std::cout << "FAILED: Count changed while enable=0" << std::endl;
            pass = false;
        }
    }
    std::cout << "  Enable=0, count frozen at " << (int)dut->io_count << " ✓" << std::endl;
    
    std::cout << "\n=== Test 3: 计数器复位测试 ===" << std::endl;
    dut->io_enable = 1;
    dut->io_reset_count = 1;
    dut->clock = 1;
    dut->eval();
    dut->clock = 0;
    dut->eval();
    
    if (dut->io_count != 0) {
        std::cout << "FAILED: Reset didn't clear counter to 0" << std::endl;
        pass = false;
    } else {
        std::cout << "  Reset successful, count=" << (int)dut->io_count << " ✓" << std::endl;
    }
    
    dut->io_reset_count = 0;
    
    std::cout << "\n=== Test 4: 溢出信号测试 ===" << std::endl;
    // 计数到9,检查溢出信号
    // 首先确保从0开始
    dut->io_reset_count = 1;
    dut->clock = 1;
    dut->eval();
    dut->clock = 0;
    dut->eval();
    dut->io_reset_count = 0;
    
    for (int i = 0; i < 10; i++) {
        dut->clock = 1;
        dut->eval();
        dut->clock = 0;
        dut->eval();
        
        // 当计数器到达9时,在下一个时钟周期溢出信号应该为高
        if (dut->io_count == 9 && dut->io_overflow != 1) {
            std::cout << "FAILED: Overflow not set at count=9" << std::endl;
            pass = false;
        }
    }
    std::cout << "  Overflow signal works correctly ✓" << std::endl;
    
    // 测试结果
    std::cout << "\n========================================" << std::endl;
    if (pass) {
        std::cout << "TEST PASSED - All tests successful!" << std::endl;
        std::cout << "Total test cycles: " << test_count << std::endl;
    } else {
        std::cout << "TEST FAILED - Some tests failed" << std::endl;
    }
    std::cout << "========================================" << std::endl;
    
    delete dut;
    return pass ? 0 : 1;
}
