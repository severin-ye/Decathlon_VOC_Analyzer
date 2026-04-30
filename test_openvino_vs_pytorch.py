#!/usr/bin/env python3
"""对比 PyTorch vs OpenVINO 的性能和 GPU/NPU 使用情况"""

import sys
import os
from pathlib import Path
import time
import psutil
from datetime import datetime

# 添加 src 路径
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "05_src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def print_section(title: str):
    """打印分隔符"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def check_openvino():
    """检查 OpenVINO 支持情况"""
    print_section("OpenVINO 检测")
    
    try:
        from openvino.runtime import Core, get_version
        print(f"✅ OpenVINO 版本: {get_version()}")
        
        core = Core()
        available_devices = core.available_devices
        print(f"✅ 可用设备: {', '.join(available_devices)}")
        
        # 获取设备支持
        for device in available_devices:
            try:
                props = core.get_property(device)
                print(f"   • {device}: {props}")
            except:
                print(f"   • {device}: 可用")
        
        return available_devices
        
    except ImportError:
        print("❌ OpenVINO 未安装")
        return []


def get_system_resources():
    """获取系统资源使用情况"""
    mem = psutil.virtual_memory()
    return {
        'cpu_percent': psutil.cpu_percent(interval=0.1),
        'memory_total': mem.total / (1024**3),
        'memory_used': mem.used / (1024**3),
        'memory_percent': mem.percent,
    }


def test_pytorch_embedding():
    """测试 PyTorch 嵌入模型"""
    print_section("PyTorch 嵌入模型测试")
    
    try:
        from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import LocalEmbeddingModel
        
        device = "cpu"  # 强制用 CPU 测试
        print(f"📍 设备: {device}")
        
        before_res = get_system_resources()
        start_time = time.time()
        
        model = LocalEmbeddingModel(device=device)
        model.load()
        
        load_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 模型加载: {load_time:.2f}s")
        print(f"   内存增长: {(after_res['memory_used'] - before_res['memory_used']):.2f} GB")
        
        # 推理测试
        test_texts = ["这是一个背包。", "顾客很满意。"]
        before_res = get_system_resources()
        start_time = time.time()
        
        embeddings = model.embed(test_texts)
        
        infer_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 推理时间: {infer_time:.3f}s (2 条文本)")
        print(f"   吞吐量: {2/infer_time:.1f} 文本/秒")
        print(f"   CPU 使用: {after_res['cpu_percent']:.1f}%")
        
        return {
            'type': 'pytorch',
            'load_time': load_time,
            'infer_time': infer_time,
            'cpu_percent': after_res['cpu_percent'],
        }
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_openvino_embedding():
    """测试 OpenVINO 嵌入模型"""
    print_section("OpenVINO 嵌入模型测试")
    
    try:
        from decathlon_voc_analyzer.stage3_retrieval.openvino_models import OpenVINOEmbeddingModel, get_openvino_device
        
        device = get_openvino_device()
        print(f"📍 设备: {device}")
        
        before_res = get_system_resources()
        start_time = time.time()
        
        model = OpenVINOEmbeddingModel(device=device)
        model.load()
        
        load_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 模型加载: {load_time:.2f}s")
        print(f"   内存增长: {(after_res['memory_used'] - before_res['memory_used']):.2f} GB")
        
        # 推理测试
        test_texts = ["这是一个背包。", "顾客很满意。"]
        before_res = get_system_resources()
        start_time = time.time()
        
        embeddings = model.embed(test_texts)
        
        infer_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 推理时间: {infer_time:.3f}s (2 条文本)")
        print(f"   吞吐量: {2/infer_time:.1f} 文本/秒")
        print(f"   CPU 使用: {after_res['cpu_percent']:.1f}%")
        
        return {
            'type': 'openvino',
            'device': device,
            'load_time': load_time,
            'infer_time': infer_time,
            'cpu_percent': after_res['cpu_percent'],
        }
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_pytorch_reranker():
    """测试 PyTorch 重排模型"""
    print_section("PyTorch 重排模型测试")
    
    try:
        from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import LocalRerankerModel
        
        device = "cpu"
        print(f"📍 设备: {device}")
        
        before_res = get_system_resources()
        start_time = time.time()
        
        model = LocalRerankerModel(device=device)
        model.load()
        
        load_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 模型加载: {load_time:.2f}s")
        print(f"   内存增长: {(after_res['memory_used'] - before_res['memory_used']):.2f} GB")
        
        # 推理测试
        query = "背包的质量怎么样？"
        candidates = ["用料厚实", "质量不错", "拉链容易坏", "颜色很漂亮"]
        
        before_res = get_system_resources()
        start_time = time.time()
        
        result = model.rerank(query, candidates)
        
        infer_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 推理时间: {infer_time:.3f}s (4 个候选)")
        print(f"   吞吐量: {4/infer_time:.1f} 候选/秒")
        print(f"   CPU 使用: {after_res['cpu_percent']:.1f}%")
        
        return {
            'type': 'pytorch_reranker',
            'load_time': load_time,
            'infer_time': infer_time,
            'cpu_percent': after_res['cpu_percent'],
        }
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_openvino_reranker():
    """测试 OpenVINO 重排模型"""
    print_section("OpenVINO 重排模型测试")
    
    try:
        from decathlon_voc_analyzer.stage3_retrieval.openvino_models import OpenVINORerankerModel, get_openvino_device
        
        device = get_openvino_device()
        print(f"📍 设备: {device}")
        
        before_res = get_system_resources()
        start_time = time.time()
        
        model = OpenVINORerankerModel(device=device)
        model.load()
        
        load_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 模型加载: {load_time:.2f}s")
        print(f"   内存增长: {(after_res['memory_used'] - before_res['memory_used']):.2f} GB")
        
        # 推理测试
        query = "背包的质量怎么样？"
        candidates = ["用料厚实", "质量不错", "拉链容易坏", "颜色很漂亮"]
        
        before_res = get_system_resources()
        start_time = time.time()
        
        result = model.rerank(query, candidates)
        
        infer_time = time.time() - start_time
        after_res = get_system_resources()
        
        print(f"✅ 推理时间: {infer_time:.3f}s (4 个候选)")
        print(f"   吞吐量: {4/infer_time:.1f} 候选/秒")
        print(f"   CPU 使用: {after_res['cpu_percent']:.1f}%")
        
        return {
            'type': 'openvino_reranker',
            'device': device,
            'load_time': load_time,
            'infer_time': infer_time,
            'cpu_percent': after_res['cpu_percent'],
        }
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def print_comparison(pytorch_result, openvino_result, task_name: str):
    """打印性能对比"""
    print_section(f"{task_name} 性能对比")
    
    if pytorch_result and openvino_result:
        pt_infer = pytorch_result['infer_time']
        ov_infer = openvino_result['infer_time']
        speedup = pt_infer / ov_infer
        
        print(f"PyTorch (CPU):")
        print(f"  推理时间: {pt_infer:.3f}s")
        print(f"  CPU 使用: {pytorch_result['cpu_percent']:.1f}%")
        print()
        print(f"OpenVINO ({openvino_result.get('device', 'CPU')}):")
        print(f"  推理时间: {ov_infer:.3f}s")
        print(f"  CPU 使用: {openvino_result['cpu_percent']:.1f}%")
        print()
        print(f"⚡ 性能提升: {speedup:.2f}x")
    else:
        print("❌ 无法进行对比")


def main():
    """主函数"""
    print(f"\n{'#'*70}")
    print(f"#  PyTorch vs OpenVINO 性能对比测试")
    print(f"#  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")
    
    # 检查 OpenVINO
    available_devices = check_openvino()
    
    results = []
    
    # 测试嵌入模型
    print("\n" + "="*70)
    print("  嵌入模型测试")
    print("="*70)
    
    try:
        pt_emb = test_pytorch_embedding()
        results.append(pt_emb)
    except KeyboardInterrupt:
        print("\n⏸️  中断...")
    except Exception as e:
        print(f"\n❌ PyTorch 嵌入模型测试失败: {e}")
    
    try:
        ov_emb = test_openvino_embedding()
        results.append(ov_emb)
    except KeyboardInterrupt:
        print("\n⏸️  中断...")
    except Exception as e:
        print(f"\n❌ OpenVINO 嵌入模型测试失败: {e}")
    
    if len(results) >= 2:
        print_comparison(results[0], results[1], "嵌入模型")
    
    # 测试重排模型
    print("\n" + "="*70)
    print("  重排模型测试")
    print("="*70)
    
    results_reranker = []
    
    try:
        pt_rer = test_pytorch_reranker()
        results_reranker.append(pt_rer)
    except KeyboardInterrupt:
        print("\n⏸️  中断...")
    except Exception as e:
        print(f"\n❌ PyTorch 重排模型测试失败: {e}")
    
    try:
        ov_rer = test_openvino_reranker()
        results_reranker.append(ov_rer)
    except KeyboardInterrupt:
        print("\n⏸️  中断...")
    except Exception as e:
        print(f"\n❌ OpenVINO 重排模型测试失败: {e}")
    
    if len(results_reranker) >= 2:
        print_comparison(results_reranker[0], results_reranker[1], "重排模型")
    
    print_section("测试完成")


if __name__ == "__main__":
    main()
