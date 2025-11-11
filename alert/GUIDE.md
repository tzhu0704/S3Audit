# S3 删除告警系统 - 完整指南

## 📖 概述

本系统提供两种互补的 S3 删除监控方案，分别针对不同的使用场景：

### ⚡ 实时告警 (S3 Event Notifications)

**工作原理**: 当 S3 bucket 中的对象被删除时，S3 服务会立即触发一个事件通知，直接发送到 SNS 主题，然后通过邮件通知相关人员。整个过程在 1 分钟内完成。

**技术实现**: 利用 S3 的原生事件通知功能，无需额外的日志处理或事件匹配，因此延迟极低。配置简单，只需要在 S3 bucket 上设置事件通知规则，指定监听 `s3:ObjectRemoved:*` 事件即可。

**适用场景**: 
- 需要快速响应误删操作的生产环境
- 运维团队需要立即知道删除操作
- 开发测试环境的快速反馈
- 对成本敏感的场景（成本最低）

**局限性**: 由于是 S3 服务直接触发的事件，不包含操作者的身份信息（IAM 用户/角色）和源 IP 地址，因此无法用于安全审计和责任追溯。

---

### 🔍 审计告警 (CloudTrail + EventBridge)

**工作原理**: 当用户通过 AWS API 删除 S3 对象时，CloudTrail 会记录完整的 API 调用信息，包括操作者身份、源 IP、请求参数等。EventBridge 持续监听 CloudTrail 事件流，当匹配到删除操作时，触发 SNS 发送告警邮件。

**技术实现**: 需要先配置 CloudTrail 的 S3 数据事件记录功能，然后创建 EventBridge 规则来匹配特定的删除事件模式。由于 CloudTrail 需要时间来收集、处理和索引事件，因此存在 15-30 分钟的延迟。

**适用场景**:
- 需要满足合规要求的生产环境
- 安全审计和事后调查
- 需要追溯操作者身份的场景
- 金融、医疗等受监管行业

**优势**: 提供完整的审计追踪链，包括谁（IAM 用户/角色）、何时、从哪里（IP 地址）、做了什么（具体操作）、操作了什么（对象键）等信息，可以作为合规审计的证据。

---

### 🎯 为什么需要双重告警？

在生产环境中，我们推荐**同时部署两种告警方式**，原因如下：

1. **互补性**: 实时告警提供快速响应能力，审计告警提供完整的追溯能力
2. **分层防护**: 第一时间发现问题（实时），事后深度分析（审计）
3. **不同受众**: 运维团队关注实时告警，安全/合规团队关注审计告警
4. **成本合理**: 两者加起来每月仅需约 $3，相比数据丢失的风险微不足道

**实际案例**: 当发生误删时，运维团队会在 1 分钟内收到实时告警并立即采取恢复措施；同时，15-30 分钟后收到的审计告警会提供完整的操作者信息，用于事后分析和流程改进。

---

## 📊 两种告警方式对比

| 特性 | ⚡ 实时告警 (S3 Event) | 🔍 审计告警 (CloudTrail) |
|------|----------------------|-------------------------|
| **延迟** | < 1 分钟 | 15-30 分钟 |
| **技术架构** | S3 → SNS → Email | S3 → CloudTrail → EventBridge → SNS → Email |
| **邮件识别** | 主题: `⚡[实时告警]bucket-name` | 内容: `🔍 [CloudTrail审计]` |
| **用户信息** | ❌ 无 | ✅ 完整（IAM 用户/角色） |
| **源 IP** | ❌ 无 | ✅ 有 |
| **请求 ID** | ❌ 无 | ✅ 有 |
| **成本/月** | ~$1 | ~$2 |
| **配置复杂度** | ⭐ 简单 | ⭐⭐ 中等 |
| **适用场景** | 快速响应、运维告警 | 安全审计、合规要求 |

## 🏗️ 架构图

### ⚡ 实时告警架构
```
详见: architecture-realtime.drawio
```

### 🔍 审计告警架构
```
详见: architecture-cloudtrail.drawio
```

---

## 🚀 快速开始

### 方式 1: 统一部署（推荐）

```bash
cd alert

# 部署双重告警（推荐）
python3 deploy_alerts.py \
  --bucket my-bucket \
  --email your-email@example.com \
  --type both
```

### 方式 2: 分别部署

#### ⚡ 实时告警
```bash
python3 setup_realtime_alert.py \
  --bucket my-bucket \
  --email your-email@example.com
```

#### 🔍 审计告警
```bash
python3 setup_deletion_alert.py \
  --bucket my-bucket \
  --email your-email@example.com
```

---

## 📋 详细命令

### 部署命令

| 场景 | 命令 |
|------|------|
| 双重告警 | `python3 deploy_alerts.py --bucket BUCKET --email EMAIL --type both` |
| 仅实时 | `python3 setup_realtime_alert.py --bucket BUCKET --email EMAIL` |
| 仅审计 | `python3 setup_deletion_alert.py --bucket BUCKET --email EMAIL` |
| 指定区域 | 添加 `--region us-west-2` |

### 测试命令

```bash
# 使用测试脚本
./test_alerts.sh my-bucket

# 手动测试
echo "test" | aws s3 cp - s3://my-bucket/test.txt
aws s3 rm s3://my-bucket/test.txt
```

### 清理命令

```bash
# 清理实时告警
python3 setup_realtime_alert.py --bucket my-bucket --cleanup

# 清理审计告警
python3 setup_deletion_alert.py --bucket my-bucket --cleanup
```

---

## 📧 邮件示例

### ⚡ 实时告警邮件

**发件人**: `⚡[实时告警]my-bucket <no-reply@sns.amazonaws.com>`

**内容**:
```json
{
  "Records": [{
    "eventName": "ObjectRemoved:DeleteMarkerCreated",
    "eventTime": "2025-11-11T05:30:00.000Z",
    "s3": {
      "bucket": {"name": "my-bucket"},
      "object": {"key": "test.txt", "size": 1024}
    }
  }]
}
```

### 🔍 审计告警邮件

**内容**:
```
🔍 [CloudTrail审计] S3删除告警

📦 Bucket: my-bucket
🗑️ 操作: DeleteObject
👤 用户: tanzhuaz-Isengard
🌐 源IP: 72.21.198.65
⏰ 时间: 2025-11-11T05:30:00Z
🔍 事件ID: abc123...

⚡ 这是CloudTrail审计告警(延迟15-30分钟)
包含完整的用户和IP信息用于审计追溯

如需恢复,请检查版本控制或备份.
```

---

## 🎯 使用场景

### 生产环境（推荐双重告警）
```bash
python3 deploy_alerts.py \
  --bucket prod-bucket \
  --email ops@example.com \
  --type both
```
- ⚡ 实时告警: 快速响应误删
- 🔍 审计告警: 满足合规要求

### 开发环境（仅实时告警）
```bash
python3 setup_realtime_alert.py \
  --bucket dev-bucket \
  --email dev@example.com
```
- 快速反馈，降低成本

### 合规审计（仅审计告警）
```bash
python3 setup_deletion_alert.py \
  --bucket audit-bucket \
  --email compliance@example.com
```
- 完整审计信息，满足合规

---

## 🌍 多区域/多 Bucket 部署

### 多区域部署
```bash
# US
python3 deploy_alerts.py --bucket us-bucket --region us-east-1 --email ops@example.com --type both

# EU
python3 deploy_alerts.py --bucket eu-bucket --region eu-west-1 --email ops@example.com --type both

# AP
python3 deploy_alerts.py --bucket ap-bucket --region ap-southeast-1 --email ops@example.com --type both
```

### 批量部署脚本
```bash
#!/bin/bash
BUCKETS=("bucket1" "bucket2" "bucket3")
EMAIL="ops@example.com"

for bucket in "${BUCKETS[@]}"; do
  python3 deploy_alerts.py --bucket "$bucket" --email "$EMAIL" --type both
done
```

---

## 🔧 前置要求

### ⚡ 实时告警
- ✅ S3 bucket 存在
- ✅ 有权限配置 S3 Event Notifications
- ✅ 有权限创建 SNS 主题

### 🔍 审计告警
- ✅ CloudTrail 已配置 S3 数据事件
- ✅ 有权限创建 EventBridge 规则
- ✅ 有权限创建 SNS 主题

#### 配置 CloudTrail 数据事件
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

---

## 🔍 验证配置

### 查看 S3 Event Notifications
```bash
aws s3api get-bucket-notification-configuration --bucket my-bucket
```

### 查看 EventBridge 规则
```bash
aws events describe-rule --name s3-deletion-my-bucket
aws events list-targets-by-rule --rule s3-deletion-my-bucket
```

### 查看 SNS 订阅
```bash
aws sns list-topics --query 'Topics[?contains(TopicArn, `s3-`) && contains(TopicArn, `alert`)]'
```

---

## 🐛 故障排查

### 实时告警收不到

1. **检查 SNS 订阅**
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn TOPIC_ARN
   ```
   确认订阅状态为 `Confirmed`

2. **检查 S3 Event Notifications**
   ```bash
   aws s3api get-bucket-notification-configuration --bucket my-bucket
   ```
   确认配置了 `s3:ObjectRemoved:*` 事件

3. **测试 SNS**
   ```bash
   aws sns publish --topic-arn TOPIC_ARN --message "test"
   ```

### 审计告警收不到

1. **检查 CloudTrail 状态**
   ```bash
   aws cloudtrail get-trail-status --name my-trail
   ```
   确认 `IsLogging: true`

2. **检查事件选择器**
   ```bash
   aws cloudtrail get-event-selectors --trail-name my-trail
   ```
   确认配置了 S3 数据事件

3. **等待时间**
   - CloudTrail 延迟: 15-30 分钟（正常）
   - 可以运行监控脚本: `python3 monitor_cloudtrail.py`

4. **检查 EventBridge 目标**
   ```bash
   aws events list-targets-by-rule --rule s3-deletion-my-bucket
   ```
   确认目标 ARN 正确

---

## 💰 成本估算

假设每天 100 次删除操作：

| 组件 | 月成本 |
|------|--------|
| S3 Event Notifications | 免费 |
| CloudTrail 数据事件 | ~$2 |
| EventBridge | 免费 |
| SNS | ~$0.50 |
| **实时告警总计** | **~$1** |
| **审计告警总计** | **~$2** |
| **双重告警总计** | **~$3** |

---

## 📚 文件说明

| 文件 | 说明 |
|------|------|
| `deploy_alerts.py` | 统一部署脚本（推荐） |
| `setup_realtime_alert.py` | 实时告警部署脚本 |
| `setup_deletion_alert.py` | 审计告警部署脚本 |
| `test_alerts.sh` | 测试脚本 |
| `monitor_cloudtrail.py` | CloudTrail 事件监控脚本 |
| `GUIDE.md` | 本文档 |
| `architecture-*.drawio` | 架构图 |

---

## ❓ 常见问题

**Q: 两种告警有什么区别？**
- 实时告警: 快速（< 1分钟），无用户信息
- 审计告警: 慢（15-30分钟），有完整审计信息

**Q: 应该选择哪种？**
- 生产环境: 推荐双重告警
- 开发环境: 仅实时告警
- 合规要求: 必须审计告警

**Q: 如何区分两种告警邮件？**
- 实时: 邮件主题 `⚡[实时告警]bucket-name`
- 审计: 邮件内容 `🔍 [CloudTrail审计]`

**Q: 为什么审计告警这么慢？**
- CloudTrail 需要时间处理和索引事件
- 这是 AWS 的正常行为
- 这就是为什么需要实时告警作为补充

**Q: 可以只监控特定前缀吗？**
- 实时告警: 可以，修改 S3 Event Notifications 的 Filter
- 审计告警: 可以，修改 EventBridge 规则的 EventPattern

**Q: 如何更新邮箱地址？**
- 重新运行部署命令即可，会自动添加新订阅

---

## 🎉 最佳实践

1. ✅ **生产环境使用双重告警**
   - 实时响应 + 完整审计

2. ✅ **设置邮件过滤规则**
   - 实时告警: 高优先级
   - 审计告警: 归档到审计文件夹

3. ✅ **定期测试告警**
   - 每月运行一次测试脚本

4. ✅ **保留 CloudTrail 日志**
   - 至少 90 天

5. ✅ **监控告警系统本身**
   - 定期检查 SNS 订阅状态
   - 监控 EventBridge 规则指标

---

## 📞 支持

如有问题，请检查：
1. 本文档的故障排查部分
2. AWS CloudTrail 文档
3. AWS EventBridge 文档
4. AWS SNS 文档
