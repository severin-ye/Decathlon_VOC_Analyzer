#!/usr/bin/env python3
"""测试 OpenVINO 集成的模型性能"""

import sys
from pathlib import Path
import time
import psutil
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "05_src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def print_section(title: str):
    """打印分隔符"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def get_resources():
    """获取系统资源"""
    mem = psutil.virtual_memory()
    return {
        'cpu': psutil.cpu_percent(interval=0.1),
        'memory': mem.used / (1024**3),
    }


def test_openvino_integrated():
    """测试 OpenVINO 集成模型"""
    print_section("OpenVINO 集成模型测试")
    
    try:
        from decathlon_voc_analyzer.stage3_retrieval.openvino_integrated import (
            OpenVINOOptimizedEmbeddingModel,
            OpenVINOOptimizedRerankerModel,
            get_openvino_device,
        )
        
        device = get_openvino_device()
        print(f"📍 检测设备: {device}\n")
        
        # 测试嵌入模型
        print("🔹 嵌入模型测试:")
        before = get_resources()
        start = time.time()
        
        emb_model = OpenVINOOptimizedEmbeddingModel(device=device)
        emb_model.load()
        
        load_time = time.time() - start
        print(f"  ✅ 加载时间: {load_time:.2f}s")
        
        # 推理
        texts = ["这是一个背包", "质量很不错"]
        before = get_resources()
        start = time.time()
        
        embeddings = emb_model.embed(texts)
        
        infer_time = time.time() - start
        after = get_resources()
        
        print(f"  ✅ 推理时间: {infer_time:.3f}s ({len(texts)} 条文本)")
        print(f"  💾 内存: {after['memory']:.2f}GB")
        print(f"  🔥 CPU: {after['cpu']:.1f}%\n")
        
        # 测试重排模型
        print("🔹 重排模型测试:")
        before = get_resources()
        start = time.time()
        
        rer_model = OpenVINOOptimizedRerankerModel(device=device)
        rer_model.load()
        
        load_time = time.time() - start
        print(f"  ✅ 加载时间: {load_time:.2f}s")
        
        # 推理
        query = "背包质量怎么样？"
        candidates = ["用料厚实", "质量不错", "拉链易坏"]
        
        before = get_resources()
        start = time.time()
        
        results = rer_model.rerank(query, candidates)
        
        infer_time = time.time() - start
        after = get_resources()
        
        print(f"  ✅ 推理时间: {infer_time:.3f}s ({len(candidates)} 个候选)")
        print(f"  📊 结果:")
        for r in results:
            idx = r['index']
            score = r['relevance_score']
            print(f"     [{idx}] {candidates[idx]}: {score:.3f}")
        print(f"  💾 内存: {after['memory']:.2f}GB")
        print(f"  🔥 CPU: {after['cpu']:.1f}%")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_openvino_integrated()
