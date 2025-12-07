# .idx/dev.nix
{ pkgs, ... }: {
  # 使用稳定通道
  channel = "stable-23.11"; 

  # 1. 安装软件包
  packages = [
    pkgs.python3
    pkgs.python3Packages.pip  # pip 包管理
    pkgs.python3Packages.virtualenv # 虚拟环境工具
    pkgs.jdk17        # Scala/Chisel 运行环境
    pkgs.mill         # 构建工具
    pkgs.verilator    # 仿真器
    pkgs.gnumake      # 编译工具
    pkgs.gcc          # C++ 编译器
  ];

  # 2. 环境变量
  env = {};

  idx = {
    extensions = [
      "ms-python.python"
      "scalameta.metals" 
    ];

    # 3. ⚠️ 关键修复：添加网页预览配置
    previews = {
      enable = true;
      previews = {
        web = {
          # IDX 会自动把 $PORT 替换为它分配的端口
          command = [
            "streamlit" 
            "run" 
            "app.py" 
            "--server.port" "$PORT"
            "--server.address" "0.0.0.0" 
            "--server.enableCORS" "false"
          ];
          manager = "web";
        };
      };
    };

    workspace = {
      onCreate = {
        # 首次创建时自动安装依赖
        install-deps = "python3 -m pip install -r requirements.txt && python3 -m pip install streamlit openai";
      };
    };
  };
}