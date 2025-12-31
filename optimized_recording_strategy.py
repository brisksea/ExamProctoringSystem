#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
优化的录制策略配置
推荐使用30秒直接上传方案，平衡实时性和系统稳定性
"""

# 录制策略配置
RECORDING_STRATEGY = {
    # 方案1：30秒直接上传（推荐）
    "strategy_1": {
        "name": "30秒直接上传",
        "recording_interval": 30,  # 录制间隔（秒）
        "upload_immediately": True,  # 立即上传
        "max_file_size_mb": 50,  # 最大文件大小限制
        "fps": 8,  # 降低帧率，减少文件大小
        "quality": 70,  # 降低质量，减少文件大小
        "scale_ratio": 0.6,  # 降低分辨率，减少文件大小
        "codec": "mp4",  # 使用MP4格式，兼容性好
        "description": "每30秒生成一个小视频文件并立即上传，实时性好，内存压力小"
    },
    
    # 方案2：2分钟分段上传（备选）
    "strategy_2": {
        "name": "2分钟分段上传",
        "recording_interval": 120,  # 录制间隔（秒）
        "upload_immediately": False,  # 延迟上传
        "max_file_size_mb": 200,  # 最大文件大小限制
        "fps": 10,  # 标准帧率
        "quality": 80,  # 标准质量
        "scale_ratio": 0.8,  # 标准分辨率
        "codec": "mp4",
        "chunk_size_mb": 20,  # 分段大小
        "description": "每2分钟生成一个视频文件，然后分段上传，网络效率高但风险较大"
    }
}

# 推荐配置
RECOMMENDED_CONFIG = {
    "strategy": "strategy_1",  # 推荐使用方案1
    "reason": "基于内存限制和系统稳定性考虑",
    "optimizations": [
        "降低帧率到8fps，减少文件大小",
        "降低质量到70%，平衡文件大小和画质",
        "降低分辨率到60%，进一步减少文件大小",
        "使用MP4格式，确保兼容性",
        "立即上传，避免数据丢失"
    ]
}

# 性能优化配置
PERFORMANCE_CONFIG = {
    "memory_optimization": {
        "max_concurrent_uploads": 2,  # 最大并发上传数
        "upload_retry_count": 3,  # 上传重试次数
        "upload_retry_delay": 5,  # 重试延迟（秒）
        "cleanup_interval": 300,  # 清理间隔（秒）
    },
    
    "network_optimization": {
        "timeout": 60,  # 上传超时（秒）
        "chunk_size": 8192,  # 上传分块大小
        "compression": True,  # 启用压缩
    },
    
    "storage_optimization": {
        "max_temp_files": 10,  # 最大临时文件数
        "temp_file_ttl": 3600,  # 临时文件生存时间（秒）
        "auto_cleanup": True,  # 自动清理
    }
}

# 监控配置
MONITORING_CONFIG = {
    "upload_metrics": {
        "track_file_size": True,
        "track_upload_time": True,
        "track_success_rate": True,
        "alert_threshold": 0.9,  # 成功率阈值
    },
    
    "system_metrics": {
        "memory_usage": True,
        "disk_usage": True,
        "network_usage": True,
    }
}

def get_recommended_config():
    """获取推荐的录制配置"""
    return RECORDING_STRATEGY[RECOMMENDED_CONFIG["strategy"]]

def get_performance_config():
    """获取性能优化配置"""
    return PERFORMANCE_CONFIG

def get_monitoring_config():
    """获取监控配置"""
    return MONITORING_CONFIG

def calculate_file_size(seconds, fps, quality, scale_ratio, resolution=(1920, 1080)):
    """
    估算视频文件大小
    
    Args:
        seconds: 录制时长（秒）
        fps: 帧率
        quality: 质量（1-100）
        scale_ratio: 缩放比例
        resolution: 原始分辨率
    
    Returns:
        估算的文件大小（MB）
    """
    # 计算实际分辨率
    actual_width = int(resolution[0] * scale_ratio)
    actual_height = int(resolution[1] * scale_ratio)
    
    # 基础比特率（Mbps）
    base_bitrate = 2.0
    
    # 根据质量调整比特率
    quality_factor = quality / 100.0
    adjusted_bitrate = base_bitrate * quality_factor
    
    # 根据帧率调整
    fps_factor = fps / 30.0
    final_bitrate = adjusted_bitrate * fps_factor
    
    # 计算文件大小（MB）
    file_size_mb = (final_bitrate * seconds) / 8
    
    return round(file_size_mb, 2)

def compare_strategies():
    """比较两种策略的性能指标"""
    strategy1 = RECORDING_STRATEGY["strategy_1"]
    strategy2 = RECORDING_STRATEGY["strategy_2"]
    
    # 计算文件大小
    size1 = calculate_file_size(
        strategy1["recording_interval"],
        strategy1["fps"],
        strategy1["quality"],
        strategy1["scale_ratio"]
    )
    
    size2 = calculate_file_size(
        strategy2["recording_interval"],
        strategy2["fps"],
        strategy2["quality"],
        strategy2["scale_ratio"]
    )
    
    comparison = {
        "strategy_1": {
            "name": strategy1["name"],
            "file_size_mb": size1,
            "files_per_hour": 120,  # 3600/30
            "total_size_per_hour_mb": size1 * 120,
            "upload_frequency": "每30秒",
            "data_loss_risk": "低",
            "memory_usage": "低",
            "network_overhead": "中等"
        },
        "strategy_2": {
            "name": strategy2["name"],
            "file_size_mb": size2,
            "files_per_hour": 30,  # 3600/120
            "total_size_per_hour_mb": size2 * 30,
            "upload_frequency": "每2分钟",
            "data_loss_risk": "高",
            "memory_usage": "高",
            "network_overhead": "低"
        }
    }
    
    return comparison

if __name__ == "__main__":
    # 打印推荐配置
    print("=== 推荐录制策略 ===")
    config = get_recommended_config()
    print(f"策略: {config['name']}")
    print(f"描述: {config['description']}")
    print(f"录制间隔: {config['recording_interval']}秒")
    print(f"最大文件大小: {config['max_file_size_mb']}MB")
    print(f"帧率: {config['fps']}fps")
    print(f"质量: {config['quality']}%")
    print(f"分辨率缩放: {config['scale_ratio']}")
    
    print("\n=== 策略对比 ===")
    comparison = compare_strategies()
    for strategy_name, metrics in comparison.items():
        print(f"\n{metrics['name']}:")
        print(f"  文件大小: {metrics['file_size_mb']}MB")
        print(f"  每小时文件数: {metrics['files_per_hour']}")
        print(f"  每小时总大小: {metrics['total_size_per_hour_mb']}MB")
        print(f"  上传频率: {metrics['upload_frequency']}")
        print(f"  数据丢失风险: {metrics['data_loss_risk']}")
        print(f"  内存使用: {metrics['memory_usage']}")
        print(f"  网络开销: {metrics['network_overhead']}")
    
    print(f"\n=== 推荐理由 ===")
    print(f"推荐策略: {RECOMMENDED_CONFIG['strategy']}")
    print(f"推荐原因: {RECOMMENDED_CONFIG['reason']}")
    print("优化措施:")
    for opt in RECOMMENDED_CONFIG['optimizations']:
        print(f"  - {opt}")
