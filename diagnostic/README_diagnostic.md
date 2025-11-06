# S3 Bucket 数据删除配置诊断工具

## 功能说明

这个工具可以全面诊断S3 bucket中可能导致数据自动删除的配置，包括：

- 🔍 **生命周期策略** - 检查对象过期、版本过期、存储类别转换
- 📦 **版本控制** - 检查版本控制状态和MFA删除保护  
- 🔄 **复制配置** - 检查跨区域/同区域复制设置
- 🧠 **智能分层** - 检查自动存储类别优化
- 🔐 **Bucket策略** - 检查删除权限配置

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法
```bash
python s3_deletion_diagnostic.py your-bucket-name
```

### 指定区域
```bash
python s3_deletion_diagnostic.py your-bucket-name --region us-west-2
```

### 输出详细报告到文件
```bash
python s3_deletion_diagnostic.py your-bucket-name --output report.json
```

## 输出说明

### 风险等级
- 🔴 **高风险 (HIGH)**: 会直接删除数据的配置
- 🟡 **中风险 (MEDIUM)**: 可能影响数据访问或完整性
- 🟢 **低风险 (LOW)**: 影响存储成本或性能，但不删除数据
- ℹ️ **信息 (INFO)**: 配置信息，需要了解但无直接风险

### 报告内容
- 风险汇总统计
- 详细风险列表（类型、描述、影响、相关规则）
- 完整配置信息（可选JSON输出）

## AWS权限要求

运行此工具需要以下S3权限：
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetBucketLifecycleConfiguration",
                "s3:GetBucketVersioning", 
                "s3:GetBucketReplication",
                "s3:ListBucketIntelligentTieringConfigurations",
                "s3:GetBucketPolicy",
                "s3:HeadBucket"
            ],
            "Resource": "arn:aws:s3:::*"
        }
    ]
}
```

## 示例输出

```
============================================================
S3 BUCKET 数据删除风险诊断报告
============================================================
Bucket: my-test-bucket
扫描时间: 2024-01-15T10:30:00

📊 风险汇总:
   🔴 高风险: 2
   🟡 中风险: 1  
   🟢 低风险: 0
   ℹ️  信息: 1

📋 详细风险列表:

1. 🔴 生命周期对象过期 [HIGH]
   描述: 对象将在 30 天后自动删除
   影响: 当前版本对象会被永久删除
   规则ID: delete-old-objects

2. 🔴 非当前版本过期 [HIGH]
   描述: 非当前版本将在 7 天后自动删除
   影响: 历史版本会被永久删除，可能影响数据恢复
   规则ID: cleanup-versions
```

## 常见问题

**Q: 工具显示"未找到AWS凭证"**
A: 请先配置AWS CLI (`aws configure`) 或设置环境变量

**Q: 某些检查失败**  
A: 确保有足够的S3权限，某些配置可能不存在（正常情况）

**Q: 如何解读风险等级**
A: 重点关注HIGH级别风险，这些配置会直接删除数据