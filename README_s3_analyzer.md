# S3 数据丢失分析工具 - 使用文档

## 📋 目录

- [简介](#简介)
- [功能特性](#功能特性)
- [安装配置](#安装配置)
- [使用方法](#使用方法)
- [输出说明](#输出说明)
- [性能优化](#性能优化)
- [常见问题](#常见问题)
- [故障排查](#故障排查)

---

## 简介

S3 数据丢失分析工具是一个用于分析 AWS S3 bucket 历史数据变化的工具,帮助识别可能的数据丢失、误删除或异常操作。

### 适用场景

- ✅ 用户报告 S3 数据丢失或数据量异常
- ✅ 需要审计 S3 bucket 的历史操作
- ✅ 未启用 Server Access Logging 或 CloudTrail 数据事件
- ✅ 需要分析版本控制和删除标记
- ✅ 排查生命周期策略导致的数据删除

---

## 功能特性

### 核心功能

| 功能 | 说明 | 数据来源 |
|------|------|---------|
| **CloudWatch 指标分析** | 过去 90 天的存储量和对象数量趋势 | CloudWatch Metrics |
| **版本控制分析** | 删除标记、非当前版本统计 | S3 Versioning API |
| **生命周期策略检查** | 自动删除规则识别 | S3 Lifecycle API |
| **CloudTrail 事件审计** | 过去 90 天的管理操作历史 | CloudTrail |
| **Bucket 策略审查** | 删除权限检查 | S3 Policy API |
| **对象统计** | 当前对象分布和前缀统计 | S3 List API (可选) |

### 输出格式

- **JSON 格式**: 完整的原始数据,便于程序处理
- **Markdown 格式**: 易读的报告,包含表格和图表

---

## 安装配置

### 系统要求

- **操作系统**: Linux / macOS / Windows (WSL)
- **Python**: 3.6 或更高版本
- **AWS CLI**: 已配置凭证

### 安装步骤

#### 1. 安装 Python 依赖

```bash
pip install boto3
```

#### 2. 配置 AWS 凭证

```bash
aws configure
```

输入:
- AWS Access Key ID
- AWS Secret Access Key
- Default region name
- Default output format

#### 3. 验证配置

```bash
aws s3 ls
```

#### 4. 下载工具

```bash
# 克隆仓库或下载文件
cd /path/to/tool
chmod +x s3-analyzer
```

### 所需 IAM 权限

创建 IAM 策略:

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
        "s3:GetBucketPolicy",
        "s3:ListBucket",
        "cloudwatch:GetMetricStatistics",
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 使用方法

### 命令行语法

```bash
s3-analyzer -b BUCKET [选项]
```

### 参数说明

| 参数 | 简写 | 说明 | 必需 | 默认值 |
|------|------|------|------|--------|
| `--bucket` | `-b` | S3 bucket 名称 | ✅ 是 | - |
| `--region` | `-r` | AWS 区域 | ❌ 否 | us-east-1 |
| `--skip-listing` | `-s` | 跳过对象列表统计 | ❌ 否 | false |
| `--help` | `-h` | 显示帮助信息 | ❌ 否 | - |

### 使用示例

#### 基本用法

```bash
# 分析 bucket
./s3-analyzer -b my-bucket

# 或使用 Python 直接运行
python3 s3_deletion_analyzer.py --bucket my-bucket
```

#### 指定区域

```bash
# 美国西部
./s3-analyzer -b my-bucket -r us-west-2

# 中国区域
./s3-analyzer -b my-bucket -r cn-north-1
```

#### 大型 Bucket (快速模式)

```bash
# 跳过对象列表统计
./s3-analyzer -b large-bucket --skip-listing
```

#### 查看帮助

```bash
./s3-analyzer -h
```

---

## 输出说明

### 报告位置

```
当前目录/
└── logs/
    ├── s3-analysis-{bucket}-{timestamp}.json
    └── s3-analysis-{bucket}-{timestamp}.md
```

### Markdown 报告结构

```markdown
# S3 数据丢失分析报告

## 📊 执行摘要
- 高危/中危/信息发现统计

## 📈 CloudWatch 指标趋势 (过去 90 天)
- 存储量和对象数量变化表格
- 异常变化高亮显示

## 🔍 CloudTrail 事件汇总 (过去 90 天)
- 事件统计表
- 生命周期策略变更
- Bucket 策略变更
- 版本控制变更
- 删除相关操作

## 📋 版本控制分析
- 删除标记列表
- 非当前版本分析
- 恢复命令示例

## 🔴/🟡/🔵 发现详情
- 按严重程度分类
- 详细说明和建议

## 📦 当前 Bucket 状态
- 对象总数和总大小
- 按前缀统计

## 💡 结论和建议
- 针对性的行动建议

## 📚 参考文档
- AWS 官方文档链接
```

### 严重程度说明

| 级别 | 图标 | 说明 | 示例 |
|------|------|------|------|
| 高危 | 🔴 | 可能导致数据丢失 | 生命周期自动删除规则、大量删除操作 |
| 中危 | 🟡 | 需要关注的配置变更 | 策略变更、版本控制变更 |
| 信息 | 🔵 | 一般性信息 | 版本控制状态、无生命周期策略 |

---

## 性能优化

### 执行时间估算

| Bucket 对象数 | 不跳过列表 | 跳过列表 | 建议 |
|--------------|----------|---------|------|
| < 1,000 | ~5 秒 | ~3 秒 | 正常运行 |
| 1,000 - 10,000 | ~30 秒 | ~3 秒 | 正常运行 |
| 10,000 - 100,000 | ~5 分钟 | ~3 秒 | 考虑跳过 |
| 100,000 - 1,000,000 | ~50 分钟 | ~3 秒 | 建议跳过 |
| > 1,000,000 | > 1 小时 | ~3 秒 | 必须跳过 |

### 优化建议

#### 1. 使用 --skip-listing

对于大型 bucket:

```bash
./s3-analyzer -b large-bucket --skip-listing
```

**跳过的内容**:
- 对象列表遍历
- 前缀统计

**保留的内容**:
- CloudWatch 指标 ✅
- CloudTrail 事件 ✅
- 版本控制分析 ✅
- 生命周期策略 ✅

#### 2. 并行分析多个 Bucket

```bash
# 后台运行
./s3-analyzer -b bucket1 --skip-listing &
./s3-analyzer -b bucket2 --skip-listing &
./s3-analyzer -b bucket3 --skip-listing &
wait
```

#### 3. 定期运行

```bash
# 添加到 crontab
0 2 * * * /path/to/s3-analyzer -b my-bucket --skip-listing
```

---

## 常见问题

### Q1: 为什么看不到具体哪些文件被删除?

**A**: 需要启用 CloudTrail 数据事件才能记录对象级别的操作。本工具只能分析:
- CloudWatch 指标(存储量和对象数量变化)
- 管理事件(策略变更等)
- 版本控制信息(如果启用)

### Q2: 分析结果显示数据量下降,如何确定原因?

**A**: 按以下顺序排查:

1. **检查 CloudWatch 指标** - 确定数据丢失的时间点
2. **查看 CloudTrail 事件** - 该时间点是否有策略变更
3. **检查生命周期策略** - 是否有自动删除规则
4. **查看版本控制** - 是否有删除标记
5. **对比 Veeam 日志** - 是否是 Veeam 自动清理

### Q3: 如何恢复被删除的对象?

**A**: 如果启用了版本控制:

```bash
# 1. 查看对象的所有版本
aws s3api list-object-versions --bucket my-bucket --prefix path/to/file

# 2. 如果是删除标记,删除标记即可恢复
aws s3api delete-object --bucket my-bucket --key path/to/file --version-id DELETE_MARKER_ID

# 3. 如果要恢复到特定版本
aws s3api copy-object \
  --bucket my-bucket \
  --copy-source my-bucket/path/to/file?versionId=VERSION_ID \
  --key path/to/file
```

### Q4: 工具运行很慢怎么办?

**A**: 使用 `--skip-listing` 参数:

```bash
./s3-analyzer -b my-bucket --skip-listing
```

### Q5: 支持哪些 AWS 区域?

**A**: 支持所有 AWS 区域,包括:
- 标准区域: us-east-1, us-west-2, eu-west-1 等
- 中国区域: cn-north-1, cn-northwest-1
- GovCloud: us-gov-west-1, us-gov-east-1

### Q6: 可以分析多个 Bucket 吗?

**A**: 可以,使用脚本批量运行:

```bash
#!/bin/bash
for bucket in bucket1 bucket2 bucket3; do
    ./s3-analyzer -b $bucket --skip-listing
done
```

---

## 故障排查

### 错误: 未找到 python3

```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt-get install python3

# CentOS/RHEL
sudo yum install python3
```

### 错误: 未找到 boto3

```bash
pip3 install boto3

# 或使用国内镜像
pip3 install boto3 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 错误: AccessDenied

检查 IAM 权限:

```bash
# 测试权限
aws s3api get-bucket-versioning --bucket my-bucket
aws cloudwatch get-metric-statistics --namespace AWS/S3 --metric-name BucketSizeBytes --dimensions Name=BucketName,Value=my-bucket Name=StorageType,Value=StandardStorage --start-time 2025-01-01T00:00:00Z --end-time 2025-01-02T00:00:00Z --period 86400 --statistics Average
```

### 错误: NoSuchBucket

确认:
1. Bucket 名称拼写正确
2. Bucket 在指定的区域
3. 有访问权限

```bash
# 列出所有 bucket
aws s3 ls

# 指定区域
aws s3 ls --region us-west-2
```

### 分析结果不准确

可能原因:
1. CloudWatch 指标有延迟(最多 24 小时)
2. 版本控制最近才启用
3. CloudTrail 事件超过 90 天

---

## 最佳实践

### 1. 定期运行

```bash
# 每周运行一次
0 2 * * 0 /path/to/s3-analyzer -b production-bucket --skip-listing
```

### 2. 保存历史报告

```bash
# 归档报告
mkdir -p archive/$(date +%Y%m)
cp logs/*.md archive/$(date +%Y%m)/
```

### 3. 启用预防措施

分析后,建议启用:

```bash
# 1. 启用版本控制
aws s3api put-bucket-versioning --bucket my-bucket --versioning-configuration Status=Enabled

# 2. 启用 CloudTrail 数据事件
aws cloudtrail put-event-selectors --trail-name my-trail --event-selectors '[{"ReadWriteType":"All","IncludeManagementEvents":true,"DataResources":[{"Type":"AWS::S3::Object","Values":["arn:aws:s3:::my-bucket/*"]}]}]'

# 3. 配置 S3 Inventory
aws s3api put-bucket-inventory-configuration --bucket my-bucket --id daily-inventory --inventory-configuration file://inventory-config.json
```

### 4. 设置告警

```bash
# CloudWatch 告警 - 对象数量下降
aws cloudwatch put-metric-alarm \
  --alarm-name s3-object-count-decrease \
  --alarm-description "Alert when S3 object count decreases" \
  --metric-name NumberOfObjects \
  --namespace AWS/S3 \
  --statistic Average \
  --period 86400 \
  --evaluation-periods 1 \
  --threshold 1000 \
  --comparison-operator LessThanThreshold \
  --dimensions Name=BucketName,Value=my-bucket Name=StorageType,Value=AllStorageTypes
```

---

## 技术支持

### 获取帮助

1. 查看帮助信息: `./s3-analyzer -h`
2. 查看本文档: `README_s3_analyzer.md`
3. 查看 AWS 文档: [S3 用户指南](https://docs.aws.amazon.com/s3/)

### 报告问题

提供以下信息:
- 错误信息截图
- Bucket 对象数量
- AWS 区域
- Python 版本: `python3 --version`
- boto3 版本: `pip3 show boto3`

---

## 更新日志

### v1.0.0 (2025-01-07)

- ✅ 初始版本发布
- ✅ CloudWatch 指标分析 (90 天)
- ✅ CloudTrail 事件审计 (90 天)
- ✅ 版本控制分析
- ✅ 生命周期策略检查
- ✅ Markdown 报告生成
- ✅ 性能优化 (--skip-listing)

---

## 许可证

本工具仅供内部使用。

---

## 附录

### A. 完整命令参考

```bash
# 查看帮助
./s3-analyzer -h

# 基本分析
./s3-analyzer -b my-bucket

# 指定区域
./s3-analyzer -b my-bucket -r us-west-2

# 快速模式
./s3-analyzer -b my-bucket --skip-listing

# Python 直接运行
python3 s3_deletion_analyzer.py --bucket my-bucket --region us-east-1 --skip-listing
```

### B. 报告示例

查看 `logs/` 目录下的示例报告:
- `s3-analysis-example-bucket-20250107-120000.md`

### C. 相关工具

- AWS CLI: https://aws.amazon.com/cli/
- boto3: https://boto3.amazonaws.com/
- S3 Inventory: https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html
