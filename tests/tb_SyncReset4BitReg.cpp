#include <stdlib.h>
#include <iostream>
#include <verilated.h>
#include <verilated_vcd_c.h>
#include "VSyncReset4BitReg.h"

#define MAX_SIM_TIME 20
vluint64_t sim_time = 0;

int main(int argc, char** argv, char** env) {
    Verilated::commandArgs(argc, argv);
    VSyncReset4BitReg *dut = new VSyncReset4BitReg;

    Verilated::traceEverOn(true);
    VerilatedVcdC *m_trace = new VerilatedVcdC;
    dut->trace(m_trace, 5);
    m_trace->open("waveform.vcd");

    bool test_passed = true;

    // Initial reset
    dut->clock = 0;
    dut->reset = 1;
    dut->io_reset = 1;
    dut->eval();
    m_trace->dump(sim_time++);

    dut->clock = 1;
    dut->eval();
    m_trace->dump(sim_time++);
    dut->clock = 0;
    dut->reset = 0;

    // Test cases
    struct TestCase {
        bool io_reset;
        uint8_t d;
        uint8_t expected_q;
    } test_cases[4] = {
        {1, 0xA, 0x0},  // Reset active
        {0, 0xA, 0xA},  // Reset inactive, load A
        {1, 0x5, 0x0},  // Reset active again
        {0, 0x5, 0x5}   // Reset inactive, load 5
    };

    for (int i = 0; i < 4; i++) {
        dut->io_reset = test_cases[i].io_reset;
        dut->io_d = test_cases[i].d;

        dut->clock = 1;
        dut->eval();
        m_trace->dump(sim_time++);

        dut->clock = 0;
        dut->eval();
        m_trace->dump(sim_time++);

        if (dut->io_q != test_cases[i].expected_q) {
            std::cout << "Error at test case " << i 
                      << ": expected " << (int)test_cases[i].expected_q
                      << ", got " << (int)dut->io_q << std::endl;
            test_passed = false;
        }
    }

    m_trace->close();
    delete dut;
    
    if (test_passed) {
        std::cout << "TEST PASSED" << std::endl;
        return 0;
    } else {
        std::cout << "TEST FAILED" << std::endl;
        return 1;
    }
}