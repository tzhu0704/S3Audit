#!/usr/bin/env python3
"""
S3 实时删除告警 - 使用 S3 Event Notifications
延迟 < 1 分钟，无需 CloudTrail
支持多 bucket 和多 region
"""

import boto3
import json
import argparse

def setup_realtime_alert(bucket_name, email, region='us-east-1'):
    """
    配置 S3 Event Notifications 实现实时告警
    """
    
    print(f"\n{'='*60}")
    print(f"⚡ 配置 S3 实时删除告警")
    print(f"{'='*60}\n")
    print(f"📦 Bucket: {bucket_name}")
    print(f"📧 告警邮箱: {email}")
    print(f"🌍 区域: {region}\n")
    
    s3 = boto3.client('s3', region_name=region)
    sns = boto3.client('sns', region_name=region)
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity()['Account']
    
    # 1. 创建新的 SNS 主题 (区别于 CloudTrail 告警)
    print("[1/5] 创建实时告警 SNS 主题...")
    topic_name = f's3-realtime-alert-{bucket_name}'
    
    try:
        topic_response = sns.create_topic(Name=topic_name)
        topic_arn = topic_response['TopicArn']
        print(f"  ✅ SNS 主题已创建: {topic_arn}")
    except Exception as e:
        print(f"  ⚠️  主题可能已存在: {e}")
        topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
    
    # 2. 设置 SNS 主题显示名称（用于邮件主题）
    print(f"\n[2/5] 设置 SNS 主题显示名称...")
    try:
        sns.set_topic_attributes(
            TopicArn=topic_arn,
            AttributeName='DisplayName',
            AttributeValue=f'⚡[实时告警]{bucket_name}'
        )
        print(f"  ✅ 显示名称已设置")
    except Exception as e:
        print(f"  ⚠️  设置失败: {e}")
    
    # 3. 订阅邮件
    print(f"\n[3/5] 添加邮件订阅...")
    try:
        sns.subscribe(
            TopicArn=topic_arn,
            Protocol='email',
            Endpoint=email
        )
        print(f"  ✅ 邮件订阅已添加")
        print(f"  📧 请检查邮箱 {email} 并确认订阅!")
    except Exception as e:
        print(f"  ⚠️  订阅可能已存在: {e}")
    
    # 4. 配置 SNS 主题策略 (允许 S3 发布)
    print(f"\n[4/5] 配置 SNS 权限...")
    
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "SNS:Publish",
                "Resource": topic_arn,
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:s3:::{bucket_name}"
                    }
                }
            }
        ]
    }
    
    try:
        sns.set_topic_attributes(
            TopicArn=topic_arn,
            AttributeName='Policy',
            AttributeValue=json.dumps(policy)
        )
        print(f"  ✅ SNS 权限已配置")
    except Exception as e:
        print(f"  ⚠️  权限配置: {e}")
    
    # 5. 配置 S3 Event Notifications
    print(f"\n[5/5] 配置 S3 Event Notifications...")
    
    # 获取现有配置
    try:
        existing_config = s3.get_bucket_notification_configuration(Bucket=bucket_name)
        # 移除 ResponseMetadata
        existing_config.pop('ResponseMetadata', None)
    except:
        existing_config = {}
    
    # 添加新的 Topic 配置
    topic_configs = existing_config.get('TopicConfigurations', [])
    
    # 检查是否已存在
    new_config = {
        'Id': 'RealtimeDeletionAlert',
        'TopicArn': topic_arn,
        'Events': [
            's3:ObjectRemoved:Delete',
            's3:ObjectRemoved:DeleteMarkerCreated'
        ]
    }
    
    # 移除旧的同名配置
    topic_configs = [c for c in topic_configs if c.get('Id') != 'RealtimeDeletionAlert']
    topic_configs.append(new_config)
    
    existing_config['TopicConfigurations'] = topic_configs
    
    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=existing_config
        )
        print(f"  ✅ S3 Event Notifications 已配置")
    except Exception as e:
        print(f"  ❌ 配置失败: {e}")
        return
    
    # 完成
    print(f"\n{'='*60}")
    print(f"✅ 实时告警配置完成!")
    print(f"{'='*60}\n")
    print(f"📋 配置摘要:")
    print(f"  - 告警类型: ⚡ S3 实时告警 (< 1 分钟)")
    print(f"  - 监控 Bucket: {bucket_name}")
    print(f"  - SNS 主题: {topic_arn}")
    print(f"  - 告警邮箱: {email}")
    print(f"  - 监控事件: ObjectRemoved:Delete, DeleteMarkerCreated")
    print(f"\n⚠️  重要: 请检查邮箱 {email} 并点击确认订阅链接!")
    print(f"\n🧪 测试实时告警:")
    print(f"  echo 'test' | aws s3 cp - s3://{bucket_name}/realtime-test.txt")
    print(f"  aws s3 rm s3://{bucket_name}/realtime-test.txt")
    print(f"  (应该在 1 分钟内收到邮件)")
    print(f"\n📊 两种告警的区别:")
    print(f"  ⚡ 实时告警 (S3 Event): 延迟 < 1 分钟，包含基本事件信息")
    print(f"  🔍 审计告警 (CloudTrail): 延迟 15-30 分钟，包含完整审计信息")
    print()

def cleanup_realtime_alert(bucket_name, region='us-east-1'):
    """清理实时告警配置"""
    print(f"\n🗑️  清理实时告警配置...")
    
    s3 = boto3.client('s3', region_name=region)
    sns = boto3.client('sns', region_name=region)
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity()['Account']
    
    topic_name = f's3-realtime-alert-{bucket_name}'
    topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
    
    try:
        # 移除 S3 通知配置
        config = s3.get_bucket_notification_configuration(Bucket=bucket_name)
        config.pop('ResponseMetadata', None)
        
        topic_configs = config.get('TopicConfigurations', [])
        topic_configs = [c for c in topic_configs if c.get('Id') != 'RealtimeDeletionAlert']
        config['TopicConfigurations'] = topic_configs
        
        s3.put_bucket_notification_configuration(
            Bucket=bucket_name,
            NotificationConfiguration=config
        )
        print(f"  ✅ 已移除 S3 Event Notifications")
        
        # 删除 SNS 主题
        sns.delete_topic(TopicArn=topic_arn)
        print(f"  ✅ 已删除 SNS 主题")
        
        print(f"\n✅ 清理完成!")
    except Exception as e:
        print(f"  ⚠️  清理过程: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='S3 实时删除告警配置工具 (< 1 分钟延迟)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 配置实时告警
  python setup_realtime_alert.py --bucket datasync-dest1 --email your-email@example.com
  
  # 指定其他 bucket 和区域
  python setup_realtime_alert.py --bucket my-bucket --region us-west-2 --email your-email@example.com
  
  # 清理配置
  python setup_realtime_alert.py --bucket datasync-dest1 --cleanup
  
对比:
  ⚡ 实时告警 (S3 Event):
     - 延迟: < 1 分钟
     - 邮件主题: ⚡[实时告警]bucket-name
     - 信息: 基本事件 (bucket, key, event type, size, time)
     - 无用户/IP 信息
  
  🔍 审计告警 (CloudTrail):
     - 延迟: 15-30 分钟
     - 邮件主题: 🔍[CloudTrail审计] S3删除告警
     - 信息: 完整审计 (user, IP, request ID, 详细参数)
     - 适合合规审计
        """
    )
    
    parser.add_argument('--bucket', required=True,
                       help='要监控的 S3 bucket')
    parser.add_argument('--email', help='接收告警的邮箱地址')
    parser.add_argument('--region', default='us-east-1', 
                       help='AWS 区域 (默认: us-east-1)')
    parser.add_argument('--cleanup', action='store_true',
                       help='清理已部署的实时告警配置')
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_realtime_alert(args.bucket, args.region)
    else:
        if not args.email:
            parser.error("配置告警需要提供 --email 参数")
        setup_realtime_alert(args.bucket, args.email, args.region)

if __name__ == '__main__':
    main()
