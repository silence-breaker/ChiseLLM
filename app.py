import streamlit as st
import time
from src.agent import ChiselAgent

# 页面配置
st.set_page_config(page_title="ChiseLLM Workstation", layout="wide", page_icon="⚡")

st.title("⚡ ChiseLLM 智能工作台")
st.caption("Auto-generating & Verifying Chisel Hardware Designs")

# --- 侧边栏：配置区 ---
with st.sidebar:
    st.header("🔧 模型配置")
    
    # 默认值是为了方便演示，你可以替换成你自己的 Key
    api_key = st.text_input("API Key", type="password", help="输入 OpenAI 或 DeepSeek 的 API Key")
    base_url = st.text_input("Base URL", value="https://api.deepseek.com", help="例如 https://api.deepseek.com")
    model_name = st.selectbox("选择模型", ["deepseek-coder", "gpt-4o", "gpt-3.5-turbo"])
    
    st.divider()
    st.info("💡 提示：本环境已集成 Scala 2.13 + Chisel 6 + Verilator。")

# --- 初始化 Session ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# --- 主界面：左侧对话，右侧结果 ---
col_chat, col_code = st.columns([1, 1])

with col_chat:
    st.subheader("💬 需求对话")
    
    # 渲染历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 处理用户输入
    if prompt := st.chat_input("请输入设计需求 (例如：写一个带使能端的4位计数器)"):
        if not api_key:
            st.error("请先在左侧侧边栏输入 API Key！")
            st.stop()
            
        # 显示用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 运行 Agent
        with st.chat_message("assistant"):
            status_box = st.status("🚀 Agent 启动中...", expanded=True)
            agent = ChiselAgent(api_key, base_url, model_name)
            
            response_content = ""
            
            # 流式获取 Agent 的步骤更新
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
                    status_box.update(label="✅ 生成成功！编译通过！", state="complete", expanded=False)
                    response_content = step["raw_response"]
                    st.session_state.last_result = step["result"]
                    st.session_state.last_code = step["code"]
                elif step["status"] == "failed":
                    status_box.update(label="💀 任务失败", state="error")
                    st.error(step["msg"])
                    st.stop()
            
            # 显示最终回答
            st.markdown(response_content)
            st.session_state.messages.append({"role": "assistant", "content": response_content})
            st.rerun() # 强制刷新以更新右侧代码区

# --- 右侧：代码与验证结果 ---
with col_code:
    st.subheader("💻 代码工作区")
    
    if st.session_state.get("last_result"):
        result = st.session_state.last_result
        code = st.session_state.last_code
        
        tab1, tab2, tab3 = st.tabs(["📐 Chisel 源码", "📝 生成的 Verilog", "📊 验证报告"])
        
        with tab1:
            st.code(code, language="scala")
            
        with tab2:
            if result.get("generated_verilog"):
                st.code(result["generated_verilog"], language="verilog")
                st.download_button(
                    label="⬇️ 下载 Verilog",
                    data=result["generated_verilog"],
                    file_name=f"{result['module_name']}.v",
                    mime="text/plain"
                )
            else:
                st.info("未生成 Verilog")
                
        with tab3:
            st.json(result)
            if result['elaborated']:
                st.success("Elaboration Passed (Firtool successfully generated Verilog)")
            else:
                st.error("Elaboration Failed")
    else:
        st.info("👈 请在左侧输入需求，生成的代码将显示在这里。")