# S3 Server Access Log 分析器

## 📊 功能概述

这是一个基于 Streamlit 的 Web 应用，用于分析 S3 Server Access Logs，帮助您深入了解 S3 bucket 的访问模式、用户行为和潜在的安全问题。

## 🎯 使用场景

- **访问审计**: 查看谁在何时访问了您的 S3 资源
- **安全分析**: 识别异常访问模式和潜在的安全威胁
- **删除追踪**: 快速定位删除操作，高亮显示 DELETE 操作
- **性能优化**: 分析访问热点，优化数据分布
- **成本分析**: 了解数据传输量和访问频率

## 🚀 快速开始

### 前置条件

1. **启用 S3 Server Access Logging**
   ```bash
   aws s3api put-bucket-logging \
     --bucket your-bucket \
     --bucket-logging-status file://logging.json
   ```

   logging.json 示例:
   ```json
   {
     "LoggingEnabled": {
       "TargetBucket": "your-log-bucket",
       "TargetPrefix": "s3logs/"
     }
   }
   ```

2. **配置 AWS 凭证**
   ```bash
   aws configure
   ```

### 安装依赖

```bash
cd app/
pip install -r requirements.txt
```

### 启动应用

```bash
streamlit run s3_log_analyzer.py
```

或使用快捷脚本:
```bash
./run.sh
```

应用将在浏览器中自动打开 `http://localhost:8501`

## 📖 使用指南

### 1. 配置参数

在左侧边栏配置以下参数：

- **选择 Bucket**: 选择存储日志的 bucket
- **日志前缀**: 日志文件的前缀路径（如 `s3logs/`）
- **时间范围**: 选择要分析的时间范围
  - 最近1天
  - 最近3天
  - 最近7天
  - 最近30天
  - 全部
- **最大日志文件数**: 限制加载的文件数量（10-2000）

### 2. 加载日志

点击 **🔄 加载日志** 按钮开始加载和解析日志文件。

加载完成后会显示：
- ✅ 已加载的记录数
- Bucket 名称
- 时间范围

### 3. 数据筛选

使用筛选条件进一步过滤数据：

- **时间范围**: 精确到日期的时间筛选
- **目标 Bucket**: 按被访问的 bucket 筛选
- **操作类型**: 筛选特定操作（GET、PUT、DELETE 等）
- **HTTP 状态码**: 筛选成功/失败的请求

### 4. 查看分析结果

#### 📈 统计概览
- 总请求数
- 唯一用户数
- 错误请求数
- 数据传输量

#### 📊 操作类型
- 操作类型分布饼图
- 操作统计表
- 每日操作趋势图

#### 👤 用户统计
- Top 10 活跃用户柱状图
- 用户请求统计表

#### 🌐 IP 分布
- Top 10 IP 地址饼图
- IP 请求统计表
- HTTP 状态码分布

#### 📋 详细列表
- 完整的访问记录表格
- **删除操作红色高亮显示**
- 分页浏览
- 导出 CSV 功能

## 🔍 关键功能

### 删除操作追踪

所有包含 DELETE 的操作会以红色背景高亮显示，方便快速识别：

- REST.DELETE.OBJECT
- REST.DELETE.BUCKET
- REST.DELETE.UPLOAD

### 高性能加载

- **多线程并行处理**: 使用50个并发线程加速文件下载
- **智能时间过滤**: 按文件修改时间预过滤，减少不必要的下载
- **缓存机制**: 相同参数的请求会使用缓存结果（5分钟有效期）

### 数据导出

点击 **📥 下载 CSV** 按钮可导出当前筛选的数据，文件名格式：
```
s3_access_log_YYYYMMDD_HHMMSS.csv
```

## ⚙️ 性能优化建议

1. **首次加载**: 建议从较小的时间范围开始（如"最近1天"）
2. **文件数量**: 根据日志量调整"最大日志文件数"
   - 少量日志: 100-200 文件
   - 中等日志: 200-500 文件
   - 大量日志: 500-1000 文件
3. **时间过滤**: 优先使用时间范围过滤，而不是加载全部后再筛选

## 📊 日志格式

应用解析标准的 S3 Server Access Log 格式，包含以下字段：

- Bucket Owner
- Bucket Name
- Time
- Remote IP
- Requester
- Request ID
- Operation
- Key
- HTTP Status
- Error Code
- Bytes Sent
- Object Size
- Total Time
- Turn-Around Time
- Referer
- User Agent
- Version ID

## 🔧 故障排除

### 问题: 未找到日志数据

**解决方案**:
1. 确认 S3 Server Access Logging 已启用
2. 检查日志前缀是否正确
3. 确认日志文件已生成（日志有延迟，通常几小时）
4. 尝试选择"全部"时间范围

### 问题: 加载速度慢

**解决方案**:
1. 减少"最大日志文件数"
2. 缩小时间范围
3. 检查网络连接
4. 确认 AWS 区域配置正确

### 问题: 内存不足

**解决方案**:
1. 减少加载的文件数量
2. 使用时间过滤减少数据量
3. 分批次分析数据

## 📚 相关文档

- [S3 Server Access Logging](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html)
- [S3 Access Log Format](https://docs.aws.amazon.com/AmazonS3/latest/userguide/LogFormat.html)
- [Streamlit Documentation](https://docs.streamlit.io/)

## 💡 最佳实践

1. **定期审计**: 建议每周审查一次访问日志
2. **关注删除操作**: 重点关注红色高亮的 DELETE 操作
3. **监控异常**: 留意错误请求数和异常 IP 地址
4. **保留日志**: 建议保留至少90天的访问日志
5. **自动化分析**: 可以结合 Lambda 实现自动化日志分析和告警
