#!/usr/bin/env python3
"""
S3 Server Access Log 分析 Web 应用
"""
import streamlit as st
import boto3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

# 页面配置
st.set_page_config(
    page_title="S3 访问日志分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"  # 默认展开侧边栏
)

# 编译正则表达式提升性能
LOG_PATTERN = re.compile(r'(\S+) (\S+) \[(.*?)\] (\S+) (\S+) (\S+) (\S+) (\S+) "(\S+) (\S+) (\S+)" (\S+) (\S+) (\S+) (\S+) (\S+) (\S+) "([^"]*)" "([^"]*)" (\S+)')

def parse_s3_log_line(line):
    """解析 S3 访问日志行"""
    match = LOG_PATTERN.match(line)
    if match:
        return {
            'bucket_owner': match.group(1),
            'bucket': match.group(2),
            'time': match.group(3),
            'remote_ip': match.group(4),
            'requester': match.group(5),
            'request_id': match.group(6),
            'operation': match.group(7),
            'key': match.group(8),
            'request_uri': match.group(9),
            'http_status': match.group(12),
            'error_code': match.group(13),
            'bytes_sent': match.group(14),
            'object_size': match.group(15),
            'total_time': match.group(16),
            'turn_around_time': match.group(17),
            'referer': match.group(18),
            'user_agent': match.group(19),
            'version_id': match.group(20)
        }
    return None

def process_log_file(s3_client, bucket, key):
    """处理单个日志文件"""
    try:
        log_obj = s3_client.get_object(Bucket=bucket, Key=key)
        content = log_obj['Body'].read().decode('utf-8')
        
        logs = []
        for line in content.strip().split('\n'):
            if line:
                parsed = parse_s3_log_line(line)
                if parsed:
                    logs.append(parsed)
        return logs
    except:
        return []

@st.cache_data(ttl=300)
def load_s3_logs(bucket, prefix, max_files=100, days_back=None):
    """从 S3 加载日志"""
    s3 = boto3.client('s3')
    
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_files)
        
        if 'Contents' not in response:
            return pd.DataFrame()
        
        # 先按文件时间过滤
        log_files = [obj for obj in response['Contents'] if obj['Size'] > 0]
        
        if days_back:
            from datetime import datetime, timedelta, timezone
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
            log_files = [obj for obj in log_files if obj['LastModified'] >= cutoff_time]
        
        if not log_files:
            return pd.DataFrame()
        
        all_logs = []
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(process_log_file, s3, bucket, obj['Key']) for obj in log_files]
            for future in as_completed(futures):
                all_logs.extend(future.result())
        
        if all_logs:
            df = pd.DataFrame(all_logs)
            df['time'] = pd.to_datetime(df['time'], format='%d/%b/%Y:%H:%M:%S %z', errors='coerce')
            df['bytes_sent'] = pd.to_numeric(df['bytes_sent'], errors='coerce').fillna(0)
            df['http_status'] = df['http_status'].astype(str)
            return df
        
        return pd.DataFrame()
    
    except Exception as e:
        st.error(f"加载日志失败: {str(e)}")
        return pd.DataFrame()

@st.cache_data
def get_bucket_list():
    """获取可用的 bucket 列表"""
    try:
        s3 = boto3.client('s3')
        response = s3.list_buckets()
        return [bucket['Name'] for bucket in response['Buckets']]
    except:
        return []

# 主应用
def main():
    st.title("📊 S3 Server Access Log 分析器")
    st.markdown("---")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 配置")
        
        # Bucket 选择
        buckets = get_bucket_list()
        if buckets:
            selected_bucket = st.selectbox("选择 Bucket", buckets, index=buckets.index('mylabdemo1') if 'mylabdemo1' in buckets else 0)
        else:
            selected_bucket = st.text_input("Bucket 名称", value="mylabdemo1")
        
        log_prefix = st.text_input("日志前缀", value="s3logs/")
        
        # 时间范围选择
        time_filter = st.selectbox(
            "时间范围",
            ["最近1天", "最近3天", "最近7天", "最近30天", "全部"],
            index=2
        )
        
        days_map = {
            "最近1天": 1,
            "最近3天": 3,
            "最近7天": 7,
            "最近30天": 30,
            "全部": None
        }
        days_back = days_map[time_filter]
        
        max_files = st.slider("最大日志文件数", 10, 2000, 200)
        
        load_button = st.button("🔄 加载日志", type="primary")
        
        st.markdown("---")
        
        # 加载数据
        if load_button:
            with st.spinner('加载中...'):
                df = load_s3_logs(selected_bucket, log_prefix, max_files, days_back)
            st.session_state.df = df
            st.session_state.bucket = selected_bucket
            st.session_state.time_filter = time_filter
            st.session_state.current_page = 1
            
            if not df.empty:
                st.success(f"✅ 已加载 {len(df)} 条日志记录 (Bucket: {selected_bucket}, 时间: {time_filter})")
            else:
                st.warning("⚠️ 未找到日志数据")
    
    if 'df' not in st.session_state or st.session_state.df.empty:
        st.info("👈 请在左侧配置并加载日志")
        return
    
    df = st.session_state.df
    
    # 显示基本信息
    time_info = st.session_state.get('time_filter', '全部')
    st.info(f"📊 当前数据: {len(df)} 条记录 | Bucket: {st.session_state.bucket} | 时间: {time_info}")
    
    # 筛选器
    st.markdown("### 🔍 筛选条件")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if not df['time'].isna().all():
            min_date = df['time'].min().date()
            max_date = df['time'].max().date()
            date_range = st.date_input(
                "时间范围",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        else:
            date_range = None
    
    with col2:
        target_buckets = ['全部'] + sorted(df['bucket'].unique().tolist())
        selected_bucket_filter = st.selectbox("目标 Bucket", target_buckets)
    
    with col3:
        operations = ['全部'] + sorted(df['operation'].unique().tolist())
        selected_operation = st.selectbox("操作类型", operations)
    
    with col4:
        status_codes = ['全部'] + sorted(df['http_status'].unique().tolist())
        selected_status = st.selectbox("HTTP 状态码", status_codes)
    
    # 应用筛选
    filtered_df = df.copy()
    
    if date_range and len(date_range) == 2:
        start_date = pd.Timestamp(date_range[0]).tz_localize('UTC')
        end_date = (pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)).tz_localize('UTC')
        filtered_df = filtered_df[(filtered_df['time'] >= start_date) & (filtered_df['time'] < end_date)]
    
    if selected_bucket_filter != '全部':
        filtered_df = filtered_df[filtered_df['bucket'] == selected_bucket_filter]
    
    if selected_operation != '全部':
        filtered_df = filtered_df[filtered_df['operation'] == selected_operation]
    
    if selected_status != '全部':
        filtered_df = filtered_df[filtered_df['http_status'] == selected_status]
    
    if len(filtered_df) != len(df):
        st.info(f"筛选后: {len(filtered_df)} 条记录 (从 {len(df)} 条中筛选)")
    else:
        st.info(f"显示: {len(filtered_df)} 条记录")
    
    # 统计概览
    st.markdown("---")
    st.markdown("### 📈 统计概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总请求数", len(filtered_df))
    
    with col2:
        unique_users = filtered_df['requester'].nunique()
        st.metric("唯一用户数", unique_users)
    
    with col3:
        error_count = len(filtered_df[~filtered_df['http_status'].isin(['200', '204', '206', '304'])])
        st.metric("错误请求数", error_count)
    
    with col4:
        total_bytes = filtered_df['bytes_sent'].sum() / (1024**3)
        st.metric("数据传输", f"{total_bytes:.2f} GB")
    
    # 图表展示
    st.markdown("---")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 操作类型", "👤 用户统计", "🌐 IP 分布", "📋 详细列表"])
    
    with tab1:
        st.markdown("### 操作类型分布")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 饼图
            op_counts = filtered_df['operation'].value_counts()
            fig = px.pie(
                values=op_counts.values,
                names=op_counts.index,
                title="操作类型占比"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 统计表
            op_df = pd.DataFrame({
                '操作类型': op_counts.index,
                '请求数': op_counts.values,
                '占比': [f"{v/len(filtered_df)*100:.1f}%" for v in op_counts.values]
            })
            st.dataframe(op_df, use_container_width=True, height=400)
        
        # 时间趋势
        if not filtered_df['time'].isna().all():
            st.markdown("#### 操作时间趋势")
            time_df = filtered_df.groupby([filtered_df['time'].dt.date, 'operation']).size().reset_index(name='count')
            time_df.columns = ['date', 'operation', 'count']
            
            fig = px.line(
                time_df,
                x='date',
                y='count',
                color='operation',
                title="每日操作趋势"
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.markdown("### 用户访问统计")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 柱状图
            user_counts = filtered_df['requester'].value_counts().head(10)
            fig = go.Figure(data=[go.Bar(x=user_counts.index, y=user_counts.values)])
            fig.update_layout(title="Top 10 活跃用户", xaxis_title="用户", yaxis_title="请求数", xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 统计表
            user_df = pd.DataFrame({
                '用户': user_counts.index,
                '请求数': user_counts.values,
                '占比': [f"{v/len(filtered_df)*100:.1f}%" for v in user_counts.values]
            })
            st.dataframe(user_df, use_container_width=True, height=400)
    
    with tab3:
        st.markdown("### IP 地址分布")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # 饼图
            ip_counts = filtered_df['remote_ip'].value_counts().head(10)
            fig = px.pie(
                values=ip_counts.values,
                names=ip_counts.index,
                title="Top 10 IP 地址"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # 统计表
            ip_df = pd.DataFrame({
                'IP 地址': ip_counts.index,
                '请求数': ip_counts.values,
                '占比': [f"{v/len(filtered_df)*100:.1f}%" for v in ip_counts.values]
            })
            st.dataframe(ip_df, use_container_width=True, height=400)
        
        # HTTP 状态码分布
        st.markdown("#### HTTP 状态码分布")
        status_counts = filtered_df['http_status'].value_counts()
        
        fig = go.Figure(data=[go.Bar(
            x=status_counts.index,
            y=status_counts.values,
            text=status_counts.values,
            textposition='auto',
        )])
        fig.update_layout(
            title="HTTP 状态码统计",
            xaxis_title="状态码",
            yaxis_title="请求数"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.markdown("### 详细访问记录")
        
        # 显示列选择
        display_cols = ['time', 'bucket', 'operation', 'key', 'http_status', 'requester', 'remote_ip', 'bytes_sent']
        
        # 格式化显示
        display_df = filtered_df[display_cols].copy()
        
        # 安全格式化时间
        if not display_df['time'].isna().all():
            display_df['time'] = display_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            display_df['time'] = display_df['time'].astype(str)
        
        # 格式化字节数
        display_df['bytes_sent'] = display_df['bytes_sent'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else '0')
        
        # 重命名列
        display_df.columns = ['时间', '目标Bucket', '操作类型', '对象键', 'HTTP状态', '用户', 'IP地址', '字节数']
        
        # 显示记录数和性能提示
        delete_count = len(display_df[display_df['操作类型'].str.contains('DELETE', na=False)])
        if delete_count > 0:
            st.info(f"📋 {len(display_df)} 条记录 | 🗑️ 删除操作: {delete_count} 条")
        else:
            st.info(f"📋 {len(display_df)} 条记录")
        
        if len(display_df) > 10000:
            st.warning("⚠️ 数据量大，建议缩小时间范围")
        
        # 初始化页码和页大小
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 1
        if 'page_size' not in st.session_state:
            # 根据数据量自动调整页大小
            if len(display_df) > 10000:
                st.session_state.page_size = 100
            else:
                st.session_state.page_size = 50
        
        total_pages = (len(display_df) - 1) // st.session_state.page_size + 1 if len(display_df) > 0 else 1
        
        # 计算分页
        start_idx = (st.session_state.current_page - 1) * st.session_state.page_size
        end_idx = start_idx + st.session_state.page_size
        page_df = display_df.iloc[start_idx:end_idx]
        
        # 应用样式高亮删除操作
        def highlight_delete(row):
            if 'DELETE' in str(row['操作类型']):
                return ['background-color: #ffcccc'] * len(row)
            return [''] * len(row)
        
        styled_df = page_df.style.apply(highlight_delete, axis=1)
        
        # 显示数据表
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=500
        )
        
        # 分页控件（靠右显示）
        col1, col2, col3, col4, col5, col6 = st.columns([3, 0.8, 1, 1, 1, 0.8])
        
        with col2:
            page_size_options = [20, 50, 100, 200]
            current_index = page_size_options.index(st.session_state.page_size) if st.session_state.page_size in page_size_options else 1
            new_page_size = st.selectbox('每页显示', page_size_options, index=current_index, key='page_size_selector', label_visibility='collapsed')
            if new_page_size != st.session_state.page_size:
                st.session_state.page_size = new_page_size
                st.session_state.current_page = 1
                st.rerun()
        
        with col3:
            if st.button('⬅️ 上一页', disabled=(st.session_state.current_page <= 1), use_container_width=True):
                st.session_state.current_page -= 1
                st.rerun()
        
        with col4:
            st.markdown(f"<div style='text-align: center; padding: 8px; font-weight: 500;'>{st.session_state.current_page} / {total_pages}</div>", unsafe_allow_html=True)
        
        with col5:
            if st.button('下一页 ➡️', disabled=(st.session_state.current_page >= total_pages), use_container_width=True):
                st.session_state.current_page += 1
                st.rerun()
        
        with col6:
            if st.button('🔄', disabled=False, use_container_width=True):
                st.session_state.current_page = 1
                st.rerun()
        
        # 下载按钮和提示
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 下载 CSV",
                data=csv,
                file_name=f"s3_access_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        with col2:
            st.caption(f"共 {len(display_df)} 条")
        with col3:
            st.caption("💡 删除操作红色高亮")

if __name__ == "__main__":
    main()
