#!/usr/bin/env python3
"""
ChiseLLM 训练监控脚本

在训练过程中运行此脚本，可以实时显示训练进度和指标。
使用方法:
    python training/monitor_training.py

功能:
    1. 实时显示 loss 曲线 (ASCII 图表)
    2. 监控 GPU 使用情况
    3. 预估剩余时间
"""

import os
import sys
import time
import json
import glob
from datetime import datetime, timedelta
from pathlib import Path

# 颜色定义
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    """清屏"""
    os.system('clear' if os.name != 'nt' else 'cls')

def get_gpu_info():
    """获取 GPU 信息"""
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            return {
                'utilization': int(parts[0]),
                'memory_used': int(parts[1]),
                'memory_total': int(parts[2]),
                'temperature': int(parts[3])
            }
    except:
        pass
    return None

def draw_progress_bar(value, max_value, width=40, fill_char='█', empty_char='░'):
    """绘制进度条"""
    if max_value == 0:
        return empty_char * width
    ratio = min(value / max_value, 1.0)
    filled = int(width * ratio)
    return fill_char * filled + empty_char * (width - filled)

def draw_loss_chart(losses, width=60, height=10):
    """绘制 ASCII Loss 图表"""
    if len(losses) < 2:
        return "  等待更多数据点..."
    
    # 取最近的 width 个点
    recent_losses = losses[-width:] if len(losses) > width else losses
    
    min_loss = min(recent_losses)
    max_loss = max(recent_losses)
    loss_range = max_loss - min_loss if max_loss > min_loss else 1
    
    chart = []
    chart.append(f"  {max_loss:.4f} ┤")
    
    for row in range(height - 2, -1, -1):
        threshold = min_loss + (loss_range * row / (height - 1))
        line = "         │"
        for loss in recent_losses:
            if loss >= threshold:
                line += "●"
            else:
                line += " "
        chart.append(line)
    
    chart.append(f"  {min_loss:.4f} ┤" + "─" * len(recent_losses))
    chart.append("         └" + "─" * len(recent_losses) + f"▶ Steps")
    
    return '\n'.join(chart)

def parse_trainer_state(output_dir):
    """解析训练状态"""
    state_file = os.path.join(output_dir, "trainer_state.json")
    
    if not os.path.exists(state_file):
        return None
    
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        log_history = state.get('log_history', [])
        losses = [entry['loss'] for entry in log_history if 'loss' in entry]
        
        return {
            'epoch': state.get('epoch', 0),
            'global_step': state.get('global_step', 0),
            'max_steps': state.get('max_steps', 0),
            'losses': losses,
            'current_loss': losses[-1] if losses else None,
            'log_history': log_history
        }
    except:
        return None

def format_time(seconds):
    """格式化时间"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def display_dashboard(output_dir):
    """显示训练仪表板"""
    clear_screen()
    
    # 标题
    print(f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════════════╗
║                    🚀 ChiseLLM Training Monitor                    ║
╚════════════════════════════════════════════════════════════════════╝{Colors.RESET}
""")
    
    # 训练状态
    state = parse_trainer_state(output_dir)
    
    if state is None:
        print(f"  {Colors.YELLOW}⏳ 等待训练开始...{Colors.RESET}")
        print(f"  监控目录: {output_dir}")
        print(f"\n  提示: 请在另一个终端运行训练脚本")
        print(f"  {Colors.GREEN}bash training/train_chisel_lora.sh{Colors.RESET}")
        return
    
    # 进度信息
    progress = state['global_step'] / state['max_steps'] if state['max_steps'] > 0 else 0
    
    print(f"  {Colors.BOLD}📊 训练进度{Colors.RESET}")
    print(f"  ├─ Epoch:  {state['epoch']:.2f} / 3.0")
    print(f"  ├─ Step:   {state['global_step']} / {state['max_steps']}")
    print(f"  └─ 进度:   [{draw_progress_bar(state['global_step'], state['max_steps'])}] {progress*100:.1f}%")
    
    # Loss 信息
    print(f"\n  {Colors.BOLD}📉 Loss{Colors.RESET}")
    if state['current_loss']:
        print(f"  └─ 当前 Loss: {Colors.GREEN}{state['current_loss']:.4f}{Colors.RESET}")
    
    # Loss 图表
    if len(state['losses']) >= 2:
        print(f"\n  {Colors.BOLD}📈 Loss 曲线{Colors.RESET}")
        print(draw_loss_chart(state['losses']))
    
    # GPU 信息
    gpu_info = get_gpu_info()
    if gpu_info:
        print(f"\n  {Colors.BOLD}🖥️  GPU 状态{Colors.RESET}")
        gpu_bar = draw_progress_bar(gpu_info['utilization'], 100, width=30)
        mem_bar = draw_progress_bar(gpu_info['memory_used'], gpu_info['memory_total'], width=30)
        print(f"  ├─ 利用率:  [{gpu_bar}] {gpu_info['utilization']}%")
        print(f"  ├─ 显存:    [{mem_bar}] {gpu_info['memory_used']}/{gpu_info['memory_total']} MB")
        print(f"  └─ 温度:    {gpu_info['temperature']}°C")
    
    # 预估时间
    if state['global_step'] > 0 and state['max_steps'] > 0:
        # 从日志中估算速度
        log_history = state['log_history']
        if len(log_history) >= 2:
            recent = [l for l in log_history if 'loss' in l]
            if len(recent) >= 2:
                # 估算每 step 耗时 (假设每 10 steps 记录一次)
                steps_per_log = 10
                elapsed_logs = len(recent)
                avg_time_per_step = 2.0  # 估计值，实际根据硬件调整
                remaining_steps = state['max_steps'] - state['global_step']
                eta_seconds = remaining_steps * avg_time_per_step
                
                print(f"\n  {Colors.BOLD}⏱️  时间估算{Colors.RESET}")
                print(f"  └─ 预计剩余: {Colors.YELLOW}{format_time(eta_seconds)}{Colors.RESET}")
    
    # 刷新提示
    print(f"\n{Colors.CYAN}─────────────────────────────────────────────────────────────────────{Colors.RESET}")
    print(f"  最后更新: {datetime.now().strftime('%H:%M:%S')}  |  按 Ctrl+C 退出")
    print(f"  TensorBoard: {Colors.BLUE}http://localhost:6006{Colors.RESET} (需另开终端运行 tensorboard)")

def main():
    """主函数"""
    output_dir = "/home/silence_breaker/git/LLaMA-Factory/outputs/chisel-coder-lora"
    
    print(f"{Colors.GREEN}启动训练监控...{Colors.RESET}")
    print(f"监控目录: {output_dir}")
    
    try:
        while True:
            display_dashboard(output_dir)
            time.sleep(5)  # 每 5 秒刷新一次
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}监控已停止{Colors.RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
