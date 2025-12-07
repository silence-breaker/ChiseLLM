import streamlit as st
# 注意：这里我们引入新的 Agent 类 (参数变了)
from src.agent import ChiselAgent

st.set_page_config(page_title="ChiseLLM Workstation", layout="wide", page_icon="⚡")

st.title("⚡ ChiseLLM 智能工作台 (Google Native 版)")
st.caption("Powered by Google Gemini 1.5 Flash & Chisel 6")

# --- 侧边栏 ---
with st.sidebar:
    st.header("🔧 配置")
    
    # 只需要 API Key
    api_key = st.text_input("Google API Key", type="password", help="输入以 AIza 开头的密钥")
    

# 修改 app.py - 使用你账号里真实存在的模型 ID
    model_name = st.selectbox(
        "选择模型", 
        [
            "gemini-flash-latest",     # ✅ 你的列表里有这个！用它！
            "gemini-pro-latest",       # ✅ 你的列表里也有这个作为保底
            "gemini-2.0-flash-exp",    # ⚠️ 实验版，如果 2.0-flash 没额度，可以试试带 exp 后缀的这个
        ],
        index=0
    )
    
    st.divider()
    st.success("✅ 已切换至 Google 原生接口，速度更快且稳定。")

# --- Session 初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

# --- 主界面 ---
col_chat, col_code = st.columns([1, 1])

with col_chat:
    st.subheader("💬 需求对话")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("请输入设计需求 (例如：写一个带同步复位的8位寄存器)"):
        if not api_key:
            st.error("请先在左侧输入 Google API Key！")
            st.stop()
            
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            status_box = st.status("🚀 Gemini 启动中...", expanded=True)
            
            # ⚠️ 注意：这里不再需要 base_url
            agent = ChiselAgent(api_key=api_key, model_name=model_name)
            
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
                    status_box.update(label="💀 任务失败", state="error")
                    st.error(step["msg"])
                    st.stop()
            
            st.markdown(response_content)
            st.session_state.messages.append({"role": "assistant", "content": response_content})
            st.rerun()

# --- 右侧代码区 (保持不变) ---
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
                st.download_button("⬇️ 下载 Verilog", result["generated_verilog"], file_name=f"{result['module_name']}.v")
            else:
                st.info("未生成 Verilog")
        with tab3:
            st.json(result)
            if result['elaborated']:
                st.success("Elaboration Passed")
            else:
                st.error("Elaboration Failed")
    else:
        st.info("👈 请在左侧输入需求")