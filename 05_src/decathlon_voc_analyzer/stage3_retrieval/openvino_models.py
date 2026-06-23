"""OpenVINO 优化的本地模型推理（支持 Intel GPU/NPU）"""

import json
import logging
from pathlib import Path
from typing import List

import numpy as np
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModel, AutoProcessor, AutoTokenizer

try:
    try:
        from openvino.runtime import Core, get_version
    except ImportError:
        from openvino import Core, get_version
    OPENVINO_AVAILABLE = True
    OV_VERSION = get_version()
except ImportError:
    OPENVINO_AVAILABLE = False
    OV_VERSION = None

logger = logging.getLogger(__name__)


class OpenVINOEmbeddingModel:
    """使用 OpenVINO 优化的 Qwen3-Embedding-0.6B 模型"""

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", device: str = "AUTO"):
        """初始化嵌入模型
        
        Args:
            model_name: 模型名称或本地路径
            device: 设备选择 ("AUTO" | "GPU" | "NPU" | "CPU")
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
        self.compiled_model = None
        self.infer_request = None
        
        if not OPENVINO_AVAILABLE:
            logger.warning("OpenVINO 未安装，将回退到 PyTorch")
            self._fallback_model = None
    
    def load(self) -> None:
        """加载模型"""
        if not OPENVINO_AVAILABLE:
            logger.warning("OpenVINO 不可用，使用 PyTorch 后备方案")
            self._load_pytorch_fallback()
            return
        
        logger.info(f"🚀 使用 OpenVINO {OV_VERSION} 加载嵌入模型...")
        
        try:
            # 下载模型到本地
            model_path = snapshot_download(self.model_name)
            
            # 加载 tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # 加载原始模型（用于 ONNX 转换）
            pytorch_model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            pytorch_model.eval()
            
            # 转换为 ONNX（如果需要）
            onnx_path = Path(model_path) / "model.onnx"
            if not onnx_path.exists():
                logger.info("⚙️ 导出为 ONNX 格式...")
                self._export_to_onnx(pytorch_model, onnx_path)
            
            # 使用 OpenVINO 编译模型
            logger.info(f"🔧 使用 {self.device} 设备编译模型...")
            core = Core()
            ov_model = core.read_model(str(onnx_path))
            self.compiled_model = core.compile_model(ov_model, self.device)
            self.infer_request = self.compiled_model.create_infer_request()
            
            logger.info(f"✅ 模型已加载到 {self.device} 设备")
            
        except Exception as e:
            logger.error(f"OpenVINO 加载失败: {e}，回退到 PyTorch")
            self._load_pytorch_fallback()
    
    def _load_pytorch_fallback(self) -> None:
        """PyTorch 后备方案"""
        from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import resolve_device
        device = resolve_device("auto")
        from .local_model_utils import LocalEmbeddingModel
        self._fallback_model = LocalEmbeddingModel(self.model_name, device=device)
        self._fallback_model.load()
    
    def _export_to_onnx(self, model, onnx_path: Path) -> None:
        """导出为 ONNX 格式（供 OpenVINO 使用）"""
        try:
            import onnx
            dummy_input = torch.randn(1, 512)
            torch.onnx.export(
                model,
                dummy_input,
                str(onnx_path),
                input_names=["input_ids"],
                output_names=["output"],
                opset_version=14,
            )
            logger.info(f"✅ ONNX 模型已保存: {onnx_path}")
        except ImportError:
            logger.warning("onnx 未安装，使用 PyTorch 推理")
            self._load_pytorch_fallback()
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        if self._fallback_model is not None:
            return self._fallback_model.embed(texts)
        
        if self.compiled_model is None:
            raise RuntimeError("模型未加载")
        
        embeddings = []
        for text in texts:
            embedding = self.embed_single(text)
            embeddings.append(embedding)
        
        return embeddings
    
    def embed_single(self, text: str) -> List[float]:
        """嵌入单个文本
        
        Args:
            text: 单个文本
            
        Returns:
            嵌入向量
        """
        if self._fallback_model is not None:
            return self._fallback_model.embed_single(text)
        
        # 使用 tokenizer 编码
        inputs = self.tokenizer(text, return_tensors="np", truncation=True, max_length=512)
        
        # OpenVINO 推理
        input_dict = {name: data for name, data in inputs.items()}
        results = self.infer_request.infer(input_dict)
        
        # 提取嵌入向量
        embeddings = results[list(results.keys())[0]]
        return embeddings[0].tolist()


class OpenVINORerankerModel:
    """使用 OpenVINO 优化的 Qwen3-Reranker-0.6B 模型"""

    def __init__(self, model_name: str = "Qwen/Qwen3-Reranker-0.6B", device: str = "AUTO"):
        """初始化重排模型
        
        Args:
            model_name: 模型名称或本地路径
            device: 设备选择 ("AUTO" | "GPU" | "NPU" | "CPU")
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
        self.compiled_model = None
        self.infer_request = None
        
        if not OPENVINO_AVAILABLE:
            logger.warning("OpenVINO 未安装，将回退到 PyTorch")
            self._fallback_model = None
    
    def load(self) -> None:
        """加载模型"""
        if not OPENVINO_AVAILABLE:
            logger.warning("OpenVINO 不可用，使用 PyTorch 后备方案")
            self._load_pytorch_fallback()
            return
        
        logger.info(f"🚀 使用 OpenVINO {OV_VERSION} 加载重排模型...")
        
        try:
            # 下载模型到本地
            model_path = snapshot_download(self.model_name)
            
            # 加载 tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # 加载原始模型
            pytorch_model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            pytorch_model.eval()
            
            # 转换为 ONNX（如果需要）
            onnx_path = Path(model_path) / "model.onnx"
            if not onnx_path.exists():
                logger.info("⚙️ 导出为 ONNX 格式...")
                self._export_to_onnx(pytorch_model, onnx_path)
            
            # 使用 OpenVINO 编译模型
            logger.info(f"🔧 使用 {self.device} 设备编译模型...")
            core = Core()
            ov_model = core.read_model(str(onnx_path))
            self.compiled_model = core.compile_model(ov_model, self.device)
            self.infer_request = self.compiled_model.create_infer_request()
            
            logger.info(f"✅ 模型已加载到 {self.device} 设备")
            
        except Exception as e:
            logger.error(f"OpenVINO 加载失败: {e}，回退到 PyTorch")
            self._load_pytorch_fallback()
    
    def _load_pytorch_fallback(self) -> None:
        """PyTorch 后备方案"""
        from decathlon_voc_analyzer.stage3_retrieval.local_model_utils import resolve_device
        device = resolve_device("auto")
        from .local_model_utils import LocalRerankerModel
        self._fallback_model = LocalRerankerModel(self.model_name, device=device)
        self._fallback_model.load()
    
    def _export_to_onnx(self, model, onnx_path: Path) -> None:
        """导出为 ONNX 格式"""
        try:
            import onnx
            dummy_input = torch.randn(1, 512)
            torch.onnx.export(
                model,
                dummy_input,
                str(onnx_path),
                input_names=["input_ids"],
                output_names=["output"],
                opset_version=14,
            )
            logger.info(f"✅ ONNX 模型已保存: {onnx_path}")
        except ImportError:
            logger.warning("onnx 未安装，使用 PyTorch 推理")
            self._load_pytorch_fallback()
    
    def rerank(self, query: str, candidates: List[str]) -> List[dict]:
        """重排候选文本
        
        Args:
            query: 查询文本
            candidates: 候选文本列表
            
        Returns:
            包含 index 和 relevance_score 的字典列表
        """
        if self._fallback_model is not None:
            return self._fallback_model.rerank(query, candidates)
        
        if self.compiled_model is None:
            raise RuntimeError("模型未加载")
        
        scores = []
        for idx, candidate in enumerate(candidates):
            text_pair = f"{query} {candidate}"
            inputs = self.tokenizer(text_pair, return_tensors="np", truncation=True, max_length=512)
            
            # OpenVINO 推理
            input_dict = {name: data for name, data in inputs.items()}
            results = self.infer_request.infer(input_dict)
            
            # 提取得分
            output = results[list(results.keys())[0]]
            score = float(output[0][0])  # 假设输出是相似度分数
            
            scores.append({"index": idx, "relevance_score": score})
        
        return scores


# 工厂函数
def get_openvino_device() -> str:
    """获取可用的 OpenVINO 设备
    
    Returns:
        设备名称 ("GPU" | "NPU" | "CPU")
    """
    if not OPENVINO_AVAILABLE:
        return "CPU"
    
    try:
        core = Core()
        available_devices = core.available_devices
        
        # 优先级：GPU > NPU > CPU
        if "GPU" in available_devices:
            return "GPU"
        elif "NPU" in available_devices:
            return "NPU"
        else:
            return "CPU"
    except Exception as e:
        logger.warning(f"OpenVINO 设备检测失败: {e}")
        return "AUTO"
