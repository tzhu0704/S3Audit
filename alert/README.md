# S3 删除告警系统

双重保障的 S3 删除监控和告警系统，支持实时告警和审计告警。

## 📚 文档导航

- **[GUIDE.md](GUIDE.md)** - 完整使用指南（推荐阅读）
- **[MONITORING_OPTIONS.md](MONITORING_OPTIONS.md)** - 所有监控方案对比
- **architecture-realtime.drawio** - 实时告警架构图
- **architecture-cloudtrail.drawio** - 审计告警架构图

## 📊 告警类型对比

| 特性 | ⚡ 实时告警 | 🔍 审计告警 |
|------|-----------|-----------|
| **延迟** | < 1 分钟 | 15-30 分钟 |
| **技术** | S3 Event Notifications | CloudTrail + EventBridge |
| **邮件主题** | `⚡[实时告警]bucket-name` | 内容包含 `[CloudTrail审计]` |
| **用户信息** | ❌ 无 | ✅ 完整 |
| **IP 地址** | ❌ 无 | ✅ 有 |
| **适用场景** | 快速响应 | 合规审计 |

## 🚀 快速开始

### 方式 1: 统一部署（推荐）

```bash
cd alert

# 部署双重告警
python3 deploy_alerts.py \
  --bucket my-bucket \
  --email your-email@example.com \
  --type both

# 仅部署实时告警
python3 deploy_alerts.py \
  --bucket my-bucket \
  --email your-email@example.com \
  --type realtime

# 仅部署审计告警
python3 deploy_alerts.py \
  --bucket my-bucket \
  --email your-email@example.com \
  --type cloudtrail
```

### 方式 2: 分别部署

```bash
cd alert

# 部署实时告警
python3 setup_realtime_alert.py \
  --bucket my-bucket \
  --email your-email@example.com

# 部署审计告警
python3 setup_deletion_alert.py \
  --bucket my-bucket \
  --email your-email@example.com
```

### 多区域支持

```bash
# 指定区域
python3 deploy_alerts.py \
  --bucket my-bucket \
  --region us-west-2 \
  --email your-email@example.com \
  --type both
```

## 📧 邮件区分

部署后，你会收到不同的告警邮件：

### ⚡ 实时告警邮件
- **发件人**: `⚡[实时告警]bucket-name`
- **延迟**: < 1 分钟
- **内容**: S3 Event JSON（包含 bucket, key, size, eventTime）

### 🔍 审计告警邮件
- **内容标识**: `🔍 [CloudTrail审计] S3删除告警`
- **延迟**: 15-30 分钟
- **内容**: CloudTrail Event JSON（包含 user, IP, requestID）

## 🧪 测试

```bash
# 创建测试文件
echo "test" | aws s3 cp - s3://my-bucket/test-alert.txt

# 删除文件（触发告警）
aws s3 rm s3://my-bucket/test-alert.txt

# 预期结果
# ⚡ 实时告警: 1 分钟内收到
# 🔍 审计告警: 15-30 分钟后收到
```

## 🔧 管理

### 查看配置

```bash
# 查看 S3 Event Notifications
aws s3api get-bucket-notification-configuration --bucket my-bucket

# 查看 EventBridge 规则
aws events describe-rule --name s3-deletion-my-bucket

# 查看 SNS 订阅
aws sns list-subscriptions
```

### 清理配置

```bash
# 清理实时告警
python3 setup_realtime_alert.py --bucket my-bucket --cleanup

# 清理审计告警
python3 setup_deletion_alert.py --bucket my-bucket --cleanup
```

## 📋 前置要求

### 实时告警
- ✅ S3 bucket 存在
- ✅ 有权限配置 S3 Event Notifications
- ✅ 有权限创建 SNS 主题

### 审计告警
- ✅ CloudTrail 已配置 S3 数据事件
- ✅ 有权限创建 EventBridge 规则
- ✅ 有权限创建 SNS 主题

配置 CloudTrail 数据事件:
```bash
aws cloudtrail put-event-selectors \
  --trail-name my-trail \
  --event-selectors '[{
    "ReadWriteType": "WriteOnly",
    "IncludeManagementEvents": false,
    "DataResources": [{
      "Type": "AWS::S3::Object",
      "Values": ["arn:aws:s3:::my-bucket/*"]
    }]
  }]'
```

## 💰 成本估算

- **实时告警**: < $1/月
- **审计告警**: < $2/月
- **总计**: < $3/月（假设每天 100 次删除）

## 🎯 推荐配置

**生产环境**: 同时启用两种告警
- ⚡ 实时告警: 快速响应误删
- 🔍 审计告警: 满足合规要求

**开发环境**: 仅启用实时告警
- 快速反馈，降低成本

## 📝 文件说明

- `deploy_alerts.py`: 统一部署脚本
- `setup_realtime_alert.py`: 实时告警部署脚本
- `setup_deletion_alert.py`: 审计告警部署脚本
- `README.md`: 本文档

## 🔍 故障排查

### 收不到实时告警

1. 检查 SNS 订阅是否确认
2. 检查 S3 Event Notifications 配置
3. 查看 CloudWatch Logs

### 收不到审计告警

1. 确认 CloudTrail 数据事件已配置
2. 等待 15-30 分钟（CloudTrail 延迟）
3. 检查 EventBridge 规则状态

### 邮件进入垃圾箱

- 将 `no-reply@sns.amazonaws.com` 添加到白名单
- 检查邮件过滤规则

## 📚 相关文档

- [S3 Event Notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/NotificationHowTo.html)
- [CloudTrail Data Events](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/logging-data-events-with-cloudtrail.html)
- [EventBridge Rules](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rules.html)
