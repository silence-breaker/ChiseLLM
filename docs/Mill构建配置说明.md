# Mill 构建配置说明

> ⚠️ **重要提示**: 本项目使用 `run_reflect.py` 作为唯一的编译和验证方式，不使用 IDE 集成。

---

## 概述

本项目的 `build.sc` 文件是 Mill 构建工具的配置文件，**仅供 `reflect_env.py` 内部使用**，不用于 VS Code Metals 等 IDE 集成。

---

## 为什么不使用 Metals？

| 问题 | 说明 |
|------|------|
| **Scala 版本冲突** | Metals 要求 Scala 2.13.14+，但 Chisel 6.0.0 仅支持 2.13.12 |
| **数据集兼容性** | 已生成 1 万条基于 Chisel 6.0.0 的数据集，升级版本会破坏兼容性 |
| **功能完备** | `run_reflect.py` 已提供完整的编译、阐述、仿真功能 |

---

## 当前配置

`build.sc` 文件内容：

```scala
import mill._
import mill.scalalib._

/**
 * ChiseLLM 项目 - Mill 构建配置
 * 
 * 注意: 此文件仅供 reflect_env.py 内部使用，不用于 IDE 集成。
 * 请使用 `python src/run_reflect.py` 进行编译和验证。
 * 
 * 技术栈版本 (与数据集保持一致):
 *   - Scala: 2.13.12
 *   - Chisel: 6.0.0
 */
object chiselllm extends ScalaModule {
  def scalaVersion = "2.13.12"
  
  // Chisel 依赖 (Mill 1.x 语法)
  def mvnDeps = Seq(
    mvn"org.chipsalliance::chisel:6.0.0"
  )
  
  // Scala 编译选项
  def scalacOptions = Seq(
    "-Xsource:2.13",
    "-language:reflectiveCalls",
    "-deprecation",
    "-feature",
    "-Xcheckinit"
  )
  
  // Chisel 编译器插件
  def scalacPluginMvnDeps = Seq(
    mvn"org.chipsalliance:::chisel-plugin:6.0.0"
  )
  
  // 源目录
  def sources = Task.Sources(os.pwd / "tests")
}
```

---

## 正确的编译方式

### ✅ 推荐：使用反射环境

```bash
# 1. 激活 Conda 环境
conda activate chisel-llm

# 2. 编译和阐述（生成 Verilog）
python src/run_reflect.py --file tests/my_module.scala

# 3. 完整测试（包含仿真）
python src/run_reflect.py --file tests/my_module.scala --testbench tests/tb_my_module.cpp
```

### ❌ 不推荐

```bash
# 这些命令不应该直接使用
mill chiselllm.compile       # 不推荐
sbt compile                  # 不推荐
```

---

## 输出说明

运行 `run_reflect.py` 后的输出：

```text
ℹ 自动检测到模块名: TenTimer
============================================================
ChiseLLM 反射环境测试
============================================================
源文件:     tests/ten_timer.scala
模块名:     TenTimer
Testbench:  (未提供,仅编译和阐述)
输出目录:   tests
============================================================

⏳ 编译和阐述中 (使用 Mill)...
✓ 编译成功
✓ 阐述成功
✓ Verilog 已保存到: tests/related_Verilog.v
ℹ 未提供 testbench,跳过仿真阶段
✓ 测试报告已保存到: tests/result.json

============================================================
测试结果摘要
============================================================
编译状态:   ✓ 成功
阐述状态:   ✓ 成功
仿真状态:   (未测试)
失败阶段:   passed
============================================================
✓ 所有测试通过!
```

---

## 版本锁定说明

| 组件 | 版本 | 原因 |
|------|------|------|
| Scala | 2.13.12 | Chisel 6.0.0 编译器插件仅支持此版本 |
| Chisel | 6.0.0 | 与 1 万条已生成数据集保持一致 |
| Mill | 1.0.6 | 使用 Mill 1.x API 语法 |

> **不要升级这些版本**，除非您准备重新生成整个数据集。

---

## 历史说明

本项目曾计划使用 VS Code + Metals 进行开发，但由于以下原因放弃：

1. Metals 要求较新的 Scala 版本，与 Chisel 6.0.0 不兼容
2. 升级 Chisel 版本会导致已生成的数据集失效
3. `run_reflect.py` 已提供足够的编译验证功能

如果您需要 IDE 智能提示功能，可以考虑：
- 升级到 Chisel 6.6.0 + Scala 2.13.15（需重新生成数据集）
- 或者使用 IntelliJ IDEA with Scala plugin

---

**版本**: v2.2  
**更新日期**: 2025-11-25  
**作者**: ChiseLLM Project
