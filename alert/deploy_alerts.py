#!/usr/bin/env python3
"""
S3 删除告警统一部署脚本
支持同时部署实时告警和审计告警
"""

import argparse
import subprocess
import sys

def deploy_alerts(bucket, email, region, alert_type):
    """部署告警系统"""
    
    print(f"\n{'='*70}")
    print(f"🚀 S3 删除告警系统部署")
    print(f"{'='*70}\n")
    print(f"📦 Bucket: {bucket}")
    print(f"📧 邮箱: {email}")
    print(f"🌍 区域: {region}")
    print(f"📋 告警类型: {alert_type}\n")
    
    success_count = 0
    total_count = 0
    
    # 部署实时告警
    if alert_type in ['realtime', 'both']:
        total_count += 1
        print(f"{'='*70}")
        print("⚡ 部署实时告警 (S3 Event Notifications)")
        print(f"{'='*70}\n")
        
        cmd = [
            'python3', 'setup_realtime_alert.py',
            '--bucket', bucket,
            '--email', email,
            '--region', region
        ]
        
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode == 0:
            success_count += 1
            print("\n✅ 实时告警部署成功!\n")
        else:
            print("\n❌ 实时告警部署失败!\n")
    
    # 部署审计告警
    if alert_type in ['cloudtrail', 'both']:
        total_count += 1
        print(f"{'='*70}")
        print("🔍 部署审计告警 (CloudTrail + EventBridge)")
        print(f"{'='*70}\n")
        
        cmd = [
            'python3', 'setup_deletion_alert.py',
            '--bucket', bucket,
            '--email', email,
            '--region', region
        ]
        
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode == 0:
            success_count += 1
            print("\n✅ 审计告警部署成功!\n")
        else:
            print("\n❌ 审计告警部署失败!\n")
    
    # 总结
    print(f"{'='*70}")
    print(f"📊 部署总结")
    print(f"{'='*70}\n")
    print(f"成功: {success_count}/{total_count}")
    
    if success_count == total_count:
        print("\n🎉 所有告警部署成功!")
        print(f"\n📧 重要: 请检查邮箱 {email} 并确认 SNS 订阅!")
        print(f"\n📋 你会收到的邮件:")
        if alert_type in ['realtime', 'both']:
            print(f"  ⚡ 实时告警: 主题显示为 '⚡[实时告警]{bucket}'")
        if alert_type in ['cloudtrail', 'both']:
            print(f"  🔍 审计告警: 内容包含 '[CloudTrail审计]'")
        
        print(f"\n🧪 测试命令:")
        print(f"  echo 'test' | aws s3 cp - s3://{bucket}/test-alert.txt")
        print(f"  aws s3 rm s3://{bucket}/test-alert.txt")
        
        if alert_type == 'both':
            print(f"\n  预期结果:")
            print(f"    ⚡ 实时告警: < 1 分钟内收到")
            print(f"    🔍 审计告警: 15-30 分钟后收到")
    else:
        print("\n⚠️  部分告警部署失败，请检查错误信息")
    
    print()

def main():
    parser = argparse.ArgumentParser(
        description='S3 删除告警统一部署工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 部署双重告警（推荐）
  python deploy_alerts.py --bucket my-bucket --email user@example.com --type both
  
  # 仅部署实时告警
  python deploy_alerts.py --bucket my-bucket --email user@example.com --type realtime
  
  # 仅部署审计告警
  python deploy_alerts.py --bucket my-bucket --email user@example.com --type cloudtrail
  
  # 指定区域
  python deploy_alerts.py --bucket my-bucket --region us-west-2 --email user@example.com --type both

告警类型对比:
  ⚡ realtime (实时告警):
     - 延迟: < 1 分钟
     - 邮件主题: ⚡[实时告警]bucket-name
     - 适合: 快速响应
  
  🔍 cloudtrail (审计告警):
     - 延迟: 15-30 分钟
     - 邮件内容: 包含 [CloudTrail审计]
     - 适合: 合规审计
  
  🎯 both (双重告警):
     - 同时部署两种告警
     - 推荐用于生产环境
        """
    )
    
    parser.add_argument('--bucket', required=True,
                       help='要监控的 S3 bucket')
    parser.add_argument('--email', required=True,
                       help='接收告警的邮箱地址')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS 区域 (默认: us-east-1)')
    parser.add_argument('--type', choices=['realtime', 'cloudtrail', 'both'],
                       default='both',
                       help='告警类型 (默认: both)')
    
    args = parser.parse_args()
    
    deploy_alerts(args.bucket, args.email, args.region, args.type)

if __name__ == '__main__':
    main()
