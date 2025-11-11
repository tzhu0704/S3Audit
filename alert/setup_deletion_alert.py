#!/usr/bin/env python3
"""
S3 删除事件实时告警部署脚本
针对已有 CloudTrail (my-s3-trail-poc) 监控的 bucket: datasync-dest1
"""

import boto3
import json
import argparse

def setup_deletion_alert(bucket_name, email, region='us-east-1'):
    """
    设置 S3 删除事件实时告警
    
    架构: CloudTrail → EventBridge → SNS → Email
    """
    
    print(f"\n{'='*60}")
    print(f"🚀 开始部署 S3 删除告警系统")
    print(f"{'='*60}\n")
    print(f"📦 Bucket: {bucket_name}")
    print(f"📧 告警邮箱: {email}")
    print(f"🌍 区域: {region}\n")
    
    sns = boto3.client('sns', region_name=region)
    events = boto3.client('events', region_name=region)
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity()['Account']
    
    # 1. 创建 SNS 主题（CloudTrail 审计告警）
    print("[1/4] 创建 SNS 告警主题...")
    topic_name = f's3-cloudtrail-alert-{bucket_name}'
    
    try:
        topic_response = sns.create_topic(Name=topic_name)
        topic_arn = topic_response['TopicArn']
        print(f"  ✅ SNS 主题已创建: {topic_arn}")
    except Exception as e:
        print(f"  ⚠️  主题可能已存在: {e}")
        topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
    
    # 2. 订阅邮件
    print(f"\n[2/4] 添加邮件订阅...")
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
    
    # 3. 创建 EventBridge 规则
    print(f"\n[3/4] 创建 EventBridge 规则...")
    rule_name = f's3-deletion-{bucket_name}'
    
    event_pattern = {
        "source": ["aws.s3"],
        "detail-type": ["AWS API Call via CloudTrail"],
        "detail": {
            "eventSource": ["s3.amazonaws.com"],
            "eventName": ["DeleteObject", "DeleteObjects"],
            "requestParameters": {
                "bucketName": [bucket_name]
            }
        }
    }
    
    try:
        events.put_rule(
            Name=rule_name,
            EventPattern=json.dumps(event_pattern),
            State='ENABLED',
            Description=f'实时告警 {bucket_name} 的删除操作'
        )
        print(f"  ✅ EventBridge 规则已创建: {rule_name}")
    except Exception as e:
        print(f"  ⚠️  规则可能已存在: {e}")
    
    # 4. 授权 EventBridge 发布到 SNS
    print(f"\n[4/4] 配置权限和目标...")
    
    # SNS 策略
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "events.amazonaws.com"},
            "Action": "SNS:Publish",
            "Resource": topic_arn,
            "Condition": {
                "StringEquals": {
                    "aws:SourceAccount": account_id
                }
            }
        }]
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
    
    # 添加 SNS 为 EventBridge 目标
    try:
        events.put_targets(
            Rule=rule_name,
            Targets=[{
                'Id': '1',
                'Arn': topic_arn,
                'InputTransformer': {
                    'InputPathsMap': {
                        'eventName': '$.detail.eventName',
                        'bucket': '$.detail.requestParameters.bucketName',
                        'user': '$.detail.userIdentity.principalId',
                        'sourceIP': '$.detail.sourceIPAddress',
                        'time': '$.detail.eventTime',
                        'eventID': '$.detail.eventID'
                    },
                    'InputTemplate': '"🔍 [CloudTrail审计] S3删除告警\n\n📦 Bucket: <bucket>\n🗑️ 操作: <eventName>\n👤 用户: <user>\n🌐 源IP: <sourceIP>\n⏰ 时间: <time>\n🔍 事件ID: <eventID>\n\n⚡ 这是CloudTrail审计告警(延迟15-30分钟)\n包含完整的用户和IP信息用于审计追溯\n\n如需恢复,请检查版本控制或备份."'
                }
            }]
        )
        print(f"  ✅ EventBridge 目标已配置")
    except Exception as e:
        print(f"  ⚠️  目标配置: {e}")
    
    # 完成
    print(f"\n{'='*60}")
    print(f"✅ 部署完成!")
    print(f"{'='*60}\n")
    print(f"📋 配置摘要:")
    print(f"  - CloudTrail: my-s3-trail-poc (已存在)")
    print(f"  - 监控 Bucket: {bucket_name}")
    print(f"  - EventBridge 规则: {rule_name}")
    print(f"  - SNS 主题: {topic_arn}")
    print(f"  - 告警邮箱: {email}")
    print(f"\n⚠️  重要: 请检查邮箱 {email} 并点击确认订阅链接!")
    print(f"\n🧪 测试告警:")
    print(f"  aws s3 rm s3://{bucket_name}/test-delete.txt")
    print(f"\n📊 查看规则:")
    print(f"  aws events describe-rule --name {rule_name}")
    print()

def cleanup_alert(bucket_name, region='us-east-1'):
    """清理告警配置"""
    print(f"\n🗑️  清理告警配置...")
    
    events = boto3.client('events', region_name=region)
    sns = boto3.client('sns', region_name=region)
    sts = boto3.client('sts')
    account_id = sts.get_caller_identity()['Account']
    
    rule_name = f's3-deletion-{bucket_name}'
    topic_name = f's3-cloudtrail-alert-{bucket_name}'
    topic_arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
    
    try:
        # 移除目标
        events.remove_targets(Rule=rule_name, Ids=['1'])
        print(f"  ✅ 已移除 EventBridge 目标")
        
        # 删除规则
        events.delete_rule(Name=rule_name)
        print(f"  ✅ 已删除 EventBridge 规则")
        
        # 删除 SNS 主题
        sns.delete_topic(TopicArn=topic_arn)
        print(f"  ✅ 已删除 SNS 主题")
        
        print(f"\n✅ 清理完成!")
    except Exception as e:
        print(f"  ⚠️  清理过程: {e}")

def main():
    parser = argparse.ArgumentParser(
        description='S3 删除事件实时告警部署工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 部署告警
  python setup_deletion_alert.py --bucket datasync-dest1 --email your-email@example.com
  
  # 指定其他 bucket 和区域
  python setup_deletion_alert.py --bucket my-bucket --region us-west-2 --email your-email@example.com
  
  # 清理配置
  python setup_deletion_alert.py --bucket datasync-dest1 --cleanup
  
注意:
  - 需要已配置 CloudTrail 数据事件
  - 邮箱需要确认订阅才能收到告警
  - 告警延迟: 15-30 分钟
  - 邮件主题: [CloudTrail审计] S3删除告警
        """
    )
    
    parser.add_argument('--bucket', required=True,
                       help='要监控的 S3 bucket')
    parser.add_argument('--email', help='接收告警的邮箱地址')
    parser.add_argument('--region', default='us-east-1', 
                       help='AWS 区域 (默认: us-east-1)')
    parser.add_argument('--cleanup', action='store_true',
                       help='清理已部署的告警配置')
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_alert(args.bucket, args.region)
    else:
        if not args.email:
            parser.error("部署告警需要提供 --email 参数")
        setup_deletion_alert(args.bucket, args.email, args.region)

if __name__ == '__main__':
    main()
