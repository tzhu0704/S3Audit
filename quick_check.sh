#!/bin/bash
#
# S3 数据丢失快速检查脚本
# 快速检查 S3 bucket 的关键指标
#

set -e

# 颜色定义
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查参数
if [ $# -eq 0 ]; then
    echo "用法: $0 <bucket-name> [region]"
    echo "示例: $0 veeam-backup-bucket us-east-1"
    exit 1
fi

BUCKET=$1
REGION=${2:-us-east-1}

echo "========================================"
echo "S3 Bucket 快速检查"
echo "========================================"
echo "Bucket: $BUCKET"
echo "Region: $REGION"
echo "时间: $(date)"
echo ""

# 1. CloudWatch 指标
echo -e "${BLUE}[1/5] 检查 CloudWatch 指标...${NC}"
echo ""

# macOS 和 Linux 兼容的日期计算
if date -v-7d > /dev/null 2>&1; then
    # macOS
    START_TIME=$(date -u -v-7d +%Y-%m-%dT%H:%M:%S)
    END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)
else
    # Linux
    START_TIME=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
    END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)
fi

echo "过去 7 天存储量变化:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name BucketSizeBytes \
  --dimensions Name=BucketName,Value=$BUCKET Name=StorageType,Value=StandardStorage \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --period 86400 \
  --statistics Average \
  --region $REGION \
  --query 'Datapoints | sort_by(@, &Timestamp)' \
  --output json | jq -r '.[] | "\(.Timestamp | split("T")[0])  \((.Average / 1024 / 1024 / 1024) | floor) GB"'

echo ""
echo "过去 7 天对象数量变化:"
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name NumberOfObjects \
  --dimensions Name=BucketName,Value=$BUCKET Name=StorageType,Value=AllStorageTypes \
  --start-time $START_TIME \
  --end-time $END_TIME \
  --period 86400 \
  --statistics Average \
  --region $REGION \
  --query 'Datapoints | sort_by(@, &Timestamp)' \
  --output json | jq -r '.[] | "\(.Timestamp | split("T")[0])  \(.Average | floor) 个对象"'

echo ""

# 2. 版本控制
echo -e "${BLUE}[2/5] 检查版本控制...${NC}"
VERSIONING=$(aws s3api get-bucket-versioning --bucket $BUCKET --region $REGION --output json 2>/dev/null || echo '{}')
STATUS=$(echo $VERSIONING | jq -r '.Status // "Disabled"')

if [ "$STATUS" == "Enabled" ]; then
    echo -e "${GREEN}✓ 版本控制已启用${NC}"
    
    # 检查删除标记
    DELETE_MARKERS=$(aws s3api list-object-versions \
      --bucket $BUCKET \
      --region $REGION \
      --max-items 1000 \
      --query 'length(DeleteMarkers[?IsLatest==`true`])' \
      --output text 2>/dev/null || echo "0")
    
    if [ "$DELETE_MARKERS" -gt 0 ]; then
        echo -e "${YELLOW}⚠ 发现 $DELETE_MARKERS 个删除标记 (可恢复)${NC}"
    else
        echo "  未发现删除标记"
    fi
else
    echo -e "${YELLOW}⚠ 版本控制未启用${NC}"
fi

echo ""

# 3. 生命周期策略
echo -e "${BLUE}[3/5] 检查生命周期策略...${NC}"
LIFECYCLE=$(aws s3api get-bucket-lifecycle-configuration --bucket $BUCKET --region $REGION 2>/dev/null || echo "")

if [ -n "$LIFECYCLE" ]; then
    RULE_COUNT=$(echo $LIFECYCLE | jq '.Rules | length')
    echo -e "${YELLOW}⚠ 发现 $RULE_COUNT 条生命周期规则${NC}"
    echo $LIFECYCLE | jq -r '.Rules[] | "  ID: \(.ID)\n  状态: \(.Status)\n  过期: \(.Expiration // "无")\n"'
else
    echo -e "${GREEN}✓ 未配置生命周期策略${NC}"
fi

echo ""

# 4. CloudTrail 事件
echo -e "${BLUE}[4/5] 检查 CloudTrail 事件 (最近 7 天)...${NC}"

LIFECYCLE_EVENTS=$(aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=$BUCKET \
  --start-time $START_TIME \
  --region $REGION \
  --query 'Events[?EventName==`PutBucketLifecycleConfiguration` || EventName==`DeleteBucketLifecycle`].[EventTime,EventName,Username]' \
  --output text 2>/dev/null || echo "")

if [ -n "$LIFECYCLE_EVENTS" ]; then
    echo -e "${YELLOW}⚠ 发现生命周期策略变更:${NC}"
    echo "$LIFECYCLE_EVENTS"
else
    echo "  未发现生命周期策略变更"
fi

echo ""

# 5. 当前状态
echo -e "${BLUE}[5/5] 统计当前对象...${NC}"
OBJECT_COUNT=$(aws s3 ls s3://$BUCKET --recursive --region $REGION | wc -l)
echo "  当前对象数: $OBJECT_COUNT"

echo ""
echo "========================================"
echo "检查完成"
echo "========================================"
echo ""
echo "建议:"
echo "  1. 如果发现存储量或对象数量显著下降,运行完整分析:"
echo "     python s3_deletion_analyzer.py --bucket $BUCKET --region $REGION"
echo ""
echo "  2. 如果发现生命周期策略,检查是否符合预期:"
echo "     aws s3api get-bucket-lifecycle-configuration --bucket $BUCKET"
echo ""
echo "  3. 如果版本控制未启用,建议启用:"
echo "     aws s3api put-bucket-versioning --bucket $BUCKET --versioning-configuration Status=Enabled"
echo ""
