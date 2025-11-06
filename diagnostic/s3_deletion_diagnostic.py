#!/usr/bin/env python3
"""
S3 Bucket 数据删除配置诊断工具
检查可能导致数据自动删除的所有配置
"""

import boto3
import json
import argparse
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError

class S3DeletionDiagnostic:
    def __init__(self, bucket_name, region=None):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client('s3', region_name=region)
        self.report = {
            'bucket_name': bucket_name,
            'scan_time': datetime.now().isoformat(),
            'risks': [],
            'configurations': {}
        }

    def check_lifecycle_policies(self):
        """检查生命周期策略"""
        try:
            response = self.s3_client.get_bucket_lifecycle_configuration(Bucket=self.bucket_name)
            rules = response.get('Rules', [])
            
            if not rules:
                return
                
            self.report['configurations']['lifecycle_policies'] = rules
            
            for rule in rules:
                rule_id = rule.get('ID', 'Unknown')
                status = rule.get('Status', 'Unknown')
                
                if status != 'Enabled':
                    continue
                    
                # 检查对象过期
                if 'Expiration' in rule:
                    exp = rule['Expiration']
                    if 'Days' in exp:
                        self.report['risks'].append({
                            'type': '生命周期对象过期',
                            'severity': 'HIGH',
                            'rule_id': rule_id,
                            'description': f'对象将在 {exp["Days"]} 天后自动删除',
                            'impact': '当前版本对象会被永久删除'
                        })
                    if 'Date' in exp:
                        self.report['risks'].append({
                            'type': '生命周期对象过期',
                            'severity': 'HIGH', 
                            'rule_id': rule_id,
                            'description': f'对象将在 {exp["Date"]} 自动删除',
                            'impact': '当前版本对象会被永久删除'
                        })
                
                # 检查非当前版本过期
                if 'NoncurrentVersionExpiration' in rule:
                    nv_exp = rule['NoncurrentVersionExpiration']
                    days = nv_exp.get('NoncurrentDays', 0)
                    self.report['risks'].append({
                        'type': '非当前版本过期',
                        'severity': 'MEDIUM',
                        'rule_id': rule_id,
                        'description': f'非当前版本将在 {days} 天后自动删除',
                        'impact': '历史版本会被永久删除，可能影响数据恢复'
                    })
                
                # 检查删除标记过期
                if rule.get('ExpiredObjectDeleteMarker'):
                    self.report['risks'].append({
                        'type': '删除标记清理',
                        'severity': 'LOW',
                        'rule_id': rule_id,
                        'description': '孤立的删除标记会被自动清理',
                        'impact': '影响对象计数统计，但不删除实际数据'
                    })
                
                # 检查存储类别转换
                if 'Transitions' in rule:
                    for transition in rule['Transitions']:
                        storage_class = transition.get('StorageClass')
                        days = transition.get('Days', 0)
                        self.report['risks'].append({
                            'type': '存储类别转换',
                            'severity': 'LOW',
                            'rule_id': rule_id,
                            'description': f'{days} 天后转换到 {storage_class}',
                            'impact': '数据仍存在但访问成本和延迟可能变化'
                        })
                        
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchLifecycleConfiguration':
                self.report['errors'] = self.report.get('errors', [])
                self.report['errors'].append(f'生命周期策略检查失败: {str(e)}')

    def check_versioning(self):
        """检查版本控制配置"""
        try:
            response = self.s3_client.get_bucket_versioning(Bucket=self.bucket_name)
            versioning_status = response.get('Status', 'Disabled')
            mfa_delete = response.get('MfaDelete', 'Disabled')
            
            self.report['configurations']['versioning'] = {
                'status': versioning_status,
                'mfa_delete': mfa_delete
            }
            
            if versioning_status == 'Enabled':
                self.report['risks'].append({
                    'type': '版本控制已启用',
                    'severity': 'INFO',
                    'description': '启用版本控制，旧版本会累积',
                    'impact': '存储成本增加，需配合生命周期策略管理旧版本'
                })
                
            if mfa_delete == 'Enabled':
                self.report['risks'].append({
                    'type': 'MFA删除保护',
                    'severity': 'INFO', 
                    'description': '启用MFA删除保护',
                    'impact': '删除版本需要MFA验证，提供额外安全保护'
                })
                
        except ClientError as e:
            self.report['errors'] = self.report.get('errors', [])
            self.report['errors'].append(f'版本控制检查失败: {str(e)}')

    def check_replication(self):
        """检查复制配置"""
        try:
            response = self.s3_client.get_bucket_replication(Bucket=self.bucket_name)
            replication_config = response.get('ReplicationConfiguration', {})
            
            if replication_config:
                self.report['configurations']['replication'] = replication_config
                rules = replication_config.get('Rules', [])
                
                for rule in rules:
                    rule_id = rule.get('ID', 'Unknown')
                    status = rule.get('Status', 'Unknown')
                    
                    if status == 'Enabled':
                        dest = rule.get('Destination', {})
                        bucket = dest.get('Bucket', 'Unknown')
                        
                        # 检查删除复制
                        delete_marker_replication = rule.get('DeleteMarkerReplication', {})
                        if delete_marker_replication.get('Status') == 'Enabled':
                            self.report['risks'].append({
                                'type': '删除标记复制',
                                'severity': 'MEDIUM',
                                'rule_id': rule_id,
                                'description': f'删除标记会复制到 {bucket}',
                                'impact': '源bucket删除操作会影响目标bucket'
                            })
                        
                        replica_modifications = rule.get('ReplicaModifications', {})
                        if replica_modifications.get('Status') == 'Enabled':
                            self.report['risks'].append({
                                'type': '副本修改复制',
                                'severity': 'MEDIUM',
                                'rule_id': rule_id,
                                'description': f'副本修改会复制到 {bucket}',
                                'impact': '目标bucket的修改可能影响源数据'
                            })
                            
        except ClientError as e:
            if e.response['Error']['Code'] != 'ReplicationConfigurationNotFoundError':
                self.report['errors'] = self.report.get('errors', [])
                self.report['errors'].append(f'复制配置检查失败: {str(e)}')

    def check_intelligent_tiering(self):
        """检查智能分层配置"""
        try:
            response = self.s3_client.list_bucket_intelligent_tiering_configurations(
                Bucket=self.bucket_name
            )
            configs = response.get('IntelligentTieringConfigurationList', [])
            
            if configs:
                self.report['configurations']['intelligent_tiering'] = configs
                
                for config in configs:
                    config_id = config.get('Id', 'Unknown')
                    status = config.get('Status', 'Unknown')
                    
                    if status == 'Enabled':
                        self.report['risks'].append({
                            'type': '智能分层',
                            'severity': 'LOW',
                            'config_id': config_id,
                            'description': '对象会自动在存储类别间移动',
                            'impact': '访问模式变化时存储成本和访问延迟可能变化'
                        })
                        
        except ClientError as e:
            self.report['errors'] = self.report.get('errors', [])
            self.report['errors'].append(f'智能分层检查失败: {str(e)}')

    def check_bucket_policy(self):
        """检查bucket策略中的删除权限"""
        try:
            response = self.s3_client.get_bucket_policy(Bucket=self.bucket_name)
            policy = json.loads(response['Policy'])
            
            self.report['configurations']['bucket_policy'] = policy
            
            for statement in policy.get('Statement', []):
                actions = statement.get('Action', [])
                if isinstance(actions, str):
                    actions = [actions]
                
                delete_actions = [action for action in actions if 'Delete' in action or action == 's3:*']
                
                if delete_actions and statement.get('Effect') == 'Allow':
                    principals = statement.get('Principal', {})
                    self.report['risks'].append({
                        'type': 'Bucket策略删除权限',
                        'severity': 'MEDIUM',
                        'description': f'允许删除操作: {", ".join(delete_actions)}',
                        'principals': str(principals),
                        'impact': '指定的主体可以删除bucket中的对象'
                    })
                    
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchBucketPolicy':
                self.report['errors'] = self.report.get('errors', [])
                self.report['errors'].append(f'Bucket策略检查失败: {str(e)}')

    def run_diagnostic(self):
        """运行完整诊断"""
        print(f"正在诊断 S3 bucket: {self.bucket_name}")
        
        try:
            # 验证bucket存在
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            print(f"错误: 无法访问bucket {self.bucket_name}: {str(e)}")
            return None
        
        print("检查生命周期策略...")
        self.check_lifecycle_policies()
        
        print("检查版本控制...")
        self.check_versioning()
        
        print("检查复制配置...")
        self.check_replication()
        
        print("检查智能分层...")
        self.check_intelligent_tiering()
        
        print("检查bucket策略...")
        self.check_bucket_policy()
        
        return self.report

    def print_report(self):
        """打印诊断报告"""
        print("\n" + "="*60)
        print(f"S3 BUCKET 数据删除风险诊断报告")
        print("="*60)
        print(f"Bucket: {self.report['bucket_name']}")
        print(f"扫描时间: {self.report['scan_time']}")
        
        # 打印风险汇总
        risks = self.report['risks']
        if not risks:
            print("\n✅ 未发现数据自动删除风险")
            return
            
        risk_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0, 'INFO': 0}
        for risk in risks:
            risk_counts[risk['severity']] += 1
            
        print(f"\n📊 风险汇总:")
        print(f"   🔴 高风险: {risk_counts['HIGH']}")
        print(f"   🟡 中风险: {risk_counts['MEDIUM']}")  
        print(f"   🟢 低风险: {risk_counts['LOW']}")
        print(f"   ℹ️  信息: {risk_counts['INFO']}")
        
        # 打印详细风险
        print(f"\n📋 详细风险列表:")
        for i, risk in enumerate(risks, 1):
            severity_icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢', 'INFO': 'ℹ️'}
            print(f"\n{i}. {severity_icon[risk['severity']]} {risk['type']} [{risk['severity']}]")
            print(f"   描述: {risk['description']}")
            print(f"   影响: {risk['impact']}")
            if 'rule_id' in risk:
                print(f"   规则ID: {risk['rule_id']}")
        
        # 打印错误
        if 'errors' in self.report:
            print(f"\n⚠️  检查过程中的错误:")
            for error in self.report['errors']:
                print(f"   - {error}")

def main():
    parser = argparse.ArgumentParser(description='S3 Bucket 数据删除配置诊断工具')
    parser.add_argument('bucket_name', help='S3 bucket名称')
    parser.add_argument('--region', help='AWS区域')
    parser.add_argument('--output', help='输出JSON报告到文件')
    
    args = parser.parse_args()
    
    try:
        diagnostic = S3DeletionDiagnostic(args.bucket_name, args.region)
        report = diagnostic.run_diagnostic()
        
        if report:
            diagnostic.print_report()
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
                print(f"\n📄 详细报告已保存到: {args.output}")
                
    except NoCredentialsError:
        print("错误: 未找到AWS凭证，请配置AWS CLI或设置环境变量")
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == '__main__':
    main()