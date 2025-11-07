#!/usr/bin/env python3
"""
S3 数据丢失分析工具
分析 S3 bucket 的历史数据,检测可能的数据丢失
"""

import boto3
import argparse
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

class S3DeletionAnalyzer:
    def __init__(self, bucket_name, region='us-east-1', skip_object_listing=False):
        self.bucket_name = bucket_name
        self.region = region
        self.skip_object_listing = skip_object_listing
        self.s3_client = boto3.client('s3', region_name=region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.findings = []
        
        # 创建 logs 目录(在脚本所在目录)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.logs_dir = os.path.join(script_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
    def analyze(self):
        """执行完整分析"""
        print(f"\n{'='*80}")
        print(f"S3 数据丢失分析报告")
        print(f"Bucket: {self.bucket_name}")
        print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # 1. CloudWatch 指标分析
        print("[1/7] 分析 CloudWatch 历史指标...")
        self._analyze_cloudwatch_metrics()
        
        # 2. 版本控制检查
        print("[2/7] 检查版本控制和删除标记...")
        self._check_versioning()
        
        # 3. 生命周期策略检查
        print("[3/7] 检查生命周期策略...")
        self._check_lifecycle_policy()
        
        # 4. CloudTrail 事件检查
        print("[4/7] 检查 CloudTrail 管理事件...")
        self._check_cloudtrail_events()
        
        # 5. Bucket 策略检查
        print("[5/7] 检查 Bucket 策略...")
        self._check_bucket_policy()
        
        # 6. 当前对象统计
        if not self.skip_object_listing:
            print("[6/7] 统计当前对象...")
            self._analyze_current_objects()
        else:
            print("[6/7] 跳过对象统计(使用 --skip-listing 参数)...")
            self.current_stats = {'skipped': True}
        
        # 7. 生成报告
        print("[7/7] 生成分析报告...\n")
        self._generate_report()
        
    def _analyze_cloudwatch_metrics(self):
        """分析 CloudWatch 指标"""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=90)
        
        try:
            # 获取存储量指标
            size_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='BucketSizeBytes',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': self.bucket_name},
                    {'Name': 'StorageType', 'Value': 'StandardStorage'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            
            # 获取对象数量指标
            count_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName='NumberOfObjects',
                Dimensions=[
                    {'Name': 'BucketName', 'Value': self.bucket_name},
                    {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Average']
            )
            
            # 分析存储量变化
            size_data = sorted(size_response['Datapoints'], key=lambda x: x['Timestamp'])
            count_data = sorted(count_response['Datapoints'], key=lambda x: x['Timestamp'])
            
            if len(size_data) > 1:
                size_changes = []
                for i in range(1, len(size_data)):
                    prev_size = size_data[i-1]['Average']
                    curr_size = size_data[i]['Average']
                    change = curr_size - prev_size
                    change_pct = (change / prev_size * 100) if prev_size > 0 else 0
                    
                    if change_pct < -10:  # 下降超过 10%
                        size_changes.append({
                            'date': size_data[i]['Timestamp'].strftime('%Y-%m-%d'),
                            'change_gb': change / (1024**3),
                            'change_pct': change_pct,
                            'prev_size_gb': prev_size / (1024**3),
                            'curr_size_gb': curr_size / (1024**3)
                        })
                
                if size_changes:
                    self.findings.append({
                        'severity': 'HIGH',
                        'category': 'CloudWatch 指标异常',
                        'title': f'检测到 {len(size_changes)} 次显著的存储量下降',
                        'details': size_changes
                    })
            
            # 分析对象数量变化
            if len(count_data) > 1:
                count_changes = []
                for i in range(1, len(count_data)):
                    prev_count = count_data[i-1]['Average']
                    curr_count = count_data[i]['Average']
                    change = curr_count - prev_count
                    
                    if change < -100:  # 减少超过 100 个对象
                        count_changes.append({
                            'date': count_data[i]['Timestamp'].strftime('%Y-%m-%d'),
                            'objects_deleted': int(abs(change)),
                            'prev_count': int(prev_count),
                            'curr_count': int(curr_count)
                        })
                
                if count_changes:
                    self.findings.append({
                        'severity': 'HIGH',
                        'category': 'CloudWatch 指标异常',
                        'title': f'检测到 {len(count_changes)} 次显著的对象数量减少',
                        'details': count_changes
                    })
            
            # 保存原始数据供报告使用
            self.size_data = size_data
            self.count_data = count_data
            
        except Exception as e:
            self.findings.append({
                'severity': 'INFO',
                'category': 'CloudWatch 指标',
                'title': '无法获取 CloudWatch 指标',
                'details': str(e)
            })
    
    def _check_versioning(self):
        """检查版本控制和删除标记"""
        try:
            versioning = self.s3_client.get_bucket_versioning(Bucket=self.bucket_name)
            status = versioning.get('Status', 'Disabled')
            
            if status == 'Enabled':
                # 列出删除标记和版本
                try:
                    response = self.s3_client.list_object_versions(
                        Bucket=self.bucket_name,
                        MaxKeys=1000
                    )
                    
                    delete_markers = [dm for dm in response.get('DeleteMarkers', []) 
                                     if dm.get('IsLatest', False)]
                    versions = response.get('Versions', [])
                    
                    # 统计版本信息
                    total_versions = len(versions)
                    noncurrent_versions = [v for v in versions if not v.get('IsLatest', False)]
                    
                    # 分析非当前版本,查找可能的误删
                    noncurrent_analysis = []
                    noncurrent_by_key = {}
                    for v in noncurrent_versions:
                        key = v['Key']
                        if key not in noncurrent_by_key:
                            noncurrent_by_key[key] = []
                        noncurrent_by_key[key].append({
                            'version_id': v['VersionId'],
                            'last_modified': v['LastModified'],
                            'size': v['Size']
                        })
                    
                    # 找出有多个非当前版本的对象(可能被多次修改/删除)
                    for key, vers in noncurrent_by_key.items():
                        if len(vers) > 0:
                            noncurrent_analysis.append({
                                'key': key,
                                'noncurrent_count': len(vers),
                                'latest_noncurrent': vers[0]['last_modified'].strftime('%Y-%m-%d %H:%M:%S'),
                                'total_size': sum(v['size'] for v in vers)
                            })
                    
                    # 按非当前版本数量排序
                    noncurrent_analysis.sort(key=lambda x: x['noncurrent_count'], reverse=True)
                    
                    version_info = {
                        'status': 'Enabled',
                        'total_versions': total_versions,
                        'noncurrent_versions': len(noncurrent_versions),
                        'delete_markers': len(delete_markers),
                        'objects_with_noncurrent': len(noncurrent_analysis)
                    }
                    
                    # 保存供报告使用
                    self.version_analysis = {
                        'delete_markers': [{
                            'key': dm['Key'],
                            'last_modified': dm['LastModified'].strftime('%Y-%m-%d %H:%M:%S'),
                            'version_id': dm['VersionId']
                        } for dm in delete_markers],
                        'noncurrent_analysis': noncurrent_analysis
                    }
                    
                    if delete_markers:
                        self.findings.append({
                            'severity': 'MEDIUM',
                            'category': '版本控制',
                            'title': f'发现 {len(delete_markers)} 个删除标记',
                            'details': {
                                'message': '这些对象被标记为删除,但可以恢复',
                                'version_info': version_info
                            }
                        })
                    
                    if len(noncurrent_analysis) > 0:
                        self.findings.append({
                            'severity': 'INFO',
                            'category': '版本控制',
                            'title': f'发现 {len(noncurrent_analysis)} 个对象有非当前版本',
                            'details': {
                                'message': f'共 {len(noncurrent_versions)} 个非当前版本,可能包含被覆盖或删除的数据',
                                'version_info': version_info
                            }
                        })
                    else:
                        self.findings.append({
                            'severity': 'INFO',
                            'category': '版本控制',
                            'title': '版本控制已启用',
                            'details': version_info
                        })
                except Exception as e:
                    pass
            else:
                self.findings.append({
                    'severity': 'INFO',
                    'category': '版本控制',
                    'title': '版本控制未启用',
                    'details': '无法追踪删除历史,建议启用版本控制'
                })
                
        except Exception as e:
            pass
    
    def _check_lifecycle_policy(self):
        """检查生命周期策略"""
        try:
            response = self.s3_client.get_bucket_lifecycle_configuration(
                Bucket=self.bucket_name
            )
            
            rules = response.get('Rules', [])
            active_rules = [r for r in rules if r.get('Status') == 'Enabled']
            
            if active_rules:
                deletion_rules = []
                for rule in active_rules:
                    if 'Expiration' in rule or 'NoncurrentVersionExpiration' in rule:
                        deletion_rules.append({
                            'id': rule.get('ID', 'N/A'),
                            'expiration': rule.get('Expiration', {}),
                            'filter': rule.get('Filter', {})
                        })
                
                if deletion_rules:
                    self.findings.append({
                        'severity': 'HIGH',
                        'category': '生命周期策略',
                        'title': f'发现 {len(deletion_rules)} 条自动删除规则',
                        'details': {
                            'message': '这些规则可能导致数据自动删除',
                            'rules': deletion_rules
                        }
                    })
        except Exception as e:
            error_code = e.response.get('Error', {}).get('Code', '') if hasattr(e, 'response') else ''
            if error_code == 'NoSuchLifecycleConfiguration':
                self.findings.append({
                    'severity': 'INFO',
                    'category': '生命周期策略',
                    'title': '未配置生命周期策略',
                    'details': '数据不会被自动删除'
                })
            # 其他错误静默处理
    
    def _check_cloudtrail_events(self):
        """检查 CloudTrail 事件"""
        try:
            start_time = datetime.utcnow() - timedelta(days=90)
            
            # 查询管理事件
            response = self.cloudtrail.lookup_events(
                LookupAttributes=[
                    {'AttributeKey': 'ResourceName', 'AttributeValue': self.bucket_name}
                ],
                StartTime=start_time,
                MaxResults=50
            )
            
            events = response.get('Events', [])
            
            # 分类事件
            lifecycle_events = []
            policy_events = []
            versioning_events = []
            delete_events = []
            other_events = []
            
            for event in events:
                event_name = event['EventName']
                event_data = {
                    'time': event['EventTime'].strftime('%Y-%m-%d %H:%M:%S'),
                    'event': event_name,
                    'user': event.get('Username', 'N/A'),
                    'source_ip': json.loads(event['CloudTrailEvent']).get('sourceIPAddress', 'N/A')
                }
                
                if 'Lifecycle' in event_name:
                    lifecycle_events.append(event_data)
                elif 'Policy' in event_name:
                    policy_events.append(event_data)
                elif 'Versioning' in event_name:
                    versioning_events.append(event_data)
                elif 'Delete' in event_name:
                    delete_events.append(event_data)
                else:
                    other_events.append(event_data)
            
            # 保存所有事件供报告使用
            self.cloudtrail_events = {
                'lifecycle': lifecycle_events,
                'policy': policy_events,
                'versioning': versioning_events,
                'delete': delete_events,
                'other': other_events
            }
            
            if lifecycle_events:
                self.findings.append({
                    'severity': 'MEDIUM',
                    'category': 'CloudTrail 事件',
                    'title': f'发现 {len(lifecycle_events)} 次生命周期策略变更',
                    'details': lifecycle_events
                })
            
            if policy_events:
                self.findings.append({
                    'severity': 'MEDIUM',
                    'category': 'CloudTrail 事件',
                    'title': f'发现 {len(policy_events)} 次策略变更',
                    'details': policy_events
                })
            
            if versioning_events:
                self.findings.append({
                    'severity': 'MEDIUM',
                    'category': 'CloudTrail 事件',
                    'title': f'发现 {len(versioning_events)} 次版本控制变更',
                    'details': versioning_events
                })
            
            if delete_events:
                self.findings.append({
                    'severity': 'HIGH',
                    'category': 'CloudTrail 事件',
                    'title': f'发现 {len(delete_events)} 次删除相关操作',
                    'details': delete_events
                })
            
            # 如果没有任何关键事件,添加信息说明
            if not (lifecycle_events or policy_events or versioning_events or delete_events):
                if events:
                    self.findings.append({
                        'severity': 'INFO',
                        'category': 'CloudTrail 事件',
                        'title': f'过去 90 天有 {len(events)} 个管理事件',
                        'details': '未发现关键的配置变更或删除操作'
                    })
                else:
                    self.findings.append({
                        'severity': 'INFO',
                        'category': 'CloudTrail 事件',
                        'title': '过去 90 天无管理事件',
                        'details': '未发现任何 bucket 级别的管理操作'
                    })
                
        except Exception as e:
            self.findings.append({
                'severity': 'INFO',
                'category': 'CloudTrail 事件',
                'title': '无法获取 CloudTrail 事件',
                'details': str(e)
            })
    
    def _check_bucket_policy(self):
        """检查 Bucket 策略"""
        try:
            response = self.s3_client.get_bucket_policy(Bucket=self.bucket_name)
            policy = json.loads(response['Policy'])
            
            # 检查是否有允许删除的语句
            delete_permissions = []
            for statement in policy.get('Statement', []):
                if statement.get('Effect') == 'Allow':
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    
                    delete_actions = [a for a in actions if 'Delete' in a or a == 's3:*']
                    if delete_actions:
                        delete_permissions.append({
                            'principal': statement.get('Principal', 'N/A'),
                            'actions': delete_actions
                        })
            
            if delete_permissions:
                self.findings.append({
                    'severity': 'MEDIUM',
                    'category': 'Bucket 策略',
                    'title': '发现允许删除操作的策略',
                    'details': delete_permissions
                })
                
        except Exception as e:
            # NoSuchBucketPolicy 或其他错误都静默处理
            pass
    
    def _analyze_current_objects(self):
        """分析当前对象(优化版)"""
        try:
            print("  正在列出对象(可能需要一些时间)...")
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(
                Bucket=self.bucket_name,
                PaginationConfig={'PageSize': 1000}  # 每页1000个对象
            )
            
            total_objects = 0
            total_size = 0
            prefix_stats = defaultdict(lambda: {'count': 0, 'size': 0})
            
            page_count = 0
            for page in pages:
                page_count += 1
                if page_count % 10 == 0:
                    print(f"  已处理 {total_objects:,} 个对象...")
                
                for obj in page.get('Contents', []):
                    total_objects += 1
                    total_size += obj['Size']
                    
                    # 按前缀统计
                    prefix = obj['Key'].split('/')[0] if '/' in obj['Key'] else 'root'
                    prefix_stats[prefix]['count'] += 1
                    prefix_stats[prefix]['size'] += obj['Size']
            
            print(f"  完成! 共 {total_objects:,} 个对象")
            
            self.current_stats = {
                'total_objects': total_objects,
                'total_size_gb': total_size / (1024**3),
                'prefix_stats': dict(prefix_stats)
            }
            
        except Exception as e:
            self.current_stats = {'error': str(e)}
    
    def _generate_report(self):
        """生成分析报告"""
        print(f"\n{'='*80}")
        print("分析结果汇总")
        print(f"{'='*80}\n")
        
        # 按严重程度分组
        high_findings = [f for f in self.findings if f['severity'] == 'HIGH']
        medium_findings = [f for f in self.findings if f['severity'] == 'MEDIUM']
        info_findings = [f for f in self.findings if f['severity'] == 'INFO']
        
        # 显示高危发现
        if high_findings:
            print(f"🔴 高危发现 ({len(high_findings)} 项):")
            print("-" * 80)
            for finding in high_findings:
                print(f"\n  [{finding['category']}] {finding['title']}")
                self._print_details(finding['details'], indent=4)
        
        # 显示中危发现
        if medium_findings:
            print(f"\n🟡 中危发现 ({len(medium_findings)} 项):")
            print("-" * 80)
            for finding in medium_findings:
                print(f"\n  [{finding['category']}] {finding['title']}")
                self._print_details(finding['details'], indent=4)
        
        # 显示信息
        if info_findings:
            print(f"\n🔵 信息 ({len(info_findings)} 项):")
            print("-" * 80)
            for finding in info_findings:
                print(f"\n  [{finding['category']}] {finding['title']}")
                self._print_details(finding['details'], indent=4)
        
        # 当前状态
        print(f"\n{'='*80}")
        print("当前 Bucket 状态")
        print(f"{'='*80}\n")
        if hasattr(self, 'current_stats') and 'error' not in self.current_stats:
            print(f"  对象总数: {self.current_stats['total_objects']:,}")
            print(f"  总大小: {self.current_stats['total_size_gb']:.2f} GB")
        
        # 结论和建议
        print(f"\n{'='*80}")
        print("结论和建议")
        print(f"{'='*80}\n")
        
        if high_findings:
            print("  ⚠️  发现可能导致数据丢失的问题!")
            print("\n  建议立即采取以下措施:")
            print("  1. 检查生命周期策略,确认是否符合预期")
            print("  2. 审查 CloudTrail 事件,确定删除操作的来源")
            print("  3. 如果启用了版本控制,检查是否可以恢复删除的对象")
            print("  4. 启用 CloudTrail 数据事件和 S3 Server Access Logging")
            print("  5. 配置 S3 Inventory 以便未来追踪")
        else:
            print("  ✅ 未发现明显的数据丢失迹象")
            print("\n  建议:")
            print("  1. 启用版本控制以防止意外删除")
            print("  2. 启用 CloudTrail 数据事件监控")
            print("  3. 配置 S3 Inventory 定期生成对象清单")
        
        # 保存报告到 logs 目录
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        json_file = os.path.join(self.logs_dir, f"s3-analysis-{self.bucket_name}-{timestamp}.json")
        md_file = os.path.join(self.logs_dir, f"s3-analysis-{self.bucket_name}-{timestamp}.md")
        
        report_data = {
            'bucket': self.bucket_name,
            'analysis_time': datetime.now().isoformat(),
            'findings': self.findings,
            'current_stats': getattr(self, 'current_stats', {}),
            'cloudwatch_data': {
                'size_data': [{'timestamp': d['Timestamp'].isoformat(), 'bytes': d['Average']} 
                             for d in getattr(self, 'size_data', [])],
                'count_data': [{'timestamp': d['Timestamp'].isoformat(), 'count': d['Average']} 
                              for d in getattr(self, 'count_data', [])]
            }
        }
        
        # 保存 JSON
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        # 生成 Markdown 报告
        self._generate_markdown_report(md_file, report_data)
        
        print(f"\n  JSON 报告已保存至: {json_file}")
        print(f"  Markdown 报告已保存至: {md_file}")
        print(f"\n{'='*80}\n")
    
    def _generate_markdown_report(self, filename, report_data):
        """生成 Markdown 格式报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            # 标题
            f.write(f"# S3 数据丢失分析报告\n\n")
            f.write(f"**Bucket**: `{report_data['bucket']}`  \n")
            f.write(f"**分析时间**: {datetime.fromisoformat(report_data['analysis_time']).strftime('%Y-%m-%d %H:%M:%S')}  \n")
            f.write(f"**分析周期**: 过去 90 天\n\n")
            f.write("---\n\n")
            
            # 执行摘要
            f.write("## 📊 执行摘要\n\n")
            high_findings = [f for f in self.findings if f['severity'] == 'HIGH']
            medium_findings = [f for f in self.findings if f['severity'] == 'MEDIUM']
            info_findings = [f for f in self.findings if f['severity'] == 'INFO']
            
            if high_findings:
                f.write(f"🔴 **高危发现**: {len(high_findings)} 项  \n")
            if medium_findings:
                f.write(f"🟡 **中危发现**: {len(medium_findings)} 项  \n")
            if info_findings:
                f.write(f"🔵 **信息**: {len(info_findings)} 项  \n")
            
            if not high_findings and not medium_findings:
                f.write("✅ **未发现明显的数据丢失迹象**\n")
            f.write("\n---\n\n")
            
            # CloudWatch 指标趋势 - 合并显示
            f.write("## 📈 CloudWatch 指标趋势 (过去 90 天)\n\n")
            
            size_data = report_data['cloudwatch_data']['size_data']
            count_data = report_data['cloudwatch_data']['count_data']
            
            if size_data and count_data:
                f.write("| 日期 | 存储量 (GB) | 存储变化 | 对象数量 | 对象变化 |\n")
                f.write("|------|------------|---------|---------|---------|\n")
                
                # 合并两个数据源
                for i in range(len(size_data)):
                    date = size_data[i]['timestamp'].split('T')[0]
                    size_gb = size_data[i]['bytes'] / (1024**3)
                    count = int(count_data[i]['count']) if i < len(count_data) else 0
                    
                    # 计算存储量变化
                    if i > 0:
                        prev_size = size_data[i-1]['bytes'] / (1024**3)
                        size_change = size_gb - prev_size
                        size_change_pct = (size_change / prev_size * 100) if prev_size > 0 else 0
                        
                        if abs(size_change_pct) > 5:
                            size_change_str = f"{size_change:+.2f} GB ({size_change_pct:+.1f}%)"
                            if size_change_pct < -10:
                                size_change_str = f"⚠️ {size_change_str}"
                        else:
                            size_change_str = "-"
                    else:
                        size_change_str = "-"
                    
                    # 计算对象数量变化
                    if i > 0 and i < len(count_data):
                        prev_count = int(count_data[i-1]['count'])
                        count_change = count - prev_count
                        
                        if abs(count_change) > 10:
                            count_change_str = f"{count_change:+d}"
                            if count_change < -100:
                                count_change_str = f"⚠️ {count_change_str}"
                        else:
                            count_change_str = "-"
                    else:
                        count_change_str = "-"
                    
                    f.write(f"| {date} | {size_gb:.2f} | {size_change_str} | {count:,} | {count_change_str} |\n")
                
                f.write("\n")
            
            f.write("---\n\n")
            
            # CloudTrail 事件汇总
            if hasattr(self, 'cloudtrail_events'):
                ct_events = self.cloudtrail_events
                total_events = sum(len(v) for v in ct_events.values())
                
                if total_events > 0:
                    f.write("## 🔍 CloudTrail 事件汇总 (过去 90 天)\n\n")
                    
                    # 统计概览
                    f.write("### 事件统计\n\n")
                    f.write("| 事件类型 | 数量 |\n")
                    f.write("|---------|------|\n")
                    if ct_events['lifecycle']:
                        f.write(f"| 生命周期策略变更 | {len(ct_events['lifecycle'])} |\n")
                    if ct_events['policy']:
                        f.write(f"| Bucket 策略变更 | {len(ct_events['policy'])} |\n")
                    if ct_events['versioning']:
                        f.write(f"| 版本控制变更 | {len(ct_events['versioning'])} |\n")
                    if ct_events['delete']:
                        f.write(f"| ⚠️ 删除相关操作 | {len(ct_events['delete'])} |\n")
                    if ct_events['other']:
                        f.write(f"| 其他管理操作 | {len(ct_events['other'])} |\n")
                    f.write(f"| **总计** | **{total_events}** |\n\n")
                    
                    # 详细事件列表
                    f.write("### 详细事件\n\n")
                    
                    if ct_events['lifecycle']:
                        f.write(f"#### 生命周期策略变更 ({len(ct_events['lifecycle'])} 次)\n\n")
                        f.write("| 时间 | 操作 | 用户 | 源 IP |\n")
                        f.write("|------|------|------|-------|\n")
                        for e in ct_events['lifecycle']:
                            f.write(f"| {e['time']} | {e['event']} | {e['user']} | {e['source_ip']} |\n")
                        f.write("\n")
                    
                    if ct_events['policy']:
                        f.write(f"#### Bucket 策略变更 ({len(ct_events['policy'])} 次)\n\n")
                        f.write("| 时间 | 操作 | 用户 | 源 IP |\n")
                        f.write("|------|------|------|-------|\n")
                        for e in ct_events['policy']:
                            f.write(f"| {e['time']} | {e['event']} | {e['user']} | {e['source_ip']} |\n")
                        f.write("\n")
                    
                    if ct_events['versioning']:
                        f.write(f"#### 版本控制变更 ({len(ct_events['versioning'])} 次)\n\n")
                        f.write("| 时间 | 操作 | 用户 | 源 IP |\n")
                        f.write("|------|------|------|-------|\n")
                        for e in ct_events['versioning']:
                            f.write(f"| {e['time']} | {e['event']} | {e['user']} | {e['source_ip']} |\n")
                        f.write("\n")
                    
                    if ct_events['delete']:
                        f.write(f"#### ⚠️ 删除相关操作 ({len(ct_events['delete'])} 次)\n\n")
                        f.write("| 时间 | 操作 | 用户 | 源 IP |\n")
                        f.write("|------|------|------|-------|\n")
                        for e in ct_events['delete']:
                            f.write(f"| {e['time']} | {e['event']} | {e['user']} | {e['source_ip']} |\n")
                        f.write("\n")
                    
                    if ct_events['other']:
                        f.write(f"#### 其他管理操作 ({len(ct_events['other'])} 次)\n\n")
                        f.write("<details>\n<summary>点击展开</summary>\n\n")
                        f.write("| 时间 | 操作 | 用户 | 源 IP |\n")
                        f.write("|------|------|------|-------|\n")
                        for e in ct_events['other'][:20]:
                            f.write(f"| {e['time']} | {e['event']} | {e['user']} | {e['source_ip']} |\n")
                        if len(ct_events['other']) > 20:
                            f.write(f"\n*显示前 20 项,共 {len(ct_events['other'])} 项*\n")
                        f.write("\n</details>\n\n")
                    
                    f.write("---\n\n")
            
            # 版本控制分析
            if hasattr(self, 'version_analysis'):
                va = self.version_analysis
                
                if va['delete_markers'] or va['noncurrent_analysis']:
                    f.write("## 📋 版本控制分析\n\n")
                    
                    if va['delete_markers']:
                        f.write(f"### 删除标记 ({len(va['delete_markers'])} 个)\n\n")
                        f.write("⚠️ 这些对象被标记为删除,但可以恢复\n\n")
                        f.write("| 对象键 | 删除时间 | 版本 ID |\n")
                        f.write("|------|---------|----------|\n")
                        for dm in va['delete_markers'][:20]:
                            f.write(f"| `{dm['key']}` | {dm['last_modified']} | `{dm['version_id'][:16]}...` |\n")
                        if len(va['delete_markers']) > 20:
                            f.write(f"\n*显示前 20 个,共 {len(va['delete_markers'])} 个*\n")
                        f.write("\n")
                        
                        f.write("**恢复命令:**\n\n")
                        f.write("```bash\n")
                        f.write("# 恢复单个对象\n")
                        if va['delete_markers']:
                            sample = va['delete_markers'][0]
                            f.write(f"aws s3api delete-object --bucket {self.bucket_name} --key '{sample['key']}' --version-id {sample['version_id']}\n")
                        f.write("```\n\n")
                    
                    if va['noncurrent_analysis']:
                        f.write(f"### 非当前版本分析 ({len(va['noncurrent_analysis'])} 个对象)\n\n")
                        f.write("📄 这些对象有非当前版本,可能包含被覆盖或删除的数据\n\n")
                        
                        f.write("| 对象键 | 非当前版本数 | 最近修改时间 | 总大小 (MB) |\n")
                        f.write("|------|--------------|-------------|-------------|\n")
                        for item in va['noncurrent_analysis'][:20]:
                            size_mb = item['total_size'] / (1024**2)
                            f.write(f"| `{item['key']}` | {item['noncurrent_count']} | {item['latest_noncurrent']} | {size_mb:.2f} |\n")
                        if len(va['noncurrent_analysis']) > 20:
                            f.write(f"\n*显示前 20 个,共 {len(va['noncurrent_analysis'])} 个*\n")
                        f.write("\n")
                        
                        f.write("**查看历史版本:**\n\n")
                        f.write("```bash\n")
                        if va['noncurrent_analysis']:
                            sample_key = va['noncurrent_analysis'][0]['key']
                            f.write(f"# 列出对象的所有版本\n")
                            f.write(f"aws s3api list-object-versions --bucket {self.bucket_name} --prefix '{sample_key}'\n\n")
                            f.write(f"# 恢复到特定版本\n")
                            f.write(f"aws s3api copy-object --bucket {self.bucket_name} --copy-source {self.bucket_name}/{sample_key}?versionId=VERSION_ID --key '{sample_key}'\n")
                        f.write("```\n\n")
                    
                    f.write("---\n\n")
            
            # 详细发现
            if high_findings:
                f.write("## 🔴 高危发现\n\n")
                for finding in high_findings:
                    f.write(f"### [{finding['category']}] {finding['title']}\n\n")
                    self._write_markdown_details(f, finding['details'])
                    f.write("\n")
            
            if medium_findings:
                f.write("## 🟡 中危发现\n\n")
                for finding in medium_findings:
                    f.write(f"### [{finding['category']}] {finding['title']}\n\n")
                    self._write_markdown_details(f, finding['details'])
                    f.write("\n")
            
            if info_findings:
                f.write("## 🔵 信息\n\n")
                for finding in info_findings:
                    f.write(f"### [{finding['category']}] {finding['title']}\n\n")
                    self._write_markdown_details(f, finding['details'])
                    f.write("\n")
            
            # 当前状态
            f.write("---\n\n")
            f.write("## 📦 当前 Bucket 状态\n\n")
            
            stats = report_data.get('current_stats', {})
            if stats.get('skipped'):
                f.write("⏭️ **跳过对象统计** (使用了 --skip-listing 参数)\n\n")
                f.write("提示: 如需详细的对象统计,请不带 --skip-listing 参数重新运行\n\n")
            elif 'error' not in stats:
                f.write(f"- **对象总数**: {stats.get('total_objects', 0):,}\n")
                f.write(f"- **总大小**: {stats.get('total_size_gb', 0):.2f} GB\n\n")
                
                prefix_stats = stats.get('prefix_stats', {})
                if prefix_stats:
                    f.write("### 按前缀统计\n\n")
                    f.write("| 前缀 | 对象数 | 大小 (GB) |\n")
                    f.write("|------|--------|----------|\n")
                    
                    sorted_prefixes = sorted(prefix_stats.items(), 
                                           key=lambda x: x[1]['size'], 
                                           reverse=True)
                    
                    for prefix, data in sorted_prefixes[:10]:
                        f.write(f"| `{prefix}` | {data['count']:,} | {data['size']/(1024**3):.2f} |\n")
                    
                    if len(sorted_prefixes) > 10:
                        f.write(f"| ... | ... | ... |\n")
                        f.write(f"\n*显示前 10 个最大的前缀*\n")
                    f.write("\n")
            
            # 结论和建议
            f.write("---\n\n")
            f.write("## 💡 结论和建议\n\n")
            
            if high_findings:
                f.write("### ⚠️ 发现可能导致数据丢失的问题!\n\n")
                f.write("**建议立即采取以下措施:**\n\n")
                f.write("1. 检查生命周期策略,确认是否符合预期\n")
                f.write("2. 审查 CloudTrail 事件,确定删除操作的来源\n")
                f.write("3. 如果启用了版本控制,检查是否可以恢复删除的对象\n")
                f.write("4. 启用 CloudTrail 数据事件和 S3 Server Access Logging\n")
                f.write("5. 配置 S3 Inventory 以便未来追踪\n")
            else:
                f.write("### ✅ 未发现明显的数据丢失迹象\n\n")
                f.write("**预防措施建议:**\n\n")
                f.write("1. 启用版本控制以防止意外删除\n")
                f.write("2. 启用 CloudTrail 数据事件监控\n")
                f.write("3. 配置 S3 Inventory 定期生成对象清单\n")
                f.write("4. 设置 CloudWatch 告警监控存储量和对象数量变化\n")
                f.write("5. 定期审查 Bucket 策略和生命周期配置\n")
            
            f.write("\n---\n\n")
            f.write("## 📚 参考文档\n\n")
            f.write("- [S3 CloudWatch Metrics](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cloudwatch-monitoring.html)\n")
            f.write("- [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)\n")
            f.write("- [S3 Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)\n")
            f.write("- [CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html)\n")
            f.write("- [S3 Inventory](https://docs.aws.amazon.com/AmazonS3/latest/userguide/storage-inventory.html)\n")
    
    def _write_markdown_details(self, f, details):
        """写入 Markdown 格式的详细信息"""
        if isinstance(details, str):
            f.write(f"{details}\n\n")
        elif isinstance(details, dict):
            if 'message' in details:
                f.write(f"{details['message']}\n\n")
            
            for key, value in details.items():
                if key == 'message':
                    continue
                    
                if isinstance(value, list) and value:
                    f.write(f"**{key}:**\n\n")
                    
                    if isinstance(value[0], dict):
                        # 表格格式
                        if len(value) > 0:
                            keys = list(value[0].keys())
                            f.write("| " + " | ".join(keys) + " |\n")
                            f.write("|" + "------|" * len(keys) + "\n")
                            
                            for item in value[:10]:
                                row = []
                                for k in keys:
                                    v = item.get(k, '')
                                    if isinstance(v, dict):
                                        v = json.dumps(v, ensure_ascii=False)
                                    row.append(str(v))
                                f.write("| " + " | ".join(row) + " |\n")
                            
                            if len(value) > 10:
                                f.write(f"\n*显示前 10 项,共 {len(value)} 项*\n")
                    else:
                        for item in value[:10]:
                            f.write(f"- {item}\n")
                        if len(value) > 10:
                            f.write(f"\n*显示前 10 项,共 {len(value)} 项*\n")
                    f.write("\n")
                elif isinstance(value, dict):
                    f.write(f"**{key}:**\n\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```\n\n")
                else:
                    f.write(f"- **{key}**: {value}\n")
        elif isinstance(details, list):
            for item in details[:10]:
                if isinstance(item, dict):
                    for k, v in item.items():
                        f.write(f"- **{k}**: {v}\n")
                    f.write("\n")
                else:
                    f.write(f"- {item}\n")
            if len(details) > 10:
                f.write(f"\n*显示前 10 项,共 {len(details)} 项*\n")
    
    def _print_details(self, details, indent=2):
        """打印详细信息"""
        prefix = " " * indent
        if isinstance(details, dict):
            for key, value in details.items():
                if isinstance(value, (list, dict)):
                    print(f"{prefix}{key}:")
                    self._print_details(value, indent + 2)
                else:
                    print(f"{prefix}{key}: {value}")
        elif isinstance(details, list):
            for item in details[:5]:  # 只显示前 5 项
                if isinstance(item, dict):
                    for key, value in item.items():
                        print(f"{prefix}{key}: {value}")
                    print()
                else:
                    print(f"{prefix}- {item}")
            if len(details) > 5:
                print(f"{prefix}... (还有 {len(details) - 5} 项)")
        else:
            print(f"{prefix}{details}")


def main():
    parser = argparse.ArgumentParser(
        description='S3 数据丢失分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python s3_deletion_analyzer.py --bucket veeam-backup-bucket
  
  # 指定区域
  python s3_deletion_analyzer.py --bucket my-bucket --region us-west-2
  
  # 跳过对象列表(适用于大型 bucket)
  python s3_deletion_analyzer.py --bucket large-bucket --skip-listing
  
注意:
  - 报告将保存在当前目录的 logs/ 子目录下
  - 对于包含数百万对象的 bucket,建议使用 --skip-listing 参数
        """
    )
    parser.add_argument('--bucket', required=True, help='S3 bucket 名称')
    parser.add_argument('--region', default='us-east-1', help='AWS 区域 (默认: us-east-1)')
    parser.add_argument('--skip-listing', action='store_true', 
                       help='跳过对象列表统计(适用于大型 bucket,可显著加快分析速度)')
    
    args = parser.parse_args()
    
    try:
        analyzer = S3DeletionAnalyzer(args.bucket, args.region, args.skip_listing)
        analyzer.analyze()
    except Exception as e:
        print(f"\n错误: {str(e)}\n")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
