#!/bin/bash

# S3 删除标记统计脚本
# 使用纯 AWS CLI 统计删除标记数量

set -e

# 默认参数
BUCKET=""
REGION="us-east-1"
MAX_ITEMS=1000000
VERBOSE=false

# 帮助信息
show_help() {
    cat << EOF
S3 删除标记统计脚本

用法: $0 --bucket BUCKET_NAME [选项]

选项:
    --bucket BUCKET_NAME    S3 bucket 名称 (必需)
    --region REGION         AWS 区域 (默认: us-east-1)
    --max-items NUMBER      最大扫描项目数 (默认: 1000000)
    --verbose               显示详细信息
    --help                  显示此帮助信息

示例:
    $0 --bucket tzhu-inventory1
    $0 --bucket tzhu-inventory1 --region us-west-2 --verbose
    $0 --bucket martinrea-alfield-veeam --max-items 500000

EOF
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket)
            BUCKET="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --max-items)
            MAX_ITEMS="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查必需参数
if [[ -z "$BUCKET" ]]; then
    echo "错误: 必须指定 --bucket 参数"
    show_help
    exit 1
fi

# 检查 AWS CLI 是否安装
if ! command -v aws &> /dev/null; then
    echo "错误: 未找到 AWS CLI，请先安装"
    exit 1
fi

# 检查 jq 是否安装
if ! command -v jq &> /dev/null; then
    echo "错误: 未找到 jq，请先安装 (brew install jq 或 apt-get install jq)"
    exit 1
fi

echo "========================================"
echo "S3 删除标记统计"
echo "========================================"
echo "Bucket: $BUCKET"
echo "Region: $REGION"
echo "Max Items: $MAX_ITEMS"
echo "========================================"
echo

# 检查 bucket 是否存在
echo "检查 bucket 是否存在..."
if ! aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
    echo "错误: Bucket '$BUCKET' 不存在或无权限访问"
    exit 1
fi

# 检查版本控制状态
echo "检查版本控制状态..."
VERSIONING=$(aws s3api get-bucket-versioning --bucket "$BUCKET" --region "$REGION" --output json 2>/dev/null || echo '{}')
STATUS=$(echo "$VERSIONING" | jq -r '.Status // "Disabled"')

echo "版本控制状态: $STATUS"

if [[ "$STATUS" != "Enabled" ]]; then
    echo "警告: 版本控制未启用，不会有删除标记"
    echo "删除标记数量: 0"
    exit 0
fi

echo

# 创建临时文件
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

echo "开始扫描删除标记..."
echo "使用分页扫描以提高速度..."
echo

# 初始化计数器
TOTAL_DELETE_MARKERS=0
LATEST_DELETE_MARKERS=0
NON_LATEST_DELETE_MARKERS=0
TOTAL_VERSIONS=0
CURRENT_VERSIONS=0
NONCURRENT_VERSIONS=0
PAGE_COUNT=0
NEXT_KEY_MARKER=""
NEXT_VERSION_ID_MARKER=""

if [[ "$VERBOSE" == "true" ]]; then
    echo "初始化完成，开始分页扫描..."
fi

# 分页扫描
while true; do
    PAGE_COUNT=$((PAGE_COUNT + 1))
    
    # 构建分页参数
    PAGINATION_ARGS=""
    if [[ -n "$NEXT_KEY_MARKER" ]]; then
        PAGINATION_ARGS="--key-marker $NEXT_KEY_MARKER"
    fi
    if [[ -n "$NEXT_VERSION_ID_MARKER" ]]; then
        PAGINATION_ARGS="$PAGINATION_ARGS --version-id-marker $NEXT_VERSION_ID_MARKER"
    fi
    
    # 获取当前页数据
    if [[ "$VERBOSE" == "true" ]]; then
        echo "正在处理第 $PAGE_COUNT 页..."
    else
        # 每10页显示一次进度
        if (( PAGE_COUNT % 10 == 0 )); then
            printf "已处理 %d 页，删除标记: %d，版本: %d\n" "$PAGE_COUNT" "$TOTAL_DELETE_MARKERS" "$TOTAL_VERSIONS"
        fi
    fi
    
    # 执行API调用，每页最多1000项
    aws s3api list-object-versions \
        --bucket "$BUCKET" \
        --region "$REGION" \
        --max-keys 1000 \
        $PAGINATION_ARGS \
        --output json > "$TEMP_FILE"
    
    # 统计当前页的删除标记
    PAGE_DELETE_MARKERS=$(jq '(.DeleteMarkers // []) | length' "$TEMP_FILE" 2>/dev/null || echo "0")
    PAGE_LATEST_DELETE_MARKERS=$(jq '[(.DeleteMarkers // [])[] | select(.IsLatest == true)] | length' "$TEMP_FILE" 2>/dev/null || echo "0")
    PAGE_NON_LATEST_DELETE_MARKERS=$(jq '[(.DeleteMarkers // [])[] | select(.IsLatest == false)] | length' "$TEMP_FILE" 2>/dev/null || echo "0")
    
    # 统计当前页的版本
    PAGE_VERSIONS=$(jq '(.Versions // []) | length' "$TEMP_FILE" 2>/dev/null || echo "0")
    PAGE_CURRENT_VERSIONS=$(jq '[(.Versions // [])[] | select(.IsLatest == true)] | length' "$TEMP_FILE" 2>/dev/null || echo "0")
    PAGE_NONCURRENT_VERSIONS=$(jq '[(.Versions // [])[] | select(.IsLatest == false)] | length' "$TEMP_FILE" 2>/dev/null || echo "0")
    
    # 确保所有变量都是数字
    PAGE_DELETE_MARKERS=${PAGE_DELETE_MARKERS:-0}
    PAGE_LATEST_DELETE_MARKERS=${PAGE_LATEST_DELETE_MARKERS:-0}
    PAGE_NON_LATEST_DELETE_MARKERS=${PAGE_NON_LATEST_DELETE_MARKERS:-0}
    PAGE_VERSIONS=${PAGE_VERSIONS:-0}
    PAGE_CURRENT_VERSIONS=${PAGE_CURRENT_VERSIONS:-0}
    PAGE_NONCURRENT_VERSIONS=${PAGE_NONCURRENT_VERSIONS:-0}
    
    if [[ "$VERBOSE" == "true" ]]; then
        printf "  第%d页: 删除标记=%d, 版本=%d\n" "$PAGE_COUNT" "$PAGE_DELETE_MARKERS" "$PAGE_VERSIONS"
    fi
    
    # 累加计数
    TOTAL_DELETE_MARKERS=$((TOTAL_DELETE_MARKERS + PAGE_DELETE_MARKERS))
    LATEST_DELETE_MARKERS=$((LATEST_DELETE_MARKERS + PAGE_LATEST_DELETE_MARKERS))
    NON_LATEST_DELETE_MARKERS=$((NON_LATEST_DELETE_MARKERS + PAGE_NON_LATEST_DELETE_MARKERS))
    TOTAL_VERSIONS=$((TOTAL_VERSIONS + PAGE_VERSIONS))
    CURRENT_VERSIONS=$((CURRENT_VERSIONS + PAGE_CURRENT_VERSIONS))
    NONCURRENT_VERSIONS=$((NONCURRENT_VERSIONS + PAGE_NONCURRENT_VERSIONS))
    
    # 检查是否还有更多页
    IS_TRUNCATED=$(jq -r '.IsTruncated // false' "$TEMP_FILE")
    if [[ "$IS_TRUNCATED" != "true" ]]; then
        break
    fi
    
    # 获取下一页的标记
    NEXT_KEY_MARKER=$(jq -r '.NextKeyMarker // ""' "$TEMP_FILE")
    NEXT_VERSION_ID_MARKER=$(jq -r '.NextVersionIdMarker // ""' "$TEMP_FILE")
    
    # 如果没有下一页标记，退出
    if [[ -z "$NEXT_KEY_MARKER" ]]; then
        break
    fi
    
    # 防止无限循环，限制最大页数
    if [[ $PAGE_COUNT -ge 1000 ]]; then
        echo "警告: 已达到最大页数限制 (1000页)，停止扫描"
        break
    fi
done

printf "扫描完成！共处理 %d 页\n" "$PAGE_COUNT"

# 统计已在分页循环中完成

# 显示结果
echo "========================================"
echo "统计结果"
echo "========================================"
echo "删除标记统计:"
printf "  总删除标记数量: %d\n" "$TOTAL_DELETE_MARKERS"
printf "  当前删除标记 (IsLatest=true): %d\n" "$LATEST_DELETE_MARKERS"
printf "  历史删除标记 (IsLatest=false): %d\n" "$NON_LATEST_DELETE_MARKERS"
echo
echo "版本统计:"
printf "  总版本数量: %d\n" "$TOTAL_VERSIONS"
printf "  当前版本数量: %d\n" "$CURRENT_VERSIONS"
printf "  非当前版本数量: %d\n" "$NONCURRENT_VERSIONS"
echo
echo "对象统计:"
printf "  当前活跃对象: %d\n" "$CURRENT_VERSIONS"
printf "  被软删除对象: %d\n" "$LATEST_DELETE_MARKERS"
printf "  总对象数 (包括已删除): %d\n" "$((CURRENT_VERSIONS + LATEST_DELETE_MARKERS))"

# 如果有删除标记且启用详细模式，显示详细信息
if [[ "$VERBOSE" == "true" && "$TOTAL_DELETE_MARKERS" -gt 0 ]]; then
    echo
    echo "========================================"
    echo "删除标记详细信息"
    echo "========================================"
    echo "获取删除标记详细信息..."
    
    # 重新获取第一页来显示示例
    aws s3api list-object-versions \
        --bucket "$BUCKET" \
        --region "$REGION" \
        --max-keys 1000 \
        --output json > "$TEMP_FILE"
    
    # 显示前10个删除标记
    DELETE_MARKER_COUNT=$(jq '(.DeleteMarkers // []) | length' "$TEMP_FILE")
    if [[ "$DELETE_MARKER_COUNT" -gt 0 ]]; then
        echo "前10个删除标记示例:"
        jq -r '(.DeleteMarkers // [])[0:10][] | "  \(.Key) | \(.LastModified) | IsLatest=\(.IsLatest) | VersionId=\(.VersionId[0:8])..."' "$TEMP_FILE"
        
        if [[ "$TOTAL_DELETE_MARKERS" -gt 10 ]]; then
            echo "  ... 总共有 $TOTAL_DELETE_MARKERS 个删除标记"
        fi
    fi
fi

# 如果发现删除标记，提供恢复建议
if [[ "$LATEST_DELETE_MARKERS" -gt 0 ]]; then
    echo
    echo "========================================"
    echo "恢复建议"
    echo "========================================"
    echo "发现 $LATEST_DELETE_MARKERS 个可恢复的删除标记"
    echo
    echo "恢复单个对象的命令:"
    # 获取一个删除标记示例
    aws s3api list-object-versions \
        --bucket "$BUCKET" \
        --region "$REGION" \
        --max-keys 10 \
        --output json > "$TEMP_FILE"
    
    SAMPLE_KEY=$(jq -r '(.DeleteMarkers // [])[0].Key // "example-file.txt"' "$TEMP_FILE")
    SAMPLE_VERSION=$(jq -r '(.DeleteMarkers // [])[0].VersionId // "example-version-id"' "$TEMP_FILE")
    echo "  aws s3api delete-object --bucket $BUCKET --key '$SAMPLE_KEY' --version-id $SAMPLE_VERSION"
    echo
    echo "批量恢复所有删除标记的脚本:"
    echo "  # 导出删除标记信息"
    echo "  aws s3api list-object-versions --bucket $BUCKET --query 'DeleteMarkers[?IsLatest==\`true\`].[Key,VersionId]' --output text > delete_markers.txt"
    echo "  # 批量删除删除标记（恢复对象）"
    echo "  while read key version_id; do"
    echo "    aws s3api delete-object --bucket $BUCKET --key \"\$key\" --version-id \"\$version_id\""
    echo "    echo \"恢复对象: \$key\""
    echo "  done < delete_markers.txt"
fi

echo
echo "========================================"
echo "统计完成"
echo "========================================"

# 显示性能信息
if [[ $PAGE_COUNT -ge 1000 ]]; then
    echo
    echo "注意: 扫描在1000页后停止，可能还有更多数据"
    echo "如需完整扫描，请联系管理员优化脚本"
fi