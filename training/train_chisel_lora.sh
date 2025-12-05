#!/bin/bash
# =============================================================================
# ChiseLLM LoRA 训练脚本
# 
# 使用方法:
#   bash training/train_chisel_lora.sh
#
# 训练可视化:
#   在另一个终端运行: tensorboard --logdir=outputs/chisel-coder-lora
#   然后打开浏览器访问: http://localhost:6006
# =============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_header() {
    echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}               🚀 ${GREEN}ChiseLLM SFT 训练启动器${NC}                     ${CYAN}║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
}

print_step() {
    echo -e "\n${BLUE}▶${NC} ${GREEN}$1${NC}"
}

print_info() {
    echo -e "  ${YELLOW}ℹ${NC} $1"
}

print_success() {
    echo -e "  ${GREEN}✔${NC} $1"
}

print_error() {
    echo -e "  ${RED}✖${NC} $1"
}

# 配置路径
CHISEL_LLM_DIR="/home/silence_breaker/git/ChiseLLM"
LLAMA_FACTORY_DIR="/home/silence_breaker/git/LLaMA-Factory"
CONFIG_FILE="${CHISEL_LLM_DIR}/training/chisel_lora_config.yaml"
DATASET_FILE="${CHISEL_LLM_DIR}/dataset/chisel_sft_merged_10550.jsonl"
TARGET_DATASET="${LLAMA_FACTORY_DIR}/data/chisel_sft.jsonl"

# 显示标题
print_header

# Step 1: 检查环境
print_step "检查训练环境..."

# 检查 conda 环境
CURRENT_ENV=$(conda info --envs | grep '*' | awk '{print $1}')
if [ "$CURRENT_ENV" != "chisel-train" ]; then
    print_error "请先激活 chisel-train 环境: conda activate chisel-train"
    exit 1
fi
print_success "Conda 环境: chisel-train ✓"

# 检查 GPU
if ! command -v nvidia-smi &> /dev/null; then
    print_error "未检测到 NVIDIA GPU"
    exit 1
fi
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
print_success "GPU: ${GPU_NAME} (${GPU_MEM})"

# Step 2: 准备数据集
print_step "准备数据集..."

if [ ! -f "$DATASET_FILE" ]; then
    print_error "数据集不存在: $DATASET_FILE"
    exit 1
fi

SAMPLE_COUNT=$(wc -l < "$DATASET_FILE")
print_info "数据集: ${DATASET_FILE}"
print_info "样本数: ${SAMPLE_COUNT}"

# 复制数据集到 LLaMA-Factory
cp "$DATASET_FILE" "$TARGET_DATASET"
print_success "数据集已复制到 LLaMA-Factory"

# Step 3: 更新数据集配置
print_step "配置 LLaMA-Factory..."

# 创建简洁的数据集配置
DATASET_INFO_FILE="${LLAMA_FACTORY_DIR}/data/dataset_info.json"

# 备份原配置
if [ -f "$DATASET_INFO_FILE" ]; then
    cp "$DATASET_INFO_FILE" "${DATASET_INFO_FILE}.bak"
fi

# 写入新的数据集配置
cat > "$DATASET_INFO_FILE" << 'EOF'
{
  "chisel_sft": {
    "file_name": "chisel_sft.jsonl",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
EOF

print_success "数据集配置已更新"

# Step 4: 显示训练配置
print_step "训练配置预览..."

echo -e "
  ${CYAN}┌─────────────────────────────────────────┐${NC}
  ${CYAN}│${NC}  ${YELLOW}模型${NC}: Qwen2.5-Coder-14B-Instruct      ${CYAN}│${NC}
  ${CYAN}│${NC}  ${YELLOW}方法${NC}: LoRA (rank=64, alpha=128)       ${CYAN}│${NC}
  ${CYAN}│${NC}  ${YELLOW}数据${NC}: ${SAMPLE_COUNT} 样本                      ${CYAN}│${NC}
  ${CYAN}│${NC}  ${YELLOW}轮数${NC}: 3 epochs                        ${CYAN}│${NC}
  ${CYAN}│${NC}  ${YELLOW}批次${NC}: 2 × 8 = 16 (有效批次)            ${CYAN}│${NC}
  ${CYAN}│${NC}  ${YELLOW}学习率${NC}: 2e-4 (cosine decay)           ${CYAN}│${NC}
  ${CYAN}│${NC}  ${YELLOW}量化${NC}: 4-bit (bitsandbytes)            ${CYAN}│${NC}
  ${CYAN}└─────────────────────────────────────────┘${NC}
"

# Step 5: 开始训练
print_step "启动 SFT 训练..."
echo -e "
  ${YELLOW}💡 提示:${NC}
  - 在另一个终端运行以下命令查看训练曲线:
    ${GREEN}tensorboard --logdir=${LLAMA_FACTORY_DIR}/outputs/chisel-coder-lora${NC}
  - 然后在浏览器打开: ${BLUE}http://localhost:6006${NC}
  - 按 Ctrl+C 可中断训练
"

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}训练开始时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"

# 切换到 LLaMA-Factory 目录并启动训练
cd "$LLAMA_FACTORY_DIR"

# 使用 llamafactory-cli 命令启动训练
llamafactory-cli train "$CONFIG_FILE"

# 训练完成
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ 训练完成！${NC}"
echo -e "${GREEN}训练结束时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

print_info "模型保存位置: ${LLAMA_FACTORY_DIR}/outputs/chisel-coder-lora"
print_info "下一步: 运行评估脚本测试模型效果"
echo -e "  ${GREEN}python eval/run_eval.py --model ${LLAMA_FACTORY_DIR}/outputs/chisel-coder-lora${NC}"
