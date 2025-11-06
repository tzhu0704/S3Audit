#!/usr/bin/env python3
"""
测试S3诊断工具的功能
"""

import boto3
import json
import tempfile
import os
from moto import mock_aws
from s3_deletion_diagnostic import S3DeletionDiagnostic



def test_diagnostic_tool():
    """测试诊断工具"""
    
    print("🧪 开始测试S3诊断工具...")
    
    with mock_aws():
        # 创建mock S3客户端
        s3_client = boto3.client('s3', region_name='us-east-1')
        bucket_name = 'test-diagnostic-bucket'
        
        # 创建测试bucket
        s3_client.create_bucket(Bucket=bucket_name)
        
        # 设置生命周期策略
        lifecycle_config = {
            'Rules': [
                {
                    'ID': 'test-delete-rule',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'logs/'},
                    'Expiration': {'Days': 30},
                    'NoncurrentVersionExpiration': {'NoncurrentDays': 7}
                },
                {
                    'ID': 'test-transition-rule', 
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'archive/'},
                    'Transitions': [
                        {
                            'Days': 30,
                            'StorageClass': 'STANDARD_IA'
                        }
                    ]
                }
            ]
        }
        
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_config
        )
        
        # 启用版本控制
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        
        # 设置bucket策略
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:user/testuser"},
                    "Action": ["s3:DeleteObject", "s3:DeleteObjectVersion"],
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                }
            ]
        }
        
        s3_client.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(bucket_policy)
        )
        
        print(f"✅ 创建测试bucket: {bucket_name}")
        print("✅ 配置生命周期策略、版本控制和bucket策略")
        
        # 创建诊断实例并使用mock客户端
        diagnostic = S3DeletionDiagnostic(bucket_name, region='us-east-1')
        diagnostic.s3_client = s3_client
        
        # 运行诊断
        report = diagnostic.run_diagnostic()
    
    if report:
        print("\n📊 诊断完成，生成报告:")
        diagnostic.print_report()
        
        # 验证报告内容
        risks = report['risks']
        assert len(risks) > 0, "应该检测到风险"
        
        # 检查是否检测到生命周期风险
        lifecycle_risks = [r for r in risks if '生命周期' in r['type']]
        assert len(lifecycle_risks) > 0, "应该检测到生命周期风险"
        
        # 检查是否检测到版本控制
        version_risks = [r for r in risks if '版本控制' in r['type']]
        assert len(version_risks) > 0, "应该检测到版本控制配置"
        
        # 检查是否检测到bucket策略风险
        policy_risks = [r for r in risks if 'Bucket策略' in r['type']]
        assert len(policy_risks) > 0, "应该检测到bucket策略风险"
        
        print("✅ 所有测试通过!")
        
        # 保存测试报告
        with open('/tmp/test_diagnostic_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("📄 测试报告保存到: /tmp/test_diagnostic_report.json")
        
    else:
        print("❌ 诊断失败")

def test_real_bucket():
    """测试真实bucket（需要用户提供bucket名称）"""
    
    print("\n🔍 测试真实S3 bucket...")
    print("请确保:")
    print("1. AWS凭证已配置")
    print("2. 有访问目标bucket的权限")
    
    # 这里可以测试真实的bucket
    # bucket_name = input("请输入要测试的bucket名称 (回车跳过): ").strip()
    
    # if bucket_name:
    #     try:
    #         diagnostic = S3DeletionDiagnostic(bucket_name)
    #         report = diagnostic.run_diagnostic()
    #         
    #         if report:
    #             diagnostic.print_report()
    #         
    #     except Exception as e:
    #         print(f"❌ 真实bucket测试失败: {str(e)}")
    # else:
    #     print("⏭️  跳过真实bucket测试")

if __name__ == '__main__':
    try:
        # 测试mock环境
        test_diagnostic_tool()
        
        # 测试真实环境（可选）
        test_real_bucket()
        
        print("\n🎉 测试完成!")
        
    except ImportError as e:
        if 'moto' in str(e):
            print("❌ 缺少moto库，请安装: pip install moto[s3]")
        else:
            print(f"❌ 导入错误: {str(e)}")
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")