#!/usr/bin/env python3
"""
监控 CloudTrail 事件并等待告警
"""

import boto3
import time
from datetime import datetime, timedelta

def monitor_cloudtrail():
    cloudtrail = boto3.client('cloudtrail')
    
    print("\n" + "="*60)
    print("🔍 监控 CloudTrail 删除事件")
    print("="*60 + "\n")
    print(f"⏰ 开始时间: {datetime.now().strftime('%H:%M:%S')}")
    print("📦 监控 Bucket: datasync-dest1")
    print("🔄 每分钟检查一次...")
    print("\n按 Ctrl+C 停止监控\n")
    print("-" * 60)
    
    check_count = 0
    found = False
    
    try:
        while not found:
            check_count += 1
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # 查询最近 1 小时的删除事件
            start_time = datetime.utcnow() - timedelta(hours=1)
            
            try:
                response = cloudtrail.lookup_events(
                    LookupAttributes=[
                        {'AttributeKey': 'EventName', 'AttributeValue': 'DeleteObject'}
                    ],
                    StartTime=start_time,
                    MaxResults=5
                )
                
                events = response.get('Events', [])
                
                if events:
                    print(f"\n[{current_time}] ✅ 发现 {len(events)} 个 DeleteObject 事件!")
                    print("-" * 60)
                    
                    for event in events[:3]:
                        import json
                        trail_event = json.loads(event['CloudTrailEvent'])
                        bucket = trail_event.get('requestParameters', {}).get('bucketName', 'N/A')
                        key = trail_event.get('requestParameters', {}).get('key', 'N/A')
                        event_time = event['EventTime'].strftime('%H:%M:%S')
                        
                        if bucket == 'datasync-dest1':
                            print(f"\n📦 Bucket: {bucket}")
                            print(f"📄 对象: {key}")
                            print(f"⏰ 事件时间: {event_time}")
                            print(f"👤 用户: {event.get('Username', 'N/A')}")
                            found = True
                    
                    if found:
                        print("\n" + "="*60)
                        print("🎉 CloudTrail 已记录删除事件!")
                        print("="*60 + "\n")
                        print("📧 EventBridge 应该会在几秒内触发告警")
                        print("📬 请检查邮箱: tanzhuaz@amazon.com")
                        print("\n💡 邮件内容应包含: 🔍 [CloudTrail审计]")
                        break
                else:
                    print(f"[{current_time}] 检查 #{check_count} - 暂无事件，继续等待...")
                
            except Exception as e:
                print(f"[{current_time}] ⚠️  查询错误: {e}")
            
            if not found:
                time.sleep(60)  # 等待 1 分钟
                
    except KeyboardInterrupt:
        print(f"\n\n⏹️  监控已停止")
        print(f"📊 共检查了 {check_count} 次")

if __name__ == '__main__':
    monitor_cloudtrail()
