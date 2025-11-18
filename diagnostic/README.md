# S3 删除诊断工具

## 🔍 功能概述

这是一个专门用于诊断 S3 bucket 数据丢失问题的工具。通过分析 CloudWatch 指标、版本控制、生命周期策略、CloudTrail 事件等多个维度，帮助您快速定位数据丢失的原因。

## 🎯 使用场景

- **数据丢失调查**: 发现 bucket 中的对象或存储量异常减少
- **删除操作审计**: 追踪谁在何时删除了哪些对象
- **版本恢复**: 识别可恢复的删除标记和历史版本
- **策略审查**: 检查生命周期策略是否导致意外删除
- **合规审计**: 生成详细的删除操作报告

## 🚀 快速开始

### 前置条件

1. **AWS 凭证配置**
   ```bash
   aws configure
   ```

2. **必需的 IAM 权限**
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetBucketVersioning",
           "s3:ListBucketVersions",
           "s3:GetBucketLifecycleConfiguration",
           "s3:GetBucketLocation",
           "s3:ListBucket",
           "cloudwatch:GetMetricStatistics",
           "cloudtrail:LookupEvents"
         ],
         "Resource": "*"
       }
     ]
   }
   ```

### 安装依赖

```bash
cd diagnostic/
pip install -r requirements.txt
```

### 运行诊断

```bash
python s3_deletion_diagnostic.py <bucket-name>
```

示例:
```bash
python s3_deletion_diagnostic.py my-important-bucket
```

## 📊 诊断内容

### 1. CloudWatch 指标分析

分析过去90天的 bucket 指标，检测异常变化：

#### 存储量分析
- 检测存储量显著下降（>10%）
- 识别突然的数据丢失
- 计算变化百分比和绝对值

#### 对象数量分析
- 检测对象数量显著减少（>10,000个）
- 追踪批量删除操作
- 识别异常的对象数量波动

**示例输出**:
```
🔴 高危发现
[CloudWatch 指标异常] 检测到 5 次显著的存储量下降
- date: 2025-08-19
- change_gb: -4.53 GB
- change_pct: -14.93%
```

### 2. 版本控制检查

如果启用了版本控制，分析：

- **删除标记**: 可以恢复的"软删除"对象
- **历史版本**: 对象的所有版本
- **非当前版本**: 被覆盖的旧版本
- **恢复命令**: 自动生成恢复脚本

**示例输出**:
```
🟡 中危发现
[版本控制] 发现 450 个删除标记
这些对象被标记为删除,但可以恢复

恢复命令:
aws s3api delete-object \
  --bucket my-bucket \
  --key 'path/to/file.txt' \
  --version-id abc123...
```

### 3. 生命周期策略审查

检查是否配置了可能导致自动删除的策略：

- **过期规则**: 对象自动删除配置
- **转换规则**: 存储类别转换
- **非当前版本过期**: 旧版本清理
- **未完成分段上传清理**: 清理规则

**风险等级**:
- 🔴 高危: 配置了过期删除规则
- 🟢 信息: 未配置生命周期策略

### 4. CloudTrail 事件分析

查询过去90天的管理事件：

- **DeleteBucket**: bucket 删除操作
- **DeleteBucketLifecycle**: 生命周期策略删除
- **DeleteBucketPolicy**: 策略删除
- **PutBucketLifecycle**: 生命周期策略修改

**示例输出**:
```
🔴 高危发现
[CloudTrail 事件] 发现 3 个管理事件
- 2025-08-15: PutBucketLifecycle by user@example.com
- 2025-08-10: DeleteBucketPolicy by admin@example.com
```

### 5. 当前状态快照

提供 bucket 的当前状态：

- 对象总数
- 总存储大小
- 按前缀统计（Top 10）

## 📄 报告格式

诊断工具生成两种格式的报告：

### 1. Markdown 报告

保存在 `logs/` 目录，文件名格式：
```
s3-analysis-{bucket-name}-{timestamp}.md
```

包含：
- 完整的诊断结果
- 格式化的表格和列表
- 恢复命令
- 建议措施

### 2. JSON 报告

保存在 `logs/` 目录，文件名格式：
```
s3-analysis-{bucket-name}-{timestamp}.json
```

包含：
- 结构化的诊断数据
- 便于程序化处理
- 可用于自动化分析

## 🎨 风险等级

诊断结果按风险等级分类：

- 🔴 **高危**: 发现明确的数据丢失或高风险配置
- 🟡 **中危**: 发现潜在风险或需要关注的配置
- 🟢 **低危**: 轻微问题或优化建议
- 🔵 **信息**: 正常状态或配置信息

## 💡 常见场景和解决方案

### 场景 1: 发现大量删除标记

**原因**: 对象被删除但版本控制已启用

**解决方案**:
1. 查看报告中的"恢复命令"部分
2. 执行命令删除删除标记，恢复对象
3. 检查是谁执行了删除操作

### 场景 2: 存储量突然下降

**原因**: 可能是生命周期策略或批量删除

**解决方案**:
1. 检查生命周期策略配置
2. 查看 CloudTrail 事件
3. 如果有版本控制，检查是否可恢复

### 场景 3: 对象数量持续减少

**原因**: 可能是自动化脚本或应用程序删除

**解决方案**:
1. 启用 S3 Server Access Logging
2. 启用 CloudTrail 数据事件
3. 审查应用程序代码和自动化脚本

### 场景 4: 未发现异常但数据丢失

**原因**: 可能是数据事件未记录

**解决方案**:
1. 启用 CloudTrail 数据事件（记录对象级操作）
2. 启用 S3 Server Access Logging
3. 配置 S3 Inventory 进行定期快照

## 🔧 高级用法

### 自定义时间范围

修改代码中的时间范围（默认90天）:

```python
# 在 s3_deletion_diagnostic.py 中修改
start_time = datetime.now(timezone.utc) - timedelta(days=180)  # 改为180天
```

### 批量诊断

创建脚本批量诊断多个 bucket:

```bash
#!/bin/bash
for bucket in $(aws s3 ls | awk '{print $3}'); do
    echo "Diagnosing $bucket..."
    python s3_deletion_diagnostic.py "$bucket"
done
```

### 自动化告警

结合 cron 定期运行并发送告警:

```bash
# crontab -e
0 2 * * * /path/to/diagnostic/s3_deletion_diagnostic.py my-bucket && \
  mail -s "S3 Diagnostic Report" admin@example.com < /path/to/logs/latest.md
```

## 📊 测试工具

使用测试脚本验证诊断功能:

```bash
python test_diagnostic.py
```

测试内容：
- CloudWatch 指标获取
- 版本控制检查
- 生命周期策略解析
- CloudTrail 事件查询

## 🔒 安全建议

1. **最小权限原则**: 只授予必需的 IAM 权限
2. **审计日志**: 定期审查诊断报告
3. **版本控制**: 对重要 bucket 启用版本控制
4. **MFA 删除**: 对关键 bucket 启用 MFA Delete
5. **备份策略**: 实施跨区域复制或定期备份

## 📚 相关文档

- [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [S3 Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [CloudWatch Metrics for S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudwatch-monitoring.html)
- [CloudTrail for S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudtrail-logging.html)
- [S3 MFA Delete](https://docs.aws.amazon.com/AmazonS3/latest/userguide/MultiFactorAuthenticationDelete.html)

## 🆘 故障排除

### 问题: 权限不足

**错误**: `AccessDenied` 或 `UnauthorizedOperation`

**解决方案**: 确认 IAM 用户/角色具有必需的权限

### 问题: 未找到 CloudWatch 指标

**原因**: CloudWatch 指标可能未启用或数据不足

**解决方案**: 
1. 确认 bucket 有足够的历史数据
2. 等待 CloudWatch 指标生成（可能需要24小时）

### 问题: CloudTrail 事件为空

**原因**: CloudTrail 可能未启用或未记录管理事件

**解决方案**:
1. 启用 CloudTrail
2. 确认 trail 配置包含 S3 管理事件
3. 检查 trail 的时间范围

## 💼 企业级部署

对于企业环境，建议：

1. **集中化部署**: 在管理账户中运行诊断
2. **自动化调度**: 使用 Lambda + EventBridge 定期执行
3. **结果存储**: 将报告存储到中心化的 S3 bucket
4. **告警集成**: 集成 SNS/SES 发送告警通知
5. **仪表板**: 使用 QuickSight 可视化诊断结果
