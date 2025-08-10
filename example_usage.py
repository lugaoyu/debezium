#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oracle归档日志分段处理器使用示例

这个示例展示了如何使用智能分段算法来并行处理Oracle归档日志，
提高大批量数据处理的性能。
"""

import cx_Oracle
import json
import time
from oracle_log_segmentation import (
    OracleLogSegmentProcessor, 
    SegmentationConfig
)


def create_oracle_connection():
    """创建Oracle数据库连接"""
    # 请根据实际环境修改连接参数
    dsn = cx_Oracle.makedsn(
        host='localhost',
        port=1521,
        service_name='ORCL'
    )
    
    connection = cx_Oracle.connect(
        user='your_username',
        password='your_password',
        dsn=dsn
    )
    
    return connection


def setup_logminer_sql(archive_log_file: str) -> str:
    """设置LogMiner的SQL语句"""
    return f"""
    BEGIN
        -- 添加归档日志文件
        DBMS_LOGMNR.ADD_LOGFILE(
            LOGFILENAME => '{archive_log_file}',
            OPTIONS => DBMS_LOGMNR.NEW
        );
        
        -- 启动LogMiner
        DBMS_LOGMNR.START_LOGMNR(
            OPTIONS => DBMS_LOGMNR.SKIP_CORRUPTION + 
                      DBMS_LOGMNR.NO_SQL_DELIMITER + 
                      DBMS_LOGMNR.NO_ROWID_IN_STMT
        );
    END;
    """


def my_record_processor(records):
    """
    自定义的记录处理函数
    
    Args:
        records: 记录列表，每条记录包含scn, timestamp, operation等字段
    """
    for record in records:
        # 这里实现您的业务逻辑
        # 例如：数据转换、写入目标系统、触发业务规则等
        
        if record['operation'] in ['INSERT', 'UPDATE', 'DELETE']:
            print(f"处理操作: {record['operation']} on {record['table_name']} "
                  f"at SCN {record['scn']}")
            
            # 示例：将重要变更写入文件
            if record['table_name'] in ['IMPORTANT_TABLE1', 'IMPORTANT_TABLE2']:
                with open(f"/tmp/changes_{record['table_name']}.log", "a") as f:
                    f.write(f"{record['scn']},{record['timestamp']},{record['sql_redo']}\n")


def example_basic_usage():
    """基础使用示例"""
    print("=== 基础使用示例 ===")
    
    # 1. 配置分段参数
    config = SegmentationConfig(
        target_records_per_segment=50000,  # 每段目标5万条记录
        max_segments=10,                    # 最多10个分段
        min_segments=2,                     # 最少2个分段
        sampling_ratio=0.002,               # 0.2%采样率
        tolerance_ratio=0.2                 # 20%容差
    )
    
    # 2. 创建处理器
    processor = OracleLogSegmentProcessor(
        connection_factory=create_oracle_connection,
        logminer_setup_sql=setup_logminer_sql('/path/to/archive_log.arc'),
        config=config
    )
    
    # 3. 并行处理归档日志
    start_scn = 100
    end_scn = 10000
    
    print(f"开始处理SCN范围: {start_scn} - {end_scn}")
    
    stats = processor.process_archive_log_parallel(
        start_scn=start_scn,
        end_scn=end_scn,
        record_processor=my_record_processor,
        max_workers=4  # 使用4个并行线程
    )
    
    # 4. 显示处理结果
    print("\n处理统计信息:")
    print(f"总分段数: {stats['total_segments']}")
    print(f"总记录数: {stats['total_records']}")
    print(f"总耗时: {stats['total_time']:.2f}秒")
    print(f"平均速度: {stats['records_per_second']:.1f}条/秒")
    
    print("\n各分段详情:")
    for i, segment in enumerate(stats['segment_details']):
        accuracy = (1 - segment['accuracy']) * 100
        print(f"分段{i+1}: {segment['range']} - "
              f"估算{segment['estimated_records']}条, "
              f"实际{segment['actual_records']}条, "
              f"准确率{accuracy:.1f}%, "
              f"耗时{segment['processing_time']:.2f}秒")


def example_high_performance_usage():
    """高性能处理示例"""
    print("\n=== 高性能处理示例 ===")
    
    # 针对大数据量优化的配置
    config = SegmentationConfig(
        target_records_per_segment=100000,  # 每段10万条记录
        max_segments=16,                    # 最多16个分段
        min_segments=4,                     # 最少4个分段
        sampling_ratio=0.001,               # 0.1%采样率（减少采样开销）
        max_sampling_records=5000,          # 最多采样5000条
        tolerance_ratio=0.25                # 25%容差（允许更大的不均匀性）
    )
    
    # 自定义高性能记录处理器
    processed_count = 0
    batch_buffer = []
    
    def high_performance_processor(records):
        nonlocal processed_count, batch_buffer
        
        # 批量缓存处理以减少I/O
        batch_buffer.extend(records)
        processed_count += len(records)
        
        # 每10万条记录批量写入一次
        if len(batch_buffer) >= 100000:
            # 这里可以批量写入数据库、消息队列等
            print(f"批量处理了 {len(batch_buffer)} 条记录，累计 {processed_count} 条")
            batch_buffer.clear()
    
    processor = OracleLogSegmentProcessor(
        connection_factory=create_oracle_connection,
        logminer_setup_sql=setup_logminer_sql('/path/to/large_archive_log.arc'),
        config=config
    )
    
    # 处理大范围SCN
    start_scn = 1000
    end_scn = 100000
    
    print(f"开始高性能处理SCN范围: {start_scn} - {end_scn}")
    
    start_time = time.time()
    stats = processor.process_archive_log_parallel(
        start_scn=start_scn,
        end_scn=end_scn,
        record_processor=high_performance_processor,
        max_workers=8  # 使用8个并行线程
    )
    
    # 处理剩余缓存
    if batch_buffer:
        print(f"处理剩余 {len(batch_buffer)} 条记录")
        batch_buffer.clear()
    
    total_time = time.time() - start_time
    print(f"\n高性能处理完成:")
    print(f"总处理时间: {total_time:.2f}秒")
    print(f"处理速度: {stats['records_per_second']:.1f}条/秒")
    print(f"分段效率: 平均每段{stats['avg_time_per_segment']:.2f}秒")


def example_custom_segmentation():
    """自定义分段策略示例"""
    print("\n=== 自定义分段策略示例 ===")
    
    # 针对特定业务场景的分段配置
    config = SegmentationConfig(
        target_records_per_segment=30000,   # 较小的分段以确保响应性
        max_segments=20,                    # 允许更多分段
        min_segments=3,                     
        sampling_ratio=0.005,               # 更高的采样率以提高准确性
        tolerance_ratio=0.15                # 更严格的容差
    )
    
    # 自定义处理器，支持特定表的特殊处理
    critical_tables = {'USER_ACCOUNTS', 'TRANSACTIONS', 'AUDIT_LOG'}
    
    def custom_processor(records):
        critical_changes = []
        normal_changes = []
        
        for record in records:
            if record['table_name'] in critical_tables:
                critical_changes.append(record)
            else:
                normal_changes.append(record)
        
        # 优先处理关键表的变更
        if critical_changes:
            print(f"处理 {len(critical_changes)} 条关键表变更")
            # 实时处理关键变更
            for change in critical_changes:
                # 发送告警、实时同步等
                pass
        
        if normal_changes:
            print(f"批量处理 {len(normal_changes)} 条普通变更")
            # 批量处理普通变更
    
    processor = OracleLogSegmentProcessor(
        connection_factory=create_oracle_connection,
        logminer_setup_sql=setup_logminer_sql('/path/to/business_archive_log.arc'),
        config=config
    )
    
    stats = processor.process_archive_log_parallel(
        start_scn=5000,
        end_scn=50000,
        record_processor=custom_processor,
        max_workers=6
    )
    
    print(f"自定义处理完成: {stats['total_records']}条记录")


def example_monitoring_and_alerting():
    """监控和告警示例"""
    print("\n=== 监控和告警示例 ===")
    
    config = SegmentationConfig(
        target_records_per_segment=80000,
        max_segments=12
    )
    
    # 监控处理进度
    def monitoring_processor(records):
        # 监控处理速度
        current_time = time.time()
        
        # 检查是否有异常操作
        for record in records:
            if record['operation'] == 'DELETE' and 'CRITICAL' in record['table_name']:
                print(f"⚠️  告警: 关键表删除操作 - {record['table_name']} at SCN {record['scn']}")
            
            if 'DROP' in (record['sql_redo'] or ''):
                print(f"🚨 严重告警: DDL操作检测 - {record['sql_redo'][:100]}...")
    
    processor = OracleLogSegmentProcessor(
        connection_factory=create_oracle_connection,
        logminer_setup_sql=setup_logminer_sql('/path/to/monitored_log.arc'),
        config=config
    )
    
    # 处理并监控
    stats = processor.process_archive_log_parallel(
        start_scn=2000,
        end_scn=20000,
        record_processor=monitoring_processor,
        max_workers=4
    )
    
    # 生成监控报告
    report = {
        'timestamp': time.time(),
        'performance': stats,
        'status': 'completed',
        'segments_accuracy': [
            segment['accuracy'] for segment in stats['segment_details']
        ]
    }
    
    with open('/tmp/processing_report.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print("监控报告已保存到 /tmp/processing_report.json")


if __name__ == "__main__":
    print("Oracle归档日志智能分段处理器示例\n")
    
    try:
        # 运行各种使用示例
        example_basic_usage()
        example_high_performance_usage()
        example_custom_segmentation()
        example_monitoring_and_alerting()
        
        print("\n✅ 所有示例执行完成！")
        
    except Exception as e:
        print(f"❌ 执行错误: {e}")
        print("请检查Oracle连接配置和LogMiner权限")


# 额外工具函数

def analyze_archive_log_scn_range(archive_log_file: str) -> tuple:
    """分析归档日志的SCN范围"""
    try:
        conn = create_oracle_connection()
        cursor = conn.cursor()
        
        # 设置LogMiner
        setup_sql = setup_logminer_sql(archive_log_file)
        cursor.execute(setup_sql)
        
        # 查询SCN范围
        cursor.execute("""
            SELECT MIN(scn) as min_scn, MAX(scn) as max_scn, COUNT(*) as total_records
            FROM v$logmnr_contents
        """)
        
        result = cursor.fetchone()
        min_scn, max_scn, total_records = result
        
        cursor.close()
        conn.close()
        
        print(f"归档日志分析结果:")
        print(f"  SCN范围: {min_scn} - {max_scn}")
        print(f"  总记录数: {total_records}")
        print(f"  SCN跨度: {max_scn - min_scn}")
        print(f"  平均密度: {total_records / (max_scn - min_scn):.4f} 记录/SCN")
        
        return min_scn, max_scn, total_records
        
    except Exception as e:
        print(f"分析归档日志失败: {e}")
        return None, None, None


def estimate_optimal_segments(total_records: int, target_per_segment: int = 100000) -> int:
    """估算最优分段数"""
    if total_records <= target_per_segment:
        return 1
    
    optimal_segments = max(2, min(20, total_records // target_per_segment))
    print(f"基于{total_records}条记录，建议分成{optimal_segments}个段")
    return optimal_segments