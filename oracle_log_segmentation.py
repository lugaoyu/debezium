#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Oracle归档日志智能分段处理器

该模块提供了对Oracle归档日志进行智能分段的功能，
通过采样估算和自适应分段算法，确保每个分段的结果集尽可能均匀，
从而提高并行处理的性能。
"""

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Tuple, Callable, Optional, Dict, Any
import cx_Oracle
from threading import Lock

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class SCNRange:
    """SCN范围数据类"""
    start_scn: int
    end_scn: int
    estimated_records: int = 0
    actual_records: Optional[int] = None
    processing_time: Optional[float] = None
    
    @property
    def span(self) -> int:
        return self.end_scn - self.start_scn
    
    def __str__(self):
        return f"SCN[{self.start_scn}-{self.end_scn}] ~{self.estimated_records}条记录"


@dataclass
class SegmentationConfig:
    """分段配置"""
    target_records_per_segment: int = 100000  # 目标每段记录数
    max_segments: int = 20  # 最大分段数
    min_segments: int = 2   # 最小分段数
    sampling_ratio: float = 0.001  # 采样比例（0.1%）
    max_sampling_records: int = 10000  # 最大采样记录数
    tolerance_ratio: float = 0.3  # 容差比例（30%）


class SCNDensityEstimator:
    """SCN密度估算器 - 通过采样估算不同SCN范围的记录密度"""
    
    def __init__(self, connection_factory: Callable[[], cx_Oracle.Connection], 
                 logminer_setup_sql: str, config: SegmentationConfig):
        self.connection_factory = connection_factory
        self.logminer_setup_sql = logminer_setup_sql
        self.config = config
        self.density_cache: Dict[Tuple[int, int], float] = {}
        self.cache_lock = Lock()
    
    def estimate_density(self, start_scn: int, end_scn: int) -> float:
        """
        估算指定SCN范围内的记录密度（每个SCN单位的平均记录数）
        
        Args:
            start_scn: 起始SCN
            end_scn: 结束SCN
            
        Returns:
            float: 密度值（记录数/SCN）
        """
        cache_key = (start_scn, end_scn)
        
        with self.cache_lock:
            if cache_key in self.density_cache:
                return self.density_cache[cache_key]
        
        try:
            conn = self.connection_factory()
            cursor = conn.cursor()
            
            # 设置LogMiner
            cursor.execute(self.logminer_setup_sql)
            
            # 计算采样范围
            total_span = end_scn - start_scn
            sample_span = max(1, int(total_span * self.config.sampling_ratio))
            
            # 多点采样以获得更准确的密度估算
            sample_points = min(5, max(2, total_span // 1000))  # 2-5个采样点
            sample_density_sum = 0
            valid_samples = 0
            
            for i in range(sample_points):
                sample_start = start_scn + i * (total_span // sample_points)
                sample_end = min(sample_start + sample_span, end_scn)
                
                if sample_end <= sample_start:
                    continue
                    
                # 查询采样范围内的记录数
                sample_query = f"""
                SELECT COUNT(*) 
                FROM v$logmnr_contents 
                WHERE scn >= {sample_start} AND scn < {sample_end}
                AND ROWNUM <= {self.config.max_sampling_records}
                """
                
                cursor.execute(sample_query)
                sample_count = cursor.fetchone()[0]
                
                if sample_count > 0:
                    sample_density = sample_count / (sample_end - sample_start)
                    sample_density_sum += sample_density
                    valid_samples += 1
                    
                logger.debug(f"采样点 {i+1}: SCN[{sample_start}-{sample_end}] = {sample_count}条记录, 密度={sample_density:.6f}")
            
            cursor.close()
            conn.close()
            
            # 计算平均密度
            if valid_samples > 0:
                avg_density = sample_density_sum / valid_samples
            else:
                # 如果没有有效采样，使用默认低密度
                avg_density = 0.001
                
            # 缓存结果
            with self.cache_lock:
                self.density_cache[cache_key] = avg_density
                
            logger.info(f"SCN范围[{start_scn}-{end_scn}]密度估算: {avg_density:.6f} 记录/SCN")
            return avg_density
            
        except Exception as e:
            logger.error(f"密度估算失败 SCN[{start_scn}-{end_scn}]: {e}")
            # 返回默认密度
            return 0.01


class AdaptiveSegmentationAlgorithm:
    """自适应分段算法"""
    
    def __init__(self, density_estimator: SCNDensityEstimator, config: SegmentationConfig):
        self.density_estimator = density_estimator
        self.config = config
    
    def create_segments(self, start_scn: int, end_scn: int) -> List[SCNRange]:
        """
        创建自适应分段
        
        Args:
            start_scn: 起始SCN
            end_scn: 结束SCN
            
        Returns:
            List[SCNRange]: 分段列表
        """
        logger.info(f"开始对SCN范围[{start_scn}-{end_scn}]进行自适应分段")
        
        # 1. 初步估算总记录数
        total_density = self.density_estimator.estimate_density(start_scn, end_scn)
        total_estimated_records = int(total_density * (end_scn - start_scn))
        
        logger.info(f"估算总记录数: {total_estimated_records}")
        
        # 2. 计算理想分段数
        if total_estimated_records <= self.config.target_records_per_segment:
            # 记录数较少，不需要分段
            segments = [SCNRange(start_scn, end_scn, total_estimated_records)]
            logger.info("记录数较少，使用单一分段")
            return segments
        
        ideal_segments = max(
            self.config.min_segments,
            min(
                self.config.max_segments,
                math.ceil(total_estimated_records / self.config.target_records_per_segment)
            )
        )
        
        logger.info(f"计算得出理想分段数: {ideal_segments}")
        
        # 3. 使用二分查找算法进行精确分段
        segments = self._binary_search_segmentation(start_scn, end_scn, ideal_segments)
        
        # 4. 验证和调整分段
        segments = self._validate_and_adjust_segments(segments)
        
        logger.info(f"最终生成 {len(segments)} 个分段:")
        for i, segment in enumerate(segments):
            logger.info(f"  段 {i+1}: {segment}")
        
        return segments
    
    def _binary_search_segmentation(self, start_scn: int, end_scn: int, target_segments: int) -> List[SCNRange]:
        """使用二分查找算法进行精确分段"""
        segments = []
        current_scn = start_scn
        target_records_per_segment = self.config.target_records_per_segment
        
        for segment_idx in range(target_segments):
            if segment_idx == target_segments - 1:
                # 最后一个分段包含剩余所有SCN
                segment_end = end_scn
            else:
                # 使用二分查找确定分段结束位置
                segment_end = self._find_segment_end(current_scn, end_scn, target_records_per_segment)
            
            if segment_end <= current_scn:
                break
            
            # 估算这个分段的记录数
            segment_density = self.density_estimator.estimate_density(current_scn, segment_end)
            estimated_records = int(segment_density * (segment_end - current_scn))
            
            segments.append(SCNRange(current_scn, segment_end, estimated_records))
            current_scn = segment_end
            
            if current_scn >= end_scn:
                break
        
        return segments
    
    def _find_segment_end(self, start_scn: int, max_end_scn: int, target_records: int) -> int:
        """使用二分查找找到包含目标记录数的分段结束SCN"""
        left = start_scn + 1
        right = max_end_scn
        best_end = right
        
        # 二分查找最合适的结束位置
        while left <= right:
            mid = (left + right) // 2
            
            # 估算到mid位置的记录数
            density = self.density_estimator.estimate_density(start_scn, mid)
            estimated_records = int(density * (mid - start_scn))
            
            if estimated_records < target_records:
                left = mid + 1
            elif estimated_records > target_records * (1 + self.config.tolerance_ratio):
                right = mid - 1
                best_end = mid
            else:
                # 在容差范围内，这是一个好的分割点
                best_end = mid
                break
        
        return min(best_end, max_end_scn)
    
    def _validate_and_adjust_segments(self, segments: List[SCNRange]) -> List[SCNRange]:
        """验证和调整分段，确保分段合理"""
        if not segments:
            return segments
        
        # 检查是否有过小的分段需要合并
        adjusted_segments = []
        min_records_threshold = self.config.target_records_per_segment * 0.1  # 最小10%阈值
        
        i = 0
        while i < len(segments):
            current_segment = segments[i]
            
            # 检查当前分段是否过小
            if (current_segment.estimated_records < min_records_threshold and 
                i < len(segments) - 1):
                # 尝试与下一个分段合并
                next_segment = segments[i + 1]
                merged_segment = SCNRange(
                    current_segment.start_scn,
                    next_segment.end_scn,
                    current_segment.estimated_records + next_segment.estimated_records
                )
                adjusted_segments.append(merged_segment)
                logger.info(f"合并小分段: {current_segment} + {next_segment} -> {merged_segment}")
                i += 2  # 跳过下一个分段
            else:
                adjusted_segments.append(current_segment)
                i += 1
        
        return adjusted_segments


class OracleLogSegmentProcessor:
    """Oracle日志分段处理器"""
    
    def __init__(self, connection_factory: Callable[[], cx_Oracle.Connection],
                 logminer_setup_sql: str, config: Optional[SegmentationConfig] = None):
        self.connection_factory = connection_factory
        self.logminer_setup_sql = logminer_setup_sql
        self.config = config or SegmentationConfig()
        
        self.density_estimator = SCNDensityEstimator(
            connection_factory, logminer_setup_sql, self.config
        )
        self.segmentation_algorithm = AdaptiveSegmentationAlgorithm(
            self.density_estimator, self.config
        )
        
        self.processing_stats = {
            'total_segments': 0,
            'total_records': 0,
            'total_time': 0,
            'segment_details': []
        }
    
    def process_archive_log_parallel(self, start_scn: int, end_scn: int,
                                   record_processor: Callable[[List[Dict[str, Any]]], None],
                                   max_workers: Optional[int] = None) -> Dict[str, Any]:
        """
        并行处理归档日志
        
        Args:
            start_scn: 起始SCN
            end_scn: 结束SCN  
            record_processor: 记录处理函数
            max_workers: 最大工作线程数
            
        Returns:
            Dict[str, Any]: 处理统计信息
        """
        start_time = time.time()
        
        # 1. 创建分段
        segments = self.segmentation_algorithm.create_segments(start_scn, end_scn)
        
        if not segments:
            logger.warning("未生成任何分段")
            return self.processing_stats
        
        # 2. 并行处理各个分段
        max_workers = max_workers or min(len(segments), 8)  # 默认最多8个线程
        
        logger.info(f"开始并行处理 {len(segments)} 个分段，使用 {max_workers} 个线程")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有分段处理任务
            future_to_segment = {
                executor.submit(self._process_single_segment, segment, record_processor): segment
                for segment in segments
            }
            
            # 收集处理结果
            completed_segments = 0
            total_records = 0
            
            for future in as_completed(future_to_segment):
                segment = future_to_segment[future]
                try:
                    segment_result = future.result()
                    segment.actual_records = segment_result['record_count']
                    segment.processing_time = segment_result['processing_time']
                    
                    completed_segments += 1
                    total_records += segment.actual_records
                    
                    logger.info(f"分段完成 ({completed_segments}/{len(segments)}): "
                              f"{segment} -> 实际{segment.actual_records}条记录, "
                              f"耗时{segment.processing_time:.2f}秒")
                    
                except Exception as e:
                    logger.error(f"分段处理失败 {segment}: {e}")
        
        # 3. 统计处理结果
        total_time = time.time() - start_time
        
        self.processing_stats = {
            'total_segments': len(segments),
            'total_records': total_records,
            'total_time': total_time,
            'avg_time_per_segment': total_time / len(segments),
            'records_per_second': total_records / total_time if total_time > 0 else 0,
            'segment_details': [
                {
                    'range': f"{s.start_scn}-{s.end_scn}",
                    'estimated_records': s.estimated_records,
                    'actual_records': s.actual_records,
                    'processing_time': s.processing_time,
                    'accuracy': abs(s.estimated_records - s.actual_records) / max(s.actual_records, 1) if s.actual_records else 0
                }
                for s in segments
            ]
        }
        
        logger.info(f"并行处理完成: {total_records}条记录, 总耗时{total_time:.2f}秒, "
                   f"平均{self.processing_stats['records_per_second']:.1f}条/秒")
        
        return self.processing_stats
    
    def _process_single_segment(self, segment: SCNRange, 
                              record_processor: Callable[[List[Dict[str, Any]]], None]) -> Dict[str, Any]:
        """处理单个分段"""
        start_time = time.time()
        record_count = 0
        
        try:
            conn = self.connection_factory()
            cursor = conn.cursor()
            
            # 设置LogMiner
            cursor.execute(self.logminer_setup_sql)
            
            # 查询分段数据
            query = f"""
            SELECT scn, timestamp, operation, table_name, sql_redo, sql_undo
            FROM v$logmnr_contents
            WHERE scn >= {segment.start_scn} AND scn < {segment.end_scn}
            ORDER BY scn
            """
            
            cursor.execute(query)
            
            # 批量处理记录
            batch_size = 1000
            batch_records = []
            
            for row in cursor:
                record = {
                    'scn': row[0],
                    'timestamp': row[1],
                    'operation': row[2],
                    'table_name': row[3],
                    'sql_redo': row[4],
                    'sql_undo': row[5]
                }
                batch_records.append(record)
                record_count += 1
                
                if len(batch_records) >= batch_size:
                    record_processor(batch_records)
                    batch_records = []
            
            # 处理剩余记录
            if batch_records:
                record_processor(batch_records)
            
            cursor.close()
            conn.close()
            
            processing_time = time.time() - start_time
            
            return {
                'record_count': record_count,
                'processing_time': processing_time
            }
            
        except Exception as e:
            logger.error(f"分段处理异常 {segment}: {e}")
            raise
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        return self.processing_stats.copy()