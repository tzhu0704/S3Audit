#!/bin/bash
# 测试 S3 删除告警系统

BUCKET="${1:-datasync-dest1}"

echo "============================================================"
echo "🧪 S3 删除告警系统测试"
echo "============================================================"
echo ""
echo "📦 Bucket: $BUCKET"
echo "⏰ 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 创建测试文件
TEST_FILE="alert-test-$(date +%s).txt"
echo "test at $(date)" | aws s3 cp - "s3://$BUCKET/$TEST_FILE"
echo "✅ 文件已创建: s3://$BUCKET/$TEST_FILE"

sleep 2

# 删除文件
aws s3 rm "s3://$BUCKET/$TEST_FILE"
echo "🗑️  文件已删除 at $(date '+%H:%M:%S')"

echo ""
echo "============================================================"
echo "📧 预期告警"
echo "============================================================"
echo ""
echo "⚡ 实时告警 (< 1 分钟):"
echo "   主题: ⚡[实时告警]$BUCKET"
echo "   内容: S3 Event JSON"
echo ""
echo "🔍 审计告警 (15-30 分钟):"
echo "   内容: 🔍 [CloudTrail审计] S3删除告警"
echo "   包含: 用户、IP、请求ID"
echo ""
echo "💡 提示: 通过邮件主题和内容可以快速区分两种告警"
echo ""
