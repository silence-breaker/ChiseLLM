#!/usr/bin/env python3
"""
合并数据集并复制到 LLaMA-Factory

用法:
    python data_gen/merge_and_prepare.py [supplement_file]
    
如果不指定 supplement_file，会自动查找最新的 chisel_util_supplement_*.jsonl
"""

import sys
import os
import json
import glob
from datetime import datetime

def find_latest_supplement():
    """查找最新的补充数据集"""
    pattern = "dataset/chisel_util_supplement_*.jsonl"
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getctime)

def main():
    # 路径配置
    base_dataset = "dataset/chisel_sft_dataset_v2_20251124_081913.jsonl"
    llama_factory_data = "/home/silence_breaker/git/LLaMA-Factory/data/chisel_sft.jsonl"
    
    # 查找补充数据集
    if len(sys.argv) > 1:
        supplement_file = sys.argv[1]
    else:
        supplement_file = find_latest_supplement()
    
    if not supplement_file or not os.path.exists(supplement_file):
        print(f"❌ 找不到补充数据集: {supplement_file}")
        print("请先运行 generate_missing_samples.py")
        sys.exit(1)
    
    print("=" * 60)
    print("📊 合并数据集")
    print("=" * 60)
    print(f"  基础数据集: {base_dataset}")
    print(f"  补充数据集: {supplement_file}")
    print(f"  目标位置: {llama_factory_data}")
    
    # 读取基础数据集
    print("\n📖 读取基础数据集...")
    base_samples = []
    with open(base_dataset, 'r', encoding='utf-8') as f:
        for line in f:
            base_samples.append(json.loads(line))
    print(f"  ✅ 基础样本: {len(base_samples)}")
    
    # 读取补充数据集
    print("\n📖 读取补充数据集...")
    supplement_samples = []
    with open(supplement_file, 'r', encoding='utf-8') as f:
        for line in f:
            supplement_samples.append(json.loads(line))
    print(f"  ✅ 补充样本: {len(supplement_samples)}")
    
    # 合并
    all_samples = base_samples + supplement_samples
    print(f"\n📦 合并后总样本: {len(all_samples)}")
    
    # 打乱顺序（可选，有助于训练）
    import random
    random.seed(42)
    random.shuffle(all_samples)
    print("  ✅ 已打乱顺序")
    
    # 统计 chisel3.util 覆盖
    util_count = 0
    enum_count = 0
    popcount_count = 0
    for sample in all_samples:
        output = sample.get('output', '')
        if 'import chisel3.util' in output:
            util_count += 1
        if 'Enum(' in output:
            enum_count += 1
        if 'PopCount' in output:
            popcount_count += 1
    
    print(f"\n📊 chisel3.util 统计:")
    print(f"  - import chisel3.util: {util_count} ({util_count/len(all_samples)*100:.1f}%)")
    print(f"  - Enum(): {enum_count}")
    print(f"  - PopCount: {popcount_count}")
    
    # 保存到本地备份
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"dataset/chisel_sft_merged_{timestamp}.jsonl"
    
    print(f"\n💾 保存本地备份: {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    # 复制到 LLaMA-Factory
    print(f"\n🚀 复制到 LLaMA-Factory: {llama_factory_data}")
    with open(llama_factory_data, 'w', encoding='utf-8') as f:
        for sample in all_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + '\n')
    
    print("\n" + "=" * 60)
    print("✅ 数据准备完成！")
    print("=" * 60)
    print(f"  总样本数: {len(all_samples)}")
    print(f"  chisel3.util 覆盖率: {util_count/len(all_samples)*100:.1f}%")
    print(f"\n下一步: 运行训练")
    print(f"  cd /home/silence_breaker/git/LLaMA-Factory")
    print(f"  conda activate chisel-train")
    print(f"  bash run_chisel_sft.sh")

if __name__ == "__main__":
    main()
