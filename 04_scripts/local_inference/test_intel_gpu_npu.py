#!/usr/bin/env python3
"""测试本地 Qwen 模型在 Intel GPU/NPU 上的运行情况"""

import sys
import os
from pathlib import Path
import torch
import time
import psutil
from datetime import datetime

# 添加 src 路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "05_src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import (
    resolve_device,
    LocalEmbeddingModel,
    LocalRerankerModel,
)


def print_section(title: str):
    """打印分隔符"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def check_hardware():
    """检查硬件支持情况"""
    print_section("硬件检测")
    
    print(f"🔍 PyTorch 版本: {torch.__version__}")
    print(f"🔍 CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA 设备: {torch.cuda.get_device_name()}")
        print(f"   设备数量: {torch.cuda.device_count()}")
    
    # 检查 Intel XPU
    try:
        import intel_extension_for_pytorch as ipex
        print(f"🔍 Intel Extension 版本: {ipex.__version__}")
        
        if hasattr(ipex, 'xpu') and hasattr(ipex.xpu, 'is_available'):
            xpu_available = ipex.xpu.is_available()
            print(f"🔍 Intel XPU 可用: {xpu_available}")
            if xpu_available:
                print(f"   XPU 设备数: {ipex.xpu.device_count()}")
                print(f"   XPU 设备: {ipex.xpu.get_device_name()}")
        else:
            print("❌ XPU API 不可用")
    except ImportError as e:
        print(f"❌ Intel Extension 未安装: {e}")


def get_system_memory():
    """获取系统内存使用情况"""
    mem = psutil.virtual_memory()
    return {
        'total': mem.total / (1024**3),  # GB
        'used': mem.used / (1024**3),
        'percent': mem.percent,
    }


def monitor_resources(label: str, before: dict, after: dict):
    """比较资源使用前后的变化"""
    print(f"\n📊 {label}:")
    print(f"   CPU 使用率: {psutil.cpu_percent(interval=0.1):.1f}%")
    print(f"   内存使用: {after['used']:.2f}GB / {after['total']:.2f}GB ({after['percent']:.1f}%)")
    
    mem_delta = (after['used'] - before['used']) * 1024  # MB
    print(f"   内存增长: {mem_delta:+.1f} MB")


def test_embedding_model():
    """测试 Qwen 嵌入模型"""
    print_section("测试 Qwen3-Embedding 模型")
    
    device = resolve_device("auto")
    print(f"✨ 选定设备: {device}")
    
    try:
        before_mem = get_system_memory()
        print(f"🚀 加载模型...")
        start_time = time.time()
        
        model = LocalEmbeddingModel(device=device)
        model.load()
        
        load_time = time.time() - start_time
        after_mem = get_system_memory()
        
        print(f"✅ 模型加载完成 ({load_time:.2f}s)")
        monitor_resources("加载后", before_mem, after_mem)
        
        # 测试推理
        print(f"\n🎯 执行推理测试...")
        test_texts = [
            "这是一个背包的产品。",
            "顾客对这个包包很满意。",
        ]
        
        before_mem = get_system_memory()
        start_time = time.time()
        
        embeddings = model.embed(test_texts)
        
        infer_time = time.time() - start_time
        after_mem = get_system_memory()
        
        print(f"✅ 推理完成 ({infer_time:.3f}s)")
        print(f"   输入文本数: {len(test_texts)}")
        print(f"   嵌入向量维度: {len(embeddings[0]) if embeddings else 'N/A'}")
        monitor_resources("推理后", before_mem, after_mem)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def test_reranker_model():
    """测试 Qwen 重排模型"""
    print_section("测试 Qwen3-Reranker 模型")
    
    device = resolve_device("auto")
    print(f"✨ 选定设备: {device}")
    
    try:
        before_mem = get_system_memory()
        print(f"🚀 加载模型...")
        start_time = time.time()
        
        model = LocalRerankerModel(device=device)
        model.load()
        
        load_time = time.time() - start_time
        after_mem = get_system_memory()
        
        print(f"✅ 模型加载完成 ({load_time:.2f}s)")
        monitor_resources("加载后", before_mem, after_mem)
        
        # 测试推理
        print(f"\n🎯 执行推理测试...")
        query = "背包的质量怎么样？"
        candidates = [
            "这个背包用料很厚实，质量不错。",
            "背包的拉链容易坏。",
            "颜色很漂亮。",
        ]
        
        before_mem = get_system_memory()
        start_time = time.time()
        
        result = model.rerank(query, candidates)
        
        infer_time = time.time() - start_time
        after_mem = get_system_memory()
        
        print(f"✅ 推理完成 ({infer_time:.3f}s)")
        print(f"   查询: {query}")
        print(f"   候选数: {len(candidates)}")
        if isinstance(result, list):
            for i, item in enumerate(result):
                if isinstance(item, dict):
                    score = item.get('relevance_score', 0.0)
                    print(f"   [{i}] 得分={score:.3f}: {candidates[i][:40]}...")
                else:
                    print(f"   [{i}] 得分={item:.3f}: {candidates[i][:40]}...")
        
        monitor_resources("推理后", before_mem, after_mem)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print(f"\n{'#'*60}")
    print(f"#  Intel GPU/NPU 本地 Qwen 模型测试")
    print(f"#  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")
    
    # 检查硬件
    check_hardware()
    
    # 测试嵌入模型
    try:
        test_embedding_model()
    except KeyboardInterrupt:
        print("\n⏸️  中断...")
    except Exception as e:
        print(f"\n❌ 嵌入模型测试失败: {e}")
    
    # 测试重排模型
    try:
        test_reranker_model()
    except KeyboardInterrupt:
        print("\n⏸️  中断...")
    except Exception as e:
        print(f"\n❌ 重排模型测试失败: {e}")
    
    print_section("测试完成")
    print(f"✨ 所有测试结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
