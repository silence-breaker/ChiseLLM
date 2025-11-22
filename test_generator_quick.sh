#!/bin/bash
# 快速测试脚本 - 生成 5 个样本来验证修复

echo "======================================"
echo "开始快速测试数据生成器 (5 samples)"
echo "======================================"

cd /home/silence_breaker/git/ChiseLLM

# 使用 stdbuf -oL 强制行缓冲
stdbuf -oL conda run -n chisel-llm python data_gen/generator.py 5 2

echo ""
echo "======================================"
echo "测试完成"
echo "======================================"
