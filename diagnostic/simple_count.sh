#!/bin/bash

# 简单的删除标记统计脚本
BUCKET="$1"

if [[ -z "$BUCKET" ]]; then
    echo "用法: $0 BUCKET_NAME"
    exit 1
fi

echo "正在统计 $BUCKET 的删除标记..."

# 直接使用AWS CLI查询
echo "方法1: 使用query参数统计删除标记"
DELETE_MARKERS=$(aws s3api list-object-versions --bucket "$BUCKET" --query 'length(DeleteMarkers[])' --output text 2>/dev/null || echo "0")
echo "删除标记总数: $DELETE_MARKERS"

echo
echo "方法2: 使用query参数统计IsLatest=true的删除标记"
LATEST_DELETE_MARKERS=$(aws s3api list-object-versions --bucket "$BUCKET" --query 'length(DeleteMarkers[?IsLatest==`true`])' --output text 2>/dev/null || echo "0")
echo "当前删除标记数: $LATEST_DELETE_MARKERS"

echo
echo "方法3: 统计版本信息"
TOTAL_VERSIONS=$(aws s3api list-object-versions --bucket "$BUCKET" --query 'length(Versions[])' --output text 2>/dev/null || echo "0")
CURRENT_VERSIONS=$(aws s3api list-object-versions --bucket "$BUCKET" --query 'length(Versions[?IsLatest==`true`])' --output text 2>/dev/null || echo "0")
echo "总版本数: $TOTAL_VERSIONS"
echo "当前版本数: $CURRENT_VERSIONS"
echo "非当前版本数: $((TOTAL_VERSIONS - CURRENT_VERSIONS))"

echo
echo "方法4: 显示前5个删除标记"
aws s3api list-object-versions --bucket "$BUCKET" --query 'DeleteMarkers[0:5].[Key,LastModified,IsLatest]' --output table 2>/dev/null || echo "无删除标记或查询失败"