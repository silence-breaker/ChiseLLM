# 本科生预研究报告

# 构建“LLM-Chisel反射环”的可行性蓝图

## 一、 核心定位与目标 (Vision & Objective)

- **长期愿景:** 最终实现一个能自动生成、验证、并优化（PPA）Chisel硬件设计的AI智能体。

- **当前目标 (本科阶段):** 转变思路，从“实现完整系统”转变为“**构建并验证系统的核心最小闭环**”。我们的目标不是立刻造出F1赛车，而是要亲手打造出那台能工作的、可迭代的“发动机”。

- **核心最小闭环 (Minimum Viable Loop):**

    1. AI模型生成 Chisel 代码。

    2. 一个“反射环境”自动执行该代码。

    3. “反射环境”将错误或结果反馈给AI。

    4. AI根据反馈，尝试“自我修复”。

本报告将围绕这个“最小闭环”，为你规划出三个清晰、可执行的研究阶段。

## 二、 [第一阶段] 搭建“反射环境”：奠定工程基石 (The Reflection Environment)

**这是整个研究的基石，也是最考验你工程能力的部分。**

- **目标:** 创建一个“Chisel即服务”(Chisel-as-a-Service)的自动化工具。它是一个黑盒，你给它Chisel代码，它还你一份“体检报告”。

- **一步一步走 (Key Tasks):**

    1. **技术栈选型:**

        - **推荐:** 使用 **Python** 作为“胶水语言”。

        - **原因:** Python的 `subprocess` 库非常适合调用和管理外部命令行工具（如 `scalac`, `sbt`, `verilator`），并且未来与LLM的Pytorch/Transformers生态无缝衔接。

    2. **创建“反射”主函数:**

        - 设计一个 Python 函数，例如 `result = reflect(chisel_code_string: str)`。

        - 这个函数将是后续所有自动化的入口。

    3. **自动化第1环：Scala编译 (Compilation)**

        - `reflect` 函数内部调用 `subprocess` 来执行 `scalac YourTempModule.scala`。

        - **关键:** 必须捕获 `stdout` (标准输出) 和 `stderr` (标准错误)。

        - 如果 `stderr` 不为空，说明**编译失败**。立刻将错误日志和 `{"compiled": false}` 存入 `result` 并返回。

    4. **自动化第2环：Chisel阐述 (Elaboration)**

        - 如果编译成功，函数继续调用 `sbt run` (或等效命令) 来执行Scala代码，使其“阐述”为 FIRRTL 和最终的 Verilog。

        - **关键:** 这是Chisel的运行时。它可能会抛出Chisel特有的错误（如“位宽不匹配”）。同样要捕获 `stderr`。

        - 如果出错，返回 `{"compiled": true, "elaborated": false, "error_log": "Chisel error: width mismatch..."}`。

    5. **自动化第3环：功能仿真 (Simulation)**

        - 如果阐述成功（你得到了 `.v` 文件），函数继续调用仿真器（推荐使用开源的 **Verilator**）。

        - 你需要为你的目标（例如：一个4位加法器）**预先写好一个 C++ testbench** (`tb_adder.cpp`)。

        - `reflect` 函数自动调用 Verilator 编译 Verilog 和 C++ testbench，并执行它。

        - **关键:** 捕获 testbench 的输出（例如，它应该打印 "TEST PASSED"）。

        - 如果仿真失败，返回 `{"compiled": true, "elaborated": true, "sim_passed": false}`。

    6. **定义标准“体检报告” (Result Object):**

        - `reflect` 函数的最终返回值应该是一个结构化对象 (JSON / Python Dict)，例如：

            ```
            {
              "compiled": true,
              "elaborated": true,
              "sim_passed": true,
              "error_log": null,
              "generated_verilog": "[...Verilog code...]"
            }
            ```

- **第一阶段可交付成果 (Deliverable):**

  - 一个（或一组）`.py` 脚本。当你运行 `python run_reflect.py --file my_buggy_adder.scala` 时，它能准确地告诉你这个文件死在了哪一步以及错误信息是什么。

## 三、 [第二阶段] 攻克“奖励稀疏性”：SFT与数据工程 (Attacking Reward Sparsity)

**“奖励稀疏性”是原计划最大的风险。** 如果LLM生成的代码100%编译不通过，它就永远学不会修复。我们必须解决这个问题。

- **目标:** 训练一个基础的SFT（监督微调）模型，它生成的Chisel代码**“编译通过率”必须显著高于0%**。

- **核心策略:** **“合成” (Synthesize) 数据集, 而非“爬取” (Scrape)。**

- **一步一步走 (Key Tasks):**

    1. **构建“Chisel课程生成器”:**

        - 编写一个Python脚本（使用模板，如 Jinja2），用程序化的方式生成（自然语言描述, Chisel代码）配对。

    2. **实施“课程学习” (Curriculum Learning):**

        - **级别 1 (语法基础):** 生成 10,000+ 个**语法绝对正确**的 Chisel **代码片段**。

            - _例子 (prompt):_ "用Chisel定义一个8位的无符号wire，名为'a'"

            - _例子 (code):_ `val a = Wire(UInt(8.W))`

        - **级别 2 (简单模块):** 生成 1,000+ 个**能完整编译**的 Chisel **模块**。

            - _例子 (prompt):_ "写一个2选1的多路选择器，数据宽度为4位"

            - _例子 (code):_

                ```
                import chisel3._
                import chisel3.util._
                class Mux2to1 extends Module {
                  val io = IO(new Bundle {
                    val a = Input(UInt(4.W))
                    val b = Input(UInt(4.W))
                    val sel = Input(Bool())
                    val y = Output(UInt(4.W))
                  })
                  io.y := Mux(io.sel, io.b, io.a)
                }
                ```

    3. **模型微调 (SFT):**

        - 选择一个基础模型（例如 CodeLlama 7B 或 13B）。

        - 使用你生成的“课程”数据集对它进行SFT微调。

- **第二阶段可交付成果 (Deliverable):**

  - 1. 你的“Chisel课程生成器”脚本。

  - 2. 一个SFT微调后的模型权重。

- **关键验证:**

  - 让你的新模型生成 100 个“2选1 Mux”。

  - 把这 100 个结果丢进**[第一阶段]**的 `reflect()` 函数中。

  - **测量“编译通过率”**。如果它从 0% 提升到了 10%，你就取得了巨大的成功。

## 四、 [第三阶段] 搭建“最小闭环”：验证自我修复 (The Minimum Viable Loop)

**这是前两个阶段的集大成，也是你研究的“高光时刻”。**

- **目标:** 演示你的AI模型如何利用[第一阶段]的**错误反馈**，来**“自我修复”**它的代码。

- **一步一步走 (Key Tasks):**

    1. **编写“智能体”脚本 (`agent.py`):**

        - 这个脚本是你的“总控”。

    2. **实现“首次尝试” (Attempt 1):**

        - `agent.py` 接收一个自然语言任务，例如: `"写一个有BUG的4位加法器"`。

        - 它将这个 prompt 喂给**[第二阶段]**的SFT模型，生成 `code_v1`。

    3. **实现“首次反思” (Reflection 1):**

        - `agent.py` 调用**[第一阶段]**的 `reflect(code_v1)`。

        - 它拿到了 `result_v1`，发现 `{"compiled": false, "error_log": "val b is not a member of Bundle..."}`。

    4. **实现“反馈-修复”循环 (Feedback-Repair Loop):**

        - `agent.py` **动态构建一个新的 Prompt**:

            ```
            你上次生成的代码有错误:
            [code_v1 的完整代码]
            
            编译器反馈的错误是:
            "val b is not a member of Bundle..."
            
            请你仔细阅读错误，并修复这段代码。
            ```

        - `agent.py` 将这个**新的、包含错误信息的 Prompt** 再次喂给SFT模型，生成 `code_v2`。

    5. **实现“迭代终止”:**

        - `agent.py` 再次调用 `reflect(code_v2)`。

        - 循环这个过程（最多 N 次，例如 5 次），直到 `result.sim_passed == true` 或达到最大尝试次数。

- **第三阶段可交付成果 (Deliverable):**

  - 一个 `agent.py` 脚本，或者一个 Jupyter Notebook。

  - 当你运行它时，你可以在终端清晰地看到：

    - `Attempt 1: Compiling... FAILED!`

    - `Feedback: "error: not found: value Mux"`

    - `Attempt 2: Generating fix... Compiling... SUCCESS!`

    - `Attempt 2: Elaborating... FAILED!`

    - `Feedback: "Chisel error: width mismatch"`

    - `Attempt 3: Generating fix... Compiling... SUCCESS! Elaborating... SUCCESS! Simulating... PASSED!`

    - `Task Complete.`

## 五、 总结与展望

这份“三步走”的蓝图，将你最初那个宏大的博士级愿景，转化为了一个大二学生**完全可以动手实现**的、极具挑战和趣味的工程项目。

- **第一阶段** 锻炼你对EDA工具链的“掌控力”。

- **第二阶段** 锻炼你对LLM“数据工程”的理解。

- **第三阶段** 则将两者结合，创造出一个真正的“智能”原型。

完成这个蓝图，你将获得一套在当今AI和硬件交叉领域**极其稀缺**的技能。这将是你本科阶段最亮眼的研究成果，无论对你未来继续深造（例如，真正开始研究PPO和PPA优化）还是进入工业界，都将是无价的财富。

祝你好运。
