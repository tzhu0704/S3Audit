# S3 实时监控和告警系统

## 🚨 功能概述

这是一个基于 AWS 原生服务的 S3 实时监控和告警系统，支持两种监控方式：
1. **S3 Event Notifications**: 实时监控 S3 对象级事件
2. **CloudTrail + EventBridge**: 监控 bucket 级管理操作

## 🎯 使用场景

- **实时删除告警**: 对象被删除时立即收到通知
- **安全监控**: 检测未授权的访问和操作
- **合规审计**: 记录所有关键操作
- **数据保护**: 防止意外或恶意删除
- **运维监控**: 追踪 bucket 配置变更

## 📋 监控选项对比

| 特性 | S3 Event Notifications | CloudTrail + EventBridge |
|------|----------------------|-------------------------|
| **监控对象** | 对象级操作 | Bucket 级管理操作 |
| **延迟** | 秒级 | 分钟级 |
| **成本** | 免费（Lambda 收费） | CloudTrail 收费 |
| **事件类型** | PUT, POST, COPY, DELETE | 所有 API 调用 |
| **适用场景** | 实时对象监控 | 审计和合规 |

详细对比请参考: [MONITORING_OPTIONS.md](./MONITORING_OPTIONS.md)

## 🚀 快速部署

### 方案 1: S3 Event Notifications（推荐用于实时监控）

#### 1. 部署告警系统

```bash
cd alert/
python setup_realtime_alert.py
```

交互式配置：
```
请输入要监控的 S3 bucket 名称: my-important-bucket
请输入接收告警的邮箱地址: admin@example.com
请输入 Lambda 函数名称 [s3-deletion-alert]: 
请输入 SNS 主题名称 [S3DeletionAlerts]: 
```

#### 2. 确认订阅

检查邮箱，点击 SNS 订阅确认链接。

#### 3. 测试告警

```bash
python test_alerts.sh my-important-bucket
```

或手动测试：
```bash
# 创建测试文件
echo "test" > test-file.txt
aws s3 cp test-file.txt s3://my-important-bucket/

# 删除测试文件（触发告警）
aws s3 rm s3://my-important-bucket/test-file.txt
```

### 方案 2: CloudTrail + EventBridge（推荐用于审计）

#### 1. 部署监控系统

```bash
python setup_deletion_alert.py
```

交互式配置：
```
请输入要监控的 S3 bucket 名称: my-important-bucket
请输入接收告警的邮箱地址: admin@example.com
是否创建新的 CloudTrail? (y/n): y
请输入 CloudTrail 名称 [s3-deletion-trail]: 
```

#### 2. 确认订阅

检查邮箱，点击 SNS 订阅确认链接。

#### 3. 测试告警

```bash
# 测试 bucket 策略删除
aws s3api delete-bucket-policy --bucket my-important-bucket

# 测试生命周期策略修改
aws s3api put-bucket-lifecycle-configuration \
  --bucket my-important-bucket \
  --lifecycle-configuration file://test-lifecycle.json
```

## 📊 告警内容

### S3 Event Notifications 告警

当对象被删除时，您会收到包含以下信息的邮件：

```
🚨 S3 删除告警

Bucket: my-important-bucket
对象: path/to/deleted-file.txt
操作: ObjectRemoved:Delete
时间: 2025-01-18 10:30:45 UTC
请求者: arn:aws:iam::123456789012:user/john
IP 地址: 203.0.113.42
```

### CloudTrail 告警

当 bucket 配置被修改时，您会收到：

```
🚨 S3 Bucket 管理操作告警

事件: DeleteBucketLifecycle
Bucket: my-important-bucket
用户: admin@example.com
时间: 2025-01-18 10:30:45 UTC
源 IP: 203.0.113.42
User Agent: aws-cli/2.x
```

## 🏗️ 架构说明

### 方案 1: S3 Event Notifications

```
┌─────────────┐
│   S3 Bucket │
│   (Source)  │
└──────┬──────┘
       │ Event
       ▼
┌─────────────┐
│   Lambda    │
│  Function   │
└──────┬──────┘
       │ Publish
       ▼
┌─────────────┐
│     SNS     │
│    Topic    │
└──────┬──────┘
       │ Email
       ▼
┌─────────────┐
│    User     │
└─────────────┘
```

**优点**:
- 实时响应（秒级）
- 成本低（无 CloudTrail 费用）
- 配置简单

**缺点**:
- 只能监控对象级操作
- 无法监控 bucket 级配置变更

### 方案 2: CloudTrail + EventBridge

```
┌─────────────┐
│   S3 API    │
│    Calls    │
└──────┬──────┘
       │ Log
       ▼
┌─────────────┐
│ CloudTrail  │
└──────┬──────┘
       │ Event
       ▼
┌─────────────┐
│ EventBridge │
│    Rule     │
└──────┬──────┘
       │ Trigger
       ▼
┌─────────────┐
│     SNS     │
│    Topic    │
└──────┬──────┘
       │ Email
       ▼
┌─────────────┐
│    User     │
└─────────────┘
```

**优点**:
- 完整的审计日志
- 监控所有 API 调用
- 支持复杂的事件过滤

**缺点**:
- 有延迟（1-15分钟）
- CloudTrail 有费用
- 配置相对复杂

## 🔧 高级配置

### 自定义 Lambda 函数

编辑 `monitor_cloudtrail.py` 自定义告警逻辑：

```python
def lambda_handler(event, context):
    # 自定义过滤逻辑
    if should_alert(event):
        send_alert(event)
    
    # 自定义告警格式
    message = format_alert(event)
    
    # 发送到多个目标
    send_to_sns(message)
    send_to_slack(message)
    send_to_pagerduty(message)
```

### 监控多个 Bucket

```bash
# 为每个 bucket 运行部署脚本
for bucket in bucket1 bucket2 bucket3; do
    python setup_realtime_alert.py <<EOF
$bucket
admin@example.com
s3-alert-$bucket
S3Alerts-$bucket
EOF
done
```

### 集成 Slack

修改 Lambda 函数发送到 Slack:

```python
import json
import urllib3

def send_to_slack(message):
    http = urllib3.PoolManager()
    slack_webhook = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    
    slack_message = {
        "text": "🚨 S3 删除告警",
        "attachments": [{
            "color": "danger",
            "fields": [
                {"title": "Bucket", "value": message['bucket'], "short": True},
                {"title": "对象", "value": message['key'], "short": True}
            ]
        }]
    }
    
    http.request(
        'POST',
        slack_webhook,
        body=json.dumps(slack_message),
        headers={'Content-Type': 'application/json'}
    )
```

### 过滤特定路径

只监控特定前缀的删除：

```python
# 在 Lambda 函数中添加
MONITORED_PREFIXES = ['important/', 'critical/', 'backup/']

def should_alert(event):
    key = event['Records'][0]['s3']['object']['key']
    return any(key.startswith(prefix) for prefix in MONITORED_PREFIXES)
```

## 📈 监控和维护

### 查看 Lambda 日志

```bash
aws logs tail /aws/lambda/s3-deletion-alert --follow
```

### 查看 CloudTrail 事件

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceName,AttributeValue=my-bucket \
  --max-results 10
```

### 测试告警系统

使用提供的测试脚本：

```bash
# 测试 S3 Event Notifications
./test_alerts.sh my-bucket

# 测试 CloudTrail 监控
python test_deletion_comprehensive.py
```

### 监控成本

```bash
# 查看 Lambda 调用次数
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=s3-deletion-alert \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-31T23:59:59Z \
  --period 86400 \
  --statistics Sum

# 查看 CloudTrail 成本
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://cloudtrail-filter.json
```

## 🔒 安全最佳实践

### 1. Lambda 函数权限

使用最小权限原则：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:*:*:S3DeletionAlerts"
    }
  ]
}
```

### 2. SNS 主题加密

启用 SNS 主题加密：

```bash
aws sns set-topic-attributes \
  --topic-arn arn:aws:sns:region:account:S3DeletionAlerts \
  --attribute-name KmsMasterKeyId \
  --attribute-value alias/aws/sns
```

### 3. CloudTrail 日志保护

启用日志文件验证：

```bash
aws cloudtrail update-trail \
  --name s3-deletion-trail \
  --enable-log-file-validation
```

### 4. 告警去重

避免告警风暴，实现去重逻辑：

```python
import time
from collections import defaultdict

alert_cache = defaultdict(int)
ALERT_COOLDOWN = 300  # 5分钟

def should_send_alert(key):
    current_time = int(time.time())
    last_alert = alert_cache.get(key, 0)
    
    if current_time - last_alert > ALERT_COOLDOWN:
        alert_cache[key] = current_time
        return True
    return False
```

## 🧪 测试和验证

### 单元测试

```bash
cd alert/
python -m pytest test_alerts.py -v
```

### 集成测试

```bash
# 完整的端到端测试
python test_deletion_comprehensive.py
```

### 性能测试

```bash
# 测试大量删除操作的告警性能
for i in {1..100}; do
    aws s3 rm s3://my-bucket/test-$i.txt &
done
wait
```

## 📚 相关文档

- [S3 Event Notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/NotificationHowTo.html)
- [CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html)
- [EventBridge](https://docs.aws.amazon.com/eventbridge/latest/userguide/what-is-amazon-eventbridge.html)
- [Lambda](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)
- [SNS](https://docs.aws.amazon.com/sns/latest/dg/welcome.html)

## 🆘 故障排除

### 问题: 未收到告警邮件

**检查清单**:
1. ✅ SNS 订阅已确认
2. ✅ Lambda 函数有权限发布到 SNS
3. ✅ S3 事件通知已正确配置
4. ✅ 检查垃圾邮件文件夹

**调试步骤**:
```bash
# 检查 Lambda 日志
aws logs tail /aws/lambda/s3-deletion-alert --follow

# 手动测试 SNS
aws sns publish \
  --topic-arn arn:aws:sns:region:account:S3DeletionAlerts \
  --message "Test message"
```

### 问题: Lambda 函数执行失败

**常见原因**:
- 权限不足
- 超时设置太短
- 内存不足

**解决方案**:
```bash
# 增加超时时间
aws lambda update-function-configuration \
  --function-name s3-deletion-alert \
  --timeout 30

# 增加内存
aws lambda update-function-configuration \
  --function-name s3-deletion-alert \
  --memory-size 256
```

### 问题: CloudTrail 事件延迟

**原因**: CloudTrail 有1-15分钟的延迟

**解决方案**: 
- 对于实时需求，使用 S3 Event Notifications
- 对于审计需求，CloudTrail 延迟是可接受的

## 💡 使用建议

### 选择合适的方案

- **实时保护**: 使用 S3 Event Notifications
- **合规审计**: 使用 CloudTrail + EventBridge
- **全面监控**: 同时部署两种方案

### 成本优化

1. **Lambda 优化**: 减少函数执行时间和内存
2. **CloudTrail 优化**: 只记录必要的事件
3. **SNS 优化**: 使用 SQS 批量处理告警

### 告警策略

1. **分级告警**: 区分高危和低危操作
2. **聚合告警**: 批量删除时发送汇总告警
3. **静默时段**: 维护窗口期间暂停告警
4. **升级机制**: 关键告警自动升级到 PagerDuty

## 🎓 最佳实践总结

1. ✅ 为关键 bucket 启用实时监控
2. ✅ 启用 CloudTrail 进行完整审计
3. ✅ 定期测试告警系统
4. ✅ 监控告警系统本身的健康状态
5. ✅ 保留告警历史记录至少90天
6. ✅ 定期审查和优化告警规则
7. ✅ 建立告警响应流程和 runbook
