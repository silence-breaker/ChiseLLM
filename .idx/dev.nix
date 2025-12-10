# .idx/dev.nix
{ pkgs, ... }: {
  # 使用稳定通道
  channel = "stable-23.11"; 

  # 1. 系统级软件
  # .idx/dev.nix 的 packages 部分
    packages = [
      pkgs.python3
      pkgs.python3Packages.pip
      pkgs.python3Packages.virtualenv
      pkgs.jdk17
      pkgs.mill
      pkgs.verilator
      pkgs.gnumake
      pkgs.gcc
      pkgs.python311Packages.pyngrok
      # 👇👇👇 核心修复：添加 CIRCT 工具链 (包含 firtool)
      pkgs.circt 
    ];

  # 2. 环境变量
  env = {};

  idx = {
    extensions = [
      "ms-python.python"
      "scalameta.metals" 
    ];

    # 3. 预览配置 (修复了路径找不到的问题)
    previews = {
      enable = true;
      previews = {
        web = {
          # 核心修复：直接调用虚拟环境里的 Python 来运行 Streamlit
          command = [
            "./.venv/bin/python" 
            "-m" 
            "streamlit" 
            "run" 
            "app.py" 
            "--server.port" "$PORT"
            "--server.address" "0.0.0.0" 
            "--server.enableCORS" "false"
          ];
          manager = "web";
          env = {
            # 确保环境变量也指向虚拟环境
            PORT = "$PORT";
          };
        };
      };
    };

    workspace = {
      # 4. 生命周期钩子：自动创建环境并安装依赖
      onCreate = {
        setup-venv = ''
          python3 -m venv .venv && \
          source .venv/bin/activate && \
          pip install --upgrade pip && \
          pip install -r requirements.txt && \
          pip install streamlit openai
        '';
      };
      # 每次启动时，确保一下依赖（可选，防止环境损坏）
      onStart = {
        check-env = "verilator --version";
      };
    };
  };
}