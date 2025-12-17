#!/usr/bin/env python3
"""
S3 非当前版本清理工具
安全删除S3 bucket中的非当前版本，节省存储成本
"""

import boto3
import argparse
import json
from datetime import datetime
from collections import defaultdict

class S3VersionCleaner:
    def __init__(self, bucket_name, region='us-east-1', dry_run=True):
        self.bucket_name = bucket_name
        self.region = region
        self.dry_run = dry_run
        self.s3_client = boto3.client('s3', region_name=region)
        
        # 统计信息
        self.stats = {
            'total_versions_scanned': 0,
            'noncurrent_versions_found': 0,
            'noncurrent_versions_deleted': 0,
            'delete_markers_found': 0,
            'delete_markers_deleted': 0,
            'storage_saved_bytes': 0,
            'objects_processed': 0,
            'errors': []
        }
    
    def analyze_versions(self):
        """分析版本情况"""
        print(f"\n{'='*80}")
        print(f"S3 版本分析")
        print(f"Bucket: {self.bucket_name}")
        print(f"模式: {'预览模式 (不会删除)' if self.dry_run else '删除模式 (会实际删除)'}")
        print(f"{'='*80}\n")
        
        print("正在扫描所有版本...")
        
        paginator = self.s3_client.get_paginator('list_object_versions')
        page_iterator = paginator.paginate(Bucket=self.bucket_name)
        
        objects_with_versions = defaultdict(list)
        delete_markers = []
        
        page_count = 0
        for page in page_iterator:
            page_count += 1
            if page_count % 10 == 0:
                print(f"  已处理 {page_count} 页...")
            
            # 处理版本
            for version in page.get('Versions', []):
                self.stats['total_versions_scanned'] += 1
                key = version['Key']
                objects_with_versions[key].append(version)
            
            # 处理删除标记
            for dm in page.get('DeleteMarkers', []):
                self.stats['delete_markers_found'] += 1
                delete_markers.append(dm)
        
        print(f"扫描完成！共处理 {page_count} 页")
        print(f"发现 {len(objects_with_versions)} 个对象")
        print(f"发现 {self.stats['delete_markers_found']} 个删除标记")
        
        return objects_with_versions, delete_markers
    
    def clean_noncurrent_versions(self, keep_versions=1):
        """清理非当前版本"""
        objects_with_versions, delete_markers = self.analyze_versions()
        
        print(f"\n开始清理非当前版本（保留最新 {keep_versions} 个版本）...")
        
        # 清理非当前版本
        for key, versions in objects_with_versions.items():
            self.stats['objects_processed'] += 1
            
            # 按时间排序，最新的在前
            versions.sort(key=lambda x: x['LastModified'], reverse=True)
            
            # 保留最新的版本，删除其余的
            versions_to_delete = versions[keep_versions:]
            
            if versions_to_delete:
                self.stats['noncurrent_versions_found'] += len(versions_to_delete)
                
                for version in versions_to_delete:
                    self.stats['storage_saved_bytes'] += version['Size']
                    
                    if not self.dry_run:
                        try:
                            self.s3_client.delete_object(
                                Bucket=self.bucket_name,
                                Key=key,
                                VersionId=version['VersionId']
                            )
                            self.stats['noncurrent_versions_deleted'] += 1
                        except Exception as e:
                            error_msg = f"删除失败 {key} (版本 {version['VersionId']}): {str(e)}"
                            self.stats['errors'].append(error_msg)
                            print(f"  ❌ {error_msg}")
                    else:
                        self.stats['noncurrent_versions_deleted'] += 1
                
                if self.stats['objects_processed'] % 100 == 0:
                    print(f"  已处理 {self.stats['objects_processed']} 个对象...")
        
        # 清理孤立的删除标记（可选）
        if delete_markers:
            print(f"\n发现 {len(delete_markers)} 个删除标记")
            print("注意：删除标记通常应该保留，除非你确定要恢复这些对象")
        
        return self.stats
    
    def clean_delete_markers(self):
        """清理删除标记（恢复被软删除的对象）"""
        _, delete_markers = self.analyze_versions()
        
        if not delete_markers:
            print("没有发现删除标记")
            return
        
        print(f"\n清理 {len(delete_markers)} 个删除标记（恢复软删除的对象）...")
        
        for dm in delete_markers:
            if not self.dry_run:
                try:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=dm['Key'],
                        VersionId=dm['VersionId']
                    )
                    self.stats['delete_markers_deleted'] += 1
                    print(f"  ✓ 恢复对象: {dm['Key']}")
                except Exception as e:
                    error_msg = f"恢复失败 {dm['Key']}: {str(e)}"
                    self.stats['errors'].append(error_msg)
                    print(f"  ❌ {error_msg}")
            else:
                self.stats['delete_markers_deleted'] += 1
                print(f"  [预览] 将恢复对象: {dm['Key']}")
    
    def generate_lifecycle_policy(self):
        """生成生命周期策略建议"""
        policy = {
            "Rules": [
                {
                    "ID": "DeleteNoncurrentVersions",
                    "Status": "Enabled",
                    "Filter": {},
                    "NoncurrentVersionExpiration": {
                        "NoncurrentDays": 30
                    }
                },
                {
                    "ID": "CleanupIncompleteUploads",
                    "Status": "Enabled",
                    "Filter": {},
                    "AbortIncompleteMultipartUpload": {
                        "DaysAfterInitiation": 7
                    }
                }
            ]
        }
        
        print("\n建议的生命周期策略（防止未来版本堆积）：")
        print(json.dumps(policy, indent=2, ensure_ascii=False))
        
        print("\n应用此策略的命令：")
        print(f"aws s3api put-bucket-lifecycle-configuration --bucket {self.bucket_name} --lifecycle-configuration file://lifecycle-policy.json")
        
        return policy
    
    def print_summary(self):
        """打印清理摘要"""
        print(f"\n{'='*80}")
        print("清理摘要")
        print(f"{'='*80}")
        
        print(f"扫描的版本总数: {self.stats['total_versions_scanned']:,}")
        print(f"处理的对象数: {self.stats['objects_processed']:,}")
        print(f"发现的非当前版本: {self.stats['noncurrent_versions_found']:,}")
        print(f"{'删除' if not self.dry_run else '将删除'}的非当前版本: {self.stats['noncurrent_versions_deleted']:,}")
        print(f"发现的删除标记: {self.stats['delete_markers_found']:,}")
        print(f"{'删除' if not self.dry_run else '将删除'}的删除标记: {self.stats['delete_markers_deleted']:,}")
        
        # 存储节省计算
        storage_saved_gb = self.stats['storage_saved_bytes'] / (1024**3)
        monthly_savings = storage_saved_gb * 0.023  # S3 标准存储价格
        
        print(f"\n存储节省:")
        print(f"  节省存储空间: {storage_saved_gb:.2f} GB")
        print(f"  预计月度节省: ${monthly_savings:.2f}")
        print(f"  预计年度节省: ${monthly_savings * 12:.2f}")
        
        if self.stats['errors']:
            print(f"\n错误 ({len(self.stats['errors'])} 个):")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")
            if len(self.stats['errors']) > 10:
                print(f"  ... 还有 {len(self.stats['errors']) - 10} 个错误")
        
        if self.dry_run:
            print(f"\n⚠️  这是预览模式，没有实际删除任何内容")
            print(f"要执行实际删除，请使用 --execute 参数")


def main():
    parser = argparse.ArgumentParser(
        description='S3 非当前版本清理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览清理效果（推荐先运行）
  python cleanup_noncurrent_versions.py --bucket tzhu-inventory1 --preview
  
  # 执行清理，保留最新1个版本
  python cleanup_noncurrent_versions.py --bucket tzhu-inventory1 --execute --keep-versions 1
  
  # 清理非当前版本并恢复软删除的对象
  python cleanup_noncurrent_versions.py --bucket tzhu-inventory1 --execute --clean-delete-markers
  
  # 生成生命周期策略建议
  python cleanup_noncurrent_versions.py --bucket tzhu-inventory1 --generate-policy
        """
    )
    
    parser.add_argument('--bucket', required=True, help='S3 bucket 名称')
    parser.add_argument('--region', default='us-east-1', help='AWS 区域')
    parser.add_argument('--preview', action='store_true', help='预览模式（不实际删除）')
    parser.add_argument('--execute', action='store_true', help='执行模式（实际删除）')
    parser.add_argument('--keep-versions', type=int, default=1, help='保留的版本数量（默认1个）')
    parser.add_argument('--clean-delete-markers', action='store_true', help='清理删除标记（恢复软删除的对象）')
    parser.add_argument('--generate-policy', action='store_true', help='生成生命周期策略建议')
    
    args = parser.parse_args()
    
    # 默认为预览模式
    dry_run = not args.execute
    
    if args.execute and not args.preview:
        confirm = input(f"\n⚠️  警告：这将永久删除 {args.bucket} 中的非当前版本！\n输入 'DELETE' 确认: ")
        if confirm != 'DELETE':
            print("操作已取消")
            return 1
    
    try:
        cleaner = S3VersionCleaner(args.bucket, args.region, dry_run)
        
        if args.generate_policy:
            cleaner.generate_lifecycle_policy()
            return 0
        
        # 清理非当前版本
        cleaner.clean_noncurrent_versions(args.keep_versions)
        
        # 清理删除标记（如果指定）
        if args.clean_delete_markers:
            cleaner.clean_delete_markers()
        
        # 打印摘要
        cleaner.print_summary()
        
        # 生成策略建议
        if not dry_run:
            print("\n" + "="*80)
            cleaner.generate_lifecycle_policy()
        
    except Exception as e:
        print(f"\n错误: {str(e)}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())