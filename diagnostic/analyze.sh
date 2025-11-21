#!/bin/bash

# S3 数据丢失分析工具 - 快捷脚本
# 用法: ./analyze.sh <bucket-name> [options]

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}S3 数据丢失分析工具${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "用法:"
    echo "  ./analyze.sh <bucket-name> [options]"
    echo ""
    echo "必需参数:"
    echo "  bucket-name          要分析的 S3 bucket 名称"
    echo ""
    echo "可选参数:"
    echo "  --region REGION      AWS 区域 (默认: us-east-1)"
    echo "  --skip-listing       跳过对象列表统计 (加快分析速度)"
    echo "  --background, -b     后台运行"
    echo "  -h, --help           显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  ${YELLOW}# 基本用法${NC}"
    echo "  ./analyze.sh my-bucket"
    echo ""
    echo "  ${YELLOW}# 后台运行${NC}"
    echo "  ./analyze.sh my-bucket --background"
    echo ""
    echo "  ${YELLOW}# 指定区域${NC}"
    echo "  ./analyze.sh my-bucket --region ap-southeast-1"
    echo ""
    echo "  ${YELLOW}# 跳过对象列表 (大型 bucket 推荐)${NC}"
    echo "  ./analyze.sh my-bucket --skip-listing"
    echo ""
    echo "  ${YELLOW}# 组合使用${NC}"
    echo "  ./analyze.sh my-bucket --region us-west-2 --skip-listing --background"
    echo ""
    echo "输出:"
    echo "  - 报告保存在 logs/ 目录"
    echo "  - 生成 Markdown 和 JSON 两种格式"
    echo "  - 后台运行时日志保存在 logs/analyze_<bucket>.log"
    echo ""
}

# 检查参数
if [ $# -eq 0 ] || [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    show_help
    exit 0
fi

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    echo "请先安装 Python 3"
    exit 1
fi

# 检查脚本是否存在
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANALYZER_SCRIPT="$SCRIPT_DIR/s3_deletion_analyzer.py"

if [ ! -f "$ANALYZER_SCRIPT" ]; then
    echo -e "${RED}错误: 未找到 s3_deletion_analyzer.py${NC}"
    echo "请确保脚本在 diagnostic/ 目录中"
    exit 1
fi

# 检查是否后台运行
BACKGROUND=false
BUCKET_NAME=""
ARGS=()

for arg in "$@"; do
    if [ "$arg" == "--background" ] || [ "$arg" == "-b" ]; then
        BACKGROUND=true
    elif [ -z "$BUCKET_NAME" ] && [[ ! "$arg" =~ ^-- ]]; then
        BUCKET_NAME="$arg"
        ARGS+=("--bucket" "$arg")
    else
        ARGS+=("$arg")
    fi
done

# 执行分析
if [ "$BACKGROUND" = true ]; then
    LOG_FILE="$SCRIPT_DIR/logs/analyze_${BUCKET_NAME}.log"
    mkdir -p "$SCRIPT_DIR/logs"
    
    echo -e "${GREEN}后台运行分析任务...${NC}"
    echo -e "日志文件: ${BLUE}$LOG_FILE${NC}"
    echo -e "查看进度: ${YELLOW}tail -f $LOG_FILE${NC}"
    
    nohup python3 "$ANALYZER_SCRIPT" "${ARGS[@]}" > "$LOG_FILE" 2>&1 &
    PID=$!
    echo -e "进程 ID: ${BLUE}$PID${NC}"
    echo $PID > "$SCRIPT_DIR/logs/analyze_${BUCKET_NAME}.pid"
    
    echo ""
    echo -e "${GREEN}✓ 任务已在后台启动${NC}"
else
    echo -e "${GREEN}开始分析 S3 bucket...${NC}"
    echo ""
    
    python3 "$ANALYZER_SCRIPT" "${ARGS[@]}"
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✓ 分析完成!${NC}"
        echo -e "报告保存在: ${BLUE}$SCRIPT_DIR/logs/${NC}"
    else
        echo ""
        echo -e "${RED}✗ 分析失败 (退出码: $EXIT_CODE)${NC}"
    fi
    
    exit $EXIT_CODE
fi
