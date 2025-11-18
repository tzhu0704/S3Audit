#!/bin/bash
# 快速启动脚本

echo "🚀 启动 S3 访问日志分析应用..."
echo ""

# 检查依赖
if ! command -v streamlit &> /dev/null; then
    echo "⚠️  未安装 streamlit，正在安装依赖..."
    pip install -r requirements.txt
fi

# 启动应用
streamlit run s3_log_analyzer.py
