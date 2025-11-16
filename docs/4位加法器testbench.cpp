// [关键] 你必须把这个文件命名为 tb_adder.cpp
// 并放在与 reflect_env.py 相同的目录中

#include "verilated.h"
#include "VTestModule.h" // [重要] V{TARGET_MODULE_NAME}.h
#include <iostream>

int main(int argc, char** argv) {
Verilated::commandArgs(argc, argv);
VTestModule* top = new VTestModule; // [重要] V{TARGET_MODULE_NAME}

bool pass = true;

for (int a = 0; a < 16; ++a) {
    for (int b = 0; b < 16; ++b) {
        top->io_a = a;
        top->io_b = b;
        top->eval();
        
        int expected_c = (a + b) & 0xF; // 4位加法 (取模16)
        
        if (top->io_c != expected_c) {
            std::cout << "TEST FAILED: " 
                      << a << " + " << b 
                      << " => " << (int)top->io_c
                      << " (expected " << expected_c << ")" 
                      << std::endl;
            pass = false;
        }
    }
}

if (pass) {
    std::cout << "--- TEST PASSED ---" << std::endl;
}

delete top;
return 0;


}