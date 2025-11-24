# VS Code + Mill 编译 Scala/Chisel 文件指南

## 概述

本文档介绍如何在 ChiseLLM 项目中使用 VS Code 配合 Mill 构建工具编译 Scala/Chisel 文件。

---

## 前置条件

### 1. 确认 Mill 已安装

```bash
mill --version
# 应显示: Mill Build Tool version 0.11.6
```

如果未安装，执行：
```bash
# 激活 conda 环境
conda activate chisel-llm

# 安装 Mill（已自动安装到 conda 环境）
which mill
```

### 2. 确认 VS Code 插件

确保已安装 **Scala (Metals)** 插件：
- 打开 VS Code
- 按 `Ctrl+Shift+X` 打开扩展面板
- 搜索 "Scala (Metals)"
- 确认已安装并启用

---

## 方法一：通过 Mill 命令编译（推荐）

### 1. 编译整个项目

在项目根目录执行：

```bash
# 激活环境
conda activate chisel-llm

# 编译项目
mill chiselllm.compile
```

**说明**：
- `chiselllm` 是 `build.sc` 中定义的模块名
- 编译结果保存在 `out/chiselllm/compile.dest/` 目录

### 2. 清理构建缓存

```bash
mill clean
```

### 3. 查看可用任务

```bash
mill resolve chiselllm._
```

输出示例：
```
chiselllm.allSources
chiselllm.compile
chiselllm.run
chiselllm.repl
...
```

### 4. 运行 Scala 主类

```bash
mill chiselllm.run
```

**注意**：这会尝试运行 `chiselllm/src/` 中的 `main` 方法。对于纯模块定义（如 `ten_timer.scala`），不需要运行，只需编译验证即可。

---

## 方法二：通过 VS Code 任务编译

### 1. 创建 `.vscode/tasks.json`

在项目根目录创建 `.vscode` 文件夹（如果不存在），然后创建 `tasks.json`：

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Mill: 编译项目",
      "type": "shell",
      "command": "mill",
      "args": ["chiselllm.compile"],
      "group": {
        "kind": "build",
        "isDefault": true
      },
      "presentation": {
        "reveal": "always",
        "panel": "shared"
      },
      "problemMatcher": []
    },
    {
      "label": "Mill: 清理项目",
      "type": "shell",
      "command": "mill",
      "args": ["clean"],
      "presentation": {
        "reveal": "always",
        "panel": "shared"
      }
    },
    {
      "label": "Mill: 重新生成 BSP",
      "type": "shell",
      "command": "mill",
      "args": ["mill.bsp.BSP/install"],
      "presentation": {
        "reveal": "always",
        "panel": "shared"
      }
    }
  ]
}
```

### 2. 使用 VS Code 任务

按 `Ctrl+Shift+B` 或：
1. 按 `Ctrl+Shift+P` 打开命令面板
2. 输入 "Tasks: Run Build Task"
3. 选择 "Mill: 编译项目"

---

## 方法三：通过 Metals 自动编译（最智能）

### 1. 导入构建配置

**首次使用或修改 `build.sc` 后必须执行**：

1. 按 `Ctrl+Shift+P` 打开命令面板
2. 输入并选择 **"Metals: Import build"**
3. 等待底部状态栏显示导入完成

### 2. 自动编译

导入成功后，Metals 会自动：
- ✅ 实时检查语法错误（红色波浪线）
- ✅ 提供代码补全和类型提示
- ✅ 在保存文件时自动编译

### 3. 查看编译错误

- **问题面板**：按 `Ctrl+Shift+M` 查看所有错误
- **行内提示**：鼠标悬停在红色波浪线上查看错误详情

### 4. 跳转到定义

- 按住 `Ctrl` 点击类名、方法名等，跳转到定义处
- 右键 → "Go to Definition" 或按 `F12`

---

## 方法四：通过 ChiseLLM 反射环境编译（项目专用）

### 适用场景

当你需要完整测试 Chisel 模块（编译 + 阐述 + 仿真）时使用。

### 基本用法

```bash
# 激活环境
conda activate chisel-llm

# 编译并阐述（生成 Verilog）
python src/run_reflect.py --file tests/ten_timer.scala

# 完整测试（包含仿真）
python src/run_reflect.py --file tests/ten_timer.scala --testbench tests/tb_ten_timer.cpp
```

### 输出说明

```
⏳ 编译和阐述中 (使用 Mill)...
✓ 编译成功
✓ 阐述成功
✓ Verilog 已保存到: tests/related_Verilog.v
```

结果文件：
- `tests/related_Verilog.v` - 生成的 Verilog 代码
- `tests/result.json` - 详细测试报告

---

## 常见问题与解决方案

### Q1: VS Code 显示 "import chisel3._ 找不到"

**原因**：Metals 尚未导入构建配置。

**解决**：
1. 按 `Ctrl+Shift+P`
2. 选择 "Metals: Import build"
3. 等待完成（首次需要下载依赖，约 1-2 分钟）

### Q2: 修改 `build.sc` 后错误不消失

**解决**：每次修改 `build.sc` 后需要重新导入：
```
Ctrl+Shift+P → "Metals: Import build"
```

### Q3: Mill 编译报错但 VS Code 没显示

**解决**：在终端手动运行查看详细错误：
```bash
mill chiselllm.compile
```

### Q4: 编译速度慢

**优化**：
- Mill 首次运行需要下载依赖（约 50MB），后续会很快
- 增量编译：只重新编译修改的文件
- 缓存位置：`~/.cache/mill` 和项目 `out/` 目录

### Q5: 如何查看 Metals 日志

1. 按 `Ctrl+Shift+P`
2. 输入 "Metals: Show Metals logs"
3. 查看详细日志

---

## 编译流程对比

### ChiseLLM 项目的两种编译方式

| 特性 | Mill 直接编译 | run_reflect.py |
|------|---------------|----------------|
| **用途** | 代码开发、IDE 支持 | 自动化测试、数据生成 |
| **编译方式** | 项目根目录 `build.sc` | 临时目录动态创建 |
| **输出** | 编译后的 `.class` 文件 | Verilog + 仿真结果 |
| **速度** | 快（增量编译） | 慢（完整流程） |
| **推荐场景** | 日常开发 | CI/CD 测试 |

---

## 最佳实践

### 日常开发工作流

1. **编辑代码**
   - 在 VS Code 中编辑 `.scala` 文件
   - Metals 自动检查语法（保存时编译）

2. **本地验证**
   ```bash
   # 快速编译检查
   mill chiselllm.compile
   ```

3. **完整测试**
   ```bash
   # 使用反射环境测试
   python src/run_reflect.py --file tests/your_module.scala
   ```

4. **批量生成数据**
   ```bash
   # 生成训练数据集
   python data_gen/generator_V2.py 100 4
   ```

### IDE 配置检查清单

- [ ] Metals 插件已安装
- [ ] 执行过 "Metals: Import build"
- [ ] `import chisel3._` 无红色波浪线
- [ ] 代码补全正常工作（输入 `io.` 有提示）
- [ ] 可以跳转到定义（`Ctrl+点击`）

---

## 快速命令参考

```bash
# === Mill 基础命令 ===
mill chiselllm.compile              # 编译项目
mill clean                          # 清理构建
mill mill.bsp.BSP/install          # 重新生成 BSP 配置

# === ChiseLLM 测试命令 ===
python src/run_reflect.py --file tests/ten_timer.scala                    # 编译+阐述
python src/run_reflect.py --file tests/ten_timer.scala --testbench ...   # 完整测试
python data_gen/generator_V2.py 100 4                                     # 生成数据

# === VS Code 快捷键 ===
Ctrl+Shift+P                        # 命令面板
Ctrl+Shift+B                        # 运行构建任务
Ctrl+Shift+M                        # 查看问题面板
F12                                 # 跳转到定义
Ctrl+`                              # 打开终端
```

---

## 附录：build.sc 文件说明

项目根目录的 `build.sc` 定义了 Mill 构建配置：

```scala
import mill._
import mill.scalalib._

object chiselllm extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  // Chisel 6.0.0 依赖
  def ivyDeps = Agg(
    ivy"org.chipsalliance::chisel:6.0.0"
  )
  
  // Chisel 编译器插件
  def scalacPluginIvyDeps = Agg(
    ivy"org.chipsalliance:::chisel-plugin:6.0.0"
  )
}
```

**关键点**：
- `chiselllm` 是模块名（用于 `mill chiselllm.compile`）
- `scalaVersion` 必须与 Chisel 兼容
- `ivyDeps` 定义项目依赖
- `scalacPluginIvyDeps` 定义编译器插件

---

## 总结

**推荐工作流程**：

1. ✅ **开发时**：使用 VS Code + Metals 自动编译（最方便）
2. ✅ **验证时**：使用 `mill chiselllm.compile`（快速检查）
3. ✅ **测试时**：使用 `python src/run_reflect.py`（完整验证）

现在你已经掌握了在 ChiseLLM 项目中使用 VS Code + Mill 编译 Scala/Chisel 文件的所有方法！

---

**版本**: v2.1 (Mill)  
**更新日期**: 2025-11-24  
**作者**: ChiseLLM Project
