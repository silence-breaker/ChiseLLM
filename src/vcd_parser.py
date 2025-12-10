"""
ChiseLLM VCD 解析器与波形可视化

将 Verilator 生成的 VCD 波形文件转换为 WaveDrom JSON 格式，
用于在浏览器端渲染波形图。

作者: ChiseLLM Project
日期: 2025-12-09
"""

from vcdvcd import VCDVCD
from typing import Dict, List, Optional, Any
import json


def vcd_to_wavedrom(
    vcd_file: str,
    signals: Optional[List[str]] = None,
    max_cycles: int = 30,
    clock_signal: str = "clock"
) -> Dict[str, Any]:
    """
    将 VCD 文件转换为 WaveDrom JSON 格式
    
    Args:
        vcd_file: VCD 文件路径
        signals: 要显示的信号列表 (None 表示全部)
        max_cycles: 最大显示周期数 (默认 30，适合显示)
        clock_signal: 时钟信号名称
        
    Returns:
        WaveDrom JSON 格式的字典
    """
    try:
        vcd = VCDVCD(vcd_file)
    except Exception as e:
        return {"error": f"无法解析 VCD 文件: {str(e)}"}
    
    # 获取所有信号 (vcd.signals 是列表)
    all_signals = vcd.signals if isinstance(vcd.signals, list) else list(vcd.signals.keys())
    
    if not all_signals:
        return {"error": "VCD 文件中未找到信号"}
    
    # 按短名称去重，避免同一信号因层级路径不同而重复显示
    # 例如 TOP.Module.clock 和 TOP.Module.Module.clock 实际上是同一个信号
    seen_short_names = set()
    unique_signals = []
    for s in all_signals:
        short_name = s.split(".")[-1]
        if short_name not in seen_short_names:
            seen_short_names.add(short_name)
            unique_signals.append(s)
    
    # 如果未指定信号，使用去重后的信号
    if signals is None:
        signals = unique_signals
    
    # 过滤有效信号
    valid_signals = [s for s in signals if s in all_signals]
    
    if not valid_signals:
        return {"error": f"未找到指定的信号。可用信号: {all_signals[:10]}"}
    
    # 获取时间信息
    timescale = vcd.timescale.get("timescale", "1ns")
    
    # 构建 WaveDrom signal 数组
    wavedrom_signals = []
    
    for signal_name in valid_signals[:10]:  # 限制最多 10 个信号
        signal = vcd[signal_name]
        wave_str = ""
        data_list = []
        
        # 获取信号的时间-值对
        tv_pairs = signal.tv
        
        if not tv_pairs:
            continue
        
        # 确定位宽 (确保是整数)
        try:
            bit_width = int(signal.size) if signal.size else 1
        except (ValueError, TypeError):
            bit_width = 1
        is_bus = bit_width > 1
        
        # 采样信号值 (简化：按固定间隔采样)
        sample_times = list(range(0, max_cycles * 10, 10))[:max_cycles]
        
        prev_value = None
        for i, t in enumerate(sample_times):
            # 找到该时间点的值
            current_value = None
            for tv_time, tv_value in tv_pairs:
                # 确保 tv_time 是整数进行比较
                try:
                    tv_time_int = int(tv_time)
                except (ValueError, TypeError):
                    tv_time_int = 0
                if tv_time_int <= t:
                    current_value = tv_value
                else:
                    break
            
            if current_value is None:
                current_value = tv_pairs[0][1] if tv_pairs else "x"
            
            if is_bus:
                # 多位信号：使用 "=" 表示数据变化，"." 表示保持
                if current_value != prev_value:
                    wave_str += "="
                    # 转换值为十六进制
                    try:
                        if isinstance(current_value, str) and current_value.startswith("b"):
                            hex_val = hex(int(current_value[1:], 2))[2:].upper()
                        else:
                            hex_val = str(current_value)
                        data_list.append(f"0x{hex_val}")
                    except:
                        data_list.append(str(current_value))
                else:
                    wave_str += "."
            else:
                # 单位信号：第一个采样点或值变化时写入实际值，否则用 "." 延续
                if i == 0 or current_value != prev_value:
                    if current_value == "1":
                        wave_str += "1"
                    elif current_value == "0":
                        wave_str += "0"
                    elif current_value == "x":
                        wave_str += "x"
                    else:
                        wave_str += "."
                else:
                    # 保持不变，使用 "." 延续
                    wave_str += "."
            
            prev_value = current_value
        
        # 构建信号条目
        signal_entry = {
            "name": signal_name.split(".")[-1],  # 使用短名称
            "wave": wave_str[:max_cycles]
        }
        
        if data_list:
            signal_entry["data"] = data_list
        
        wavedrom_signals.append(signal_entry)
    
    # 添加时钟信号 (如果不存在则生成)
    has_clock = any("clock" in s.lower() or "clk" in s.lower() for s in valid_signals)
    if not has_clock:
        clock_wave = "p" + "." * (max_cycles - 1)
        wavedrom_signals.insert(0, {"name": "clk", "wave": clock_wave})
    
    # 构建 WaveDrom JSON (使用更清晰的配置)
    wavedrom_json = {
        "signal": wavedrom_signals,
        "config": {
            "hscale": 2,  # 水平缩放，让波形更宽
            "skin": "default"
        },
        "head": {
            "text": ["tspan", {"class": "h3"}, "Simulation Waveform"],
            "tick": 0,
            "every": 5
        },
        "foot": {
            "text": f"Timescale: {timescale}",
            "tick": 0
        }
    }
    
    return wavedrom_json


def generate_wavedrom_html(wavedrom_json: Dict[str, Any], height: int = 300) -> str:
    """
    生成包含 WaveDrom 渲染的 HTML 代码
    
    Args:
        wavedrom_json: WaveDrom JSON 数据
        height: 渲染区域高度
        
    Returns:
        完整的 HTML 代码字符串
    """
    json_str = json.dumps(wavedrom_json, indent=2)
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/wavedrom/3.1.0/skins/default.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/wavedrom/3.1.0/wavedrom.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            background: #ffffff;
            font-family: 'Consolas', 'Monaco', monospace;
            padding: 16px;
        }}
        #waveform {{
            background: #fafafa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
            min-height: {height}px;
        }}
        /* WaveDrom 样式覆盖 */
        svg {{
            font-family: 'Consolas', 'Monaco', monospace !important;
        }}
        svg text {{
            font-size: 12px !important;
            fill: #333 !important;
        }}
    </style>
</head>
<body onload="WaveDrom.ProcessAll()">
    <div id="waveform">
        <script type="WaveDrom">
{json_str}
        </script>
    </div>
</body>
</html>
"""
    return html


def generate_default_testbench(module_name: str, signals: List[Dict[str, str]], max_cycles: int = 50) -> str:
    """
    生成默认的 C++ Testbench 用于 Verilator 仿真
    
    Args:
        module_name: 模块名称
        signals: 信号列表 [{"name": "io_xxx", "direction": "input/output", "width": 8}]
        max_cycles: 仿真周期数
        
    Returns:
        C++ Testbench 代码
    """
    cpp_code = f"""
#include <stdlib.h>
#include "V{module_name}.h"
#include "verilated.h"
#include "verilated_vcd_c.h"

int main(int argc, char** argv) {{
    Verilated::commandArgs(argc, argv);
    Verilated::traceEverOn(true);
    
    V{module_name}* top = new V{module_name};
    VerilatedVcdC* tfp = new VerilatedVcdC;
    top->trace(tfp, 99);
    tfp->open("waveform.vcd");
    
    vluint64_t sim_time = 0;
    
    // 初始化
    top->clock = 0;
    top->reset = 1;
    
    // 仿真循环
    for (int cycle = 0; cycle < {max_cycles * 2}; cycle++) {{
        // 时钟翻转
        top->clock = !top->clock;
        
        // 复位逻辑
        if (cycle > 10) {{
            top->reset = 0;
        }}
        
        // 计算更新
        top->eval();
        tfp->dump(sim_time);
        sim_time++;
    }}
    
    tfp->close();
    delete top;
    
    printf("TEST PASSED\\n");
    return 0;
}}
"""
    return cpp_code
