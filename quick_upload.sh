#!/bin/bash

# 简单的自动上传脚本
# 快速上传当前更改到GitHub

# 检查是否在Git仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ 错误：当前目录不是Git仓库！"
    exit 1
fi

# 显示当前状态
echo "📊 当前Git状态："
git status --short

# 添加所有更改
echo "📝 添加所有更改..."
git add .

# 检查是否有更改
if git diff --cached --quiet; then
    echo "ℹ️  没有检测到更改，无需提交。"
    exit 0
fi

# 获取提交信息
if [ -n "$1" ]; then
    commit_msg="$1"
else
    commit_msg="Auto update: $(date '+%Y-%m-%d %H:%M:%S')"
fi

# 提交更改
echo "💾 提交更改: $commit_msg"
git commit -m "$commit_msg"

# 推送到GitHub
echo "🚀 推送到GitHub..."
git push

if [ $? -eq 0 ]; then
    echo "✅ 成功！代码已上传到GitHub！"
else
    echo "❌ 推送失败！请检查网络和权限。"
    exit 1
fi
