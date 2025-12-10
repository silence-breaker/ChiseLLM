"""
ChiseLLM 智能工作台 - 支持多 API Provider

支持的 API:
- Google Gemini
- OpenAI (GPT-4o, GPT-4 Turbo 等)
- Qwen (通义千问)
- DeepSeek
- Anthropic Claude
- 自定义 OpenAI 兼容 API
"""

import streamlit as st
from src.agent import ChiselAgent
from src.llm_provider import PROVIDER_CONFIGS

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="ChiseLLM Workstation", 
    layout="wide", 
    page_icon="⚡"
)

st.title("⚡ ChiseLLM 智能工作台")
st.caption("AI 驱动的 Chisel 硬件设计生成与验证平台")

# ==================== 侧边栏配置 ====================
with st.sidebar:
    st.header("🔧 API 配置")
    
    # 检查是否有默认配置
    has_default = hasattr(st, 'secrets') and 'default' in st.secrets
    
    # 使用默认配置的开关
    use_default = st.checkbox(
        "🚀 使用测试配置", 
        value=has_default,
        help="勾选后自动填充测试用的 API 配置",
        disabled=not has_default
    )
    
    # Provider 选择
    provider_options = {
        "siliconflow": "🔮 SiliconFlow (测试推荐)",
        "gemini": "🌟 Google Gemini",
        "openai": "🟢 OpenAI (GPT)",
        "qwen": "🔮 Qwen (通义千问)",
        "deepseek": "🔷 DeepSeek",
        "claude": "🟣 Anthropic Claude",
        "custom": "⚙️ 自定义 OpenAI 兼容"
    }
    
    # 默认选择 siliconflow
    default_provider = "siliconflow" if use_default else "gemini"
    provider_type = st.selectbox(
        "选择 API 类型",
        options=list(provider_options.keys()),
        format_func=lambda x: provider_options[x],
        index=list(provider_options.keys()).index(default_provider)
    )
    
    # API Key 输入 - 只有使用测试配置 + SiliconFlow 时才隐藏
    if use_default and has_default and provider_type == "siliconflow":
        api_key = st.secrets["default"]["api_key"]
        st.text_input(
            "API Key", 
            value="••••••••••••••••••••",
            type="password",
            disabled=True,
            help="使用测试配置中的 API Key"
        )
    else:
        api_key = st.text_input(
            "API Key", 
            type="password", 
            help="输入对应平台的 API Key"
        )
    
    # 获取当前 Provider 配置
    provider_config = PROVIDER_CONFIGS.get(provider_type, {})
    
    # 保存原始 provider_type 用于显示
    display_provider_type = provider_type
    
    # Base URL 和模型配置
    base_url = None
    if provider_type == "siliconflow":
        # SiliconFlow 特殊配置
        if use_default and has_default:
            base_url = st.secrets["default"]["base_url"]
            model_name = st.secrets["default"]["model_name"]
            st.text_input("API Base URL", value=base_url, disabled=True)
            st.text_input("模型名称", value=model_name, disabled=True)
        else:
            base_url = st.text_input(
                "API Base URL",
                value="https://api.siliconflow.cn/v1",
                help="SiliconFlow API 地址"
            )
            model_name = st.text_input(
                "模型名称",
                value="deepseek-ai/DeepSeek-V3",
                help="SiliconFlow 支持的模型"
            )
        # 实际使用 custom 类型处理
        provider_type = "custom"
    elif provider_type == "custom":
        base_url = st.text_input(
            "API Base URL",
            value="https://api.openai.com/v1",
            help="OpenAI 兼容 API 的 Base URL"
        )
        custom_model = st.text_input(
            "模型名称",
            value="gpt-3.5-turbo",
            help="自定义模型名称"
        )
        model_name = custom_model
    else:
        # 模型选择 (根据 Provider 动态更新)
        models = provider_config.get("models", [])
        default_model = provider_config.get("default_model", "")
        
        if models:
            model_name = st.selectbox(
                "选择模型",
                options=models,
                index=models.index(default_model) if default_model in models else 0
            )
        else:
            model_name = st.text_input("模型名称", value=default_model)
    
    st.divider()
    
    # 显示当前配置状态
    if api_key:
        st.success(f"✅ 已配置 {provider_options[display_provider_type]}")
    else:
        st.warning("⚠️ 请输入 API Key")
    
    # 帮助信息
    with st.expander("📘 API 获取指南"):
        st.markdown("""
        **Google Gemini**: [Google AI Studio](https://aistudio.google.com/)
        
        **OpenAI**: [OpenAI Platform](https://platform.openai.com/)
        
        **Qwen**: [阿里云 DashScope](https://dashscope.console.aliyun.com/)
        
        **DeepSeek**: [DeepSeek Platform](https://platform.deepseek.com/)
        
        **Claude**: [Anthropic Console](https://console.anthropic.com/)
        """)

# ==================== Session 初始化 ====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_code" not in st.session_state:
    st.session_state.last_code = None

# ==================== 主界面 ====================
col_chat, col_code = st.columns([1, 1])

# --- 左侧对话区 ---
with col_chat:
    st.subheader("💬 需求对话")
    
    # 显示历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 用户输入
    if prompt := st.chat_input("请输入设计需求 (例如：写一个带同步复位的8位寄存器)"):
        if not api_key:
            st.error("请先在左侧输入 API Key！")
            st.stop()
            
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            status_box = st.status("🚀 启动中...", expanded=True)
            
            # 使用工厂方法创建 Agent
            try:
                agent = ChiselAgent.from_config(
                    provider_type=provider_type,
                    api_key=api_key,
                    model_name=model_name,
                    base_url=base_url
                )
            except Exception as e:
                st.error(f"创建 Agent 失败: {str(e)}")
                st.stop()
            
            response_content = ""
            
            for step in agent.run_loop(prompt):
                if step["status"] == "generating":
                    status_box.write(f"✍️ {step['msg']}")
                elif step["status"] == "reflecting":
                    status_box.write(f"🔨 {step['msg']}")
                elif step["status"] == "fixing":
                    status_box.write(f"🚑 {step['msg']}")
                elif step["status"] == "error":
                    status_box.update(label="❌ 发生错误", state="error")
                    st.error(step["msg"])
                    st.stop()
                elif step["status"] == "success":
                    status_box.update(label="✅ 生成成功！", state="complete", expanded=False)
                    response_content = step["raw_response"]
                    st.session_state.last_result = step["result"]
                    st.session_state.last_code = step["code"]
                elif step["status"] == "failed":
                    status_box.update(label="💀 任务失败，已显示最后一次错误报告", state="error")
                    st.error(step["msg"])
                    
                    # 即使失败，也保存结果
                    if "result" in step:
                        st.session_state.last_result = step["result"]
                        st.session_state.last_code = step["code"]
            
            st.markdown(response_content)
            st.session_state.messages.append({"role": "assistant", "content": response_content})
            st.rerun()

# --- 右侧代码区 ---
with col_code:
    st.subheader("💻 代码工作区")
    
    if st.session_state.get("last_result"):
        result = st.session_state.last_result
        code = st.session_state.last_code
        module_name = result.get("module_name", "Module")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📐 Chisel 源码", 
            "📝 Verilog", 
            "🌊 波形仿真",
            "📊 验证报告",
            "📦 下载中心"
        ])
        
        with tab1:
            st.code(code, language="scala")
        
        with tab2:
            if result.get("generated_verilog"):
                st.code(result["generated_verilog"], language="verilog")
            else:
                st.info("未生成 Verilog (elaboration 失败)")
        
        with tab3:
            # 波形可视化
            if result.get("vcd_content"):
                st.success("✅ 仿真波形已生成")
                
                # 使用 vcd_parser 转换并渲染
                try:
                    import tempfile
                    import streamlit.components.v1 as components
                    from src.vcd_parser import vcd_to_wavedrom, generate_wavedrom_html
                    
                    # 将 VCD 内容写入临时文件
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.vcd', delete=False) as f:
                        f.write(result["vcd_content"])
                        temp_vcd_path = f.name
                    
                    # 转换为 WaveDrom JSON
                    wavedrom_json = vcd_to_wavedrom(temp_vcd_path, max_cycles=50)
                    
                    if "error" not in wavedrom_json:
                        # 生成 HTML 并嵌入
                        html_content = generate_wavedrom_html(wavedrom_json, height=400)
                        components.html(html_content, height=450, scrolling=True)
                    else:
                        st.warning(f"波形解析警告: {wavedrom_json.get('error')}")
                        st.info("显示原始 VCD 文件内容 (前 2000 字符)")
                        st.code(result["vcd_content"][:2000], language="text")
                        
                except Exception as e:
                    st.error(f"波形渲染失败: {str(e)}")
                    st.info("显示原始 VCD 文件")
                    st.code(result["vcd_content"][:2000], language="text")
            else:
                st.info("💡 波形仿真需要提供 Testbench 文件")
                st.markdown("""
                **如何生成波形：**
                1. 准备 C++ Testbench 文件
                2. 在反射验证时指定 testbench 路径
                3. 仿真完成后自动生成 VCD 波形
                """)
        
        with tab4:
            # 验证状态
            if result['elaborated']:
                st.success("✅ Elaboration Passed")
            else:
                st.error("❌ Elaboration Failed")
            
            if result.get('sim_passed') is True:
                st.success("✅ Simulation Passed")
            elif result.get('sim_passed') is False:
                st.error("❌ Simulation Failed")
            
            # 显示详细报告
            with st.expander("📋 详细报告"):
                # 过滤掉过大的字段
                display_result = {k: v for k, v in result.items() 
                                  if k not in ["vcd_content", "full_stdout", "full_stderr"]}
                st.json(display_result)
        
        with tab5:
            # 下载中心
            st.markdown("### 📥 下载中心")
            
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                # Chisel 源码
                st.download_button(
                    "⬇️ Chisel 源码 (.scala)",
                    code,
                    file_name=f"{module_name}.scala",
                    mime="text/plain",
                    use_container_width=True
                )
                
                # Verilog
                if result.get("generated_verilog"):
                    st.download_button(
                        "⬇️ Verilog (.v)",
                        result["generated_verilog"],
                        file_name=f"{module_name}.v",
                        mime="text/plain",
                        use_container_width=True
                    )
            
            with col_dl2:
                # VCD 波形
                if result.get("vcd_content"):
                    st.download_button(
                        "⬇️ 波形文件 (.vcd)",
                        result["vcd_content"],
                        file_name=f"{module_name}.vcd",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                # 项目打包 (Zip)
                if result.get("generated_verilog"):
                    import io
                    import zipfile
                    
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.writestr(f"{module_name}.scala", code)
                        zf.writestr(f"{module_name}.v", result["generated_verilog"])
                        if result.get("vcd_content"):
                            zf.writestr(f"{module_name}.vcd", result["vcd_content"])
                        # 添加 README
                        readme = f"""# {module_name}

Generated by ChiseLLM

## Files
- {module_name}.scala - Chisel source code
- {module_name}.v - Generated Verilog
{"- " + module_name + ".vcd - Simulation waveform" if result.get("vcd_content") else ""}

## Verification Status
- Elaboration: {"✅ Passed" if result['elaborated'] else "❌ Failed"}
"""
                        zf.writestr("README.md", readme)
                    
                    st.download_button(
                        "📦 下载项目包 (.zip)",
                        zip_buffer.getvalue(),
                        file_name=f"{module_name}_project.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    else:
        st.info("👈 请在左侧输入需求")