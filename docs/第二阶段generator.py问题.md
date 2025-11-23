# ChiseLLM 第二阶段：数据生成器改进备忘录

**文档目标：** 汇总 `generator.py` 的当前状态、已修复的问题以及后续优化建议，指导 SFT 数据工程的迭代。

## 1. 当前状态评估 (Current Status)

- **代码成熟度**：⭐⭐⭐⭐⭐

  - `generator.py` 实现了 **多进程加速 (Multiprocessing)**、**进度条显示 (TQDM)** 和 **无痕内存验证 (In-memory Reflection)**，工程实现非常成熟且高效。

- **数据策略**：✅ 已就绪

  - 采用了分级课程策略 (Level 1: 60%, Level 2: 30%, Level 3: 10%)。

  - **已解决模块命名问题**：代码中已集成语义化命名逻辑（如 `prefixes` + `nouns` 的随机组合），解决了之前 `ModuleL1_0` 命名过于机械的问题。

- **行动建议**：**Ready to Launch**。当前脚本完全可以用于生成第一版 10,000 条数据并启动模型训练。

## 2. 建议改进清单 (Improvements Checklist)

这些改进不必阻止当前的训练计划，建议在第一版模型训练期间并行开发 **Generator v2.0**。

### 🚀 优先级：高 (High Priority) - 影响模型泛化能力

1. **增加指令 (Prompt) 多样性**

    - **问题**：目前的 Instruction 模板比较单一（例如总是 _"Implement a module performing..."_）。这会导致模型过拟合特定的提问句式。

    - **建议**：为每个任务类型创建一个“指令池 (`instruction_pool`)”，随机抽取不同的问法。

    - _例子_：

        - "Write an adder module."

        - "Create a circuit that adds two inputs."

        - "I need a module named 'FastAdder' to compute sum."

2. **补充高频语法模板 (Cat, Slice, MuxCase)**

    - **问题**：Level 2 目前缺少一些 Chisel 硬件设计中极常用的操作符，可能导致模型生成的代码不够“地道”（例如用循环去拼位，而不是用 `Cat`）。

    - **建议新增模板**：

        - **位拼接**：`val res = Cat(io.high, io.low)`

        - **位截取**：`val slice = io.data(7, 0)` 或 `io.data.head(4)`

        - **多路条件**：`MuxCase` (比嵌套的 `Mux` 更常见)

3. **完善 Level 3：状态机 (FSM)**

    - **问题**：目前的 Level 3 只有计数器和移位寄存器，缺乏硬件逻辑的核心——有限状态机。

    - **建议新增模板**：引入 `Enum` 定义状态，配合 `switch / is` 语法。这是 Chisel 相比 Verilog 的一大优势，模型必须学会。

### 🛠 优先级：中 (Medium Priority) - 工程体验优化

4. **捕获验证失败日志**

    - **问题**：目前 `worker_task` 验证失败后直接返回 `None`，如果某个新写的模板有 Bug 导致通过率为 0%，很难被发现。

    - **建议**：添加一个简单的错误日志机制，将验证失败的 `code` 或 `error_log` 写入 `generation_errors.log` 文件，方便排查模板错误。

5. **代码格式微调**

    - **问题**：Jinja2 模板渲染后，代码首尾可能保留多余的换行符。

    - **建议**：在 `generate_*` 函数返回前，对 `code` 字符串调用 `.strip()`。

## 3. 下一步行动计划 (Action Plan)

1. **[立即执行] 生成数据**：

    - 运行当前的 `generator.py`。

    - 生成 **5,000 - 10,000** 条数据。

    - 保存为 `dataset/chisel_sft_dataset_v1.jsonl`。

2. **[立即执行] 启动训练**：

    - 使用 **LLaMA-Factory**。

    - 模型：**Qwen2.5-Coder-14B-Instruct** (配合 4-bit QLoRA)。

    - 这就是你的 **Baseline 模型**。

3. **[并行开发] 迭代 Generator v2.0**：

    - 在模型“炼丹”的几个小时里，着手修改 `generator.py`，加入状态机模板和指令池。

    - 如果 v1 模型效果不够完美，使用 v2 数据集进行第二轮微调。
