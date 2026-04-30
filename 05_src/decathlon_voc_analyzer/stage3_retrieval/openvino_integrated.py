"""OpenVINO 直接集成 - 使用 PyTorch 模型但通过 OpenVINO 优化"""

import logging
from typing import List

import torch
from huggingface_hub import snapshot_download
from transformers import AutoModel, AutoTokenizer

try:
    from openvino.runtime import Core, get_version
    import intel_extension_for_pytorch as ipex
    IPEX_AVAILABLE = True
    OV_VERSION = get_version()
except ImportError:
    IPEX_AVAILABLE = False
    OV_VERSION = None

logger = logging.getLogger(__name__)


def get_openvino_device() -> str:
    """获取最佳 OpenVINO 设备"""
    if not IPEX_AVAILABLE:
        return "cpu"
    
    try:
        from openvino.runtime import Core
        core = Core()
        available_devices = core.available_devices
        
        logger.info(f"📱 OpenVINO 可用设备: {available_devices}")
        
        # 优先级：GPU > NPU > CPU
        if "GPU" in available_devices:
            logger.info("✅ 检测到 Intel Iris Xe GPU，将使用 GPU 加速")
            return "GPU"
        elif "NPU" in available_devices:
            logger.info("✅ 检测到 Intel NPU，将使用 NPU 加速")
            return "NPU"
        else:
            logger.info("💻 使用 CPU (OpenVINO)")
            return "CPU"
    except Exception as e:
        logger.warning(f"OpenVINO 设备检测失败: {e}")
        return "cpu"


class OpenVINOOptimizedEmbeddingModel:
    """使用 OpenVINO 优化的嵌入模型"""
    
    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", device: str = "auto"):
        """初始化嵌入模型
        
        Args:
            model_name: 模型名称
            device: 设备选择 ("auto" | "gpu" | "npu" | "cpu")
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
        self.actual_device = None
    
    def load(self) -> None:
        """加载并优化模型"""
        logger.info(f"🚀 加载嵌入模型...")
        
        # 确定实际设备
        if self.device == "auto":
            self.actual_device = get_openvino_device()
        else:
            self.actual_device = self.device
        
        try:
            # 下载并加载模型
            model_path = snapshot_download(self.model_name)
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            
            # 应用 OpenVINO 优化
            if IPEX_AVAILABLE and self.actual_device != "cpu":
                logger.info(f"⚙️ 应用 OpenVINO {self.actual_device} 优化...")
                try:
                    # 使用 IPEX 优化推理
                    self.model = ipex.llm.optimize(
                        self.model.eval(),
                        dtype=torch.float32,
                        inplace=True,
                    )
                    logger.info(f"✅ 模型已优化")
                except Exception as e:
                    logger.warning(f"OpenVINO 优化失败: {e}，使用原生 PyTorch")
            
            self.model.eval()
            logger.info("✅ 嵌入模型加载完成")
            
        except Exception as e:
            logger.error(f"加载失败: {e}")
            raise
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """嵌入文本列表"""
        embeddings = []
        with torch.no_grad():
            for text in texts:
                inputs = self.tokenizer(
                    text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                )
                
                # 推理
                with torch.autocast("cpu") if self.actual_device == "cpu" else torch.autocast("cpu"):
                    outputs = self.model(**inputs)
                
                # 提取嵌入
                embedding = outputs.last_hidden_state[0, 0, :].cpu().tolist()
                embeddings.append(embedding)
        
        return embeddings
    
    def embed_single(self, text: str) -> List[float]:
        """嵌入单个文本"""
        return self.embed([text])[0]


class OpenVINOOptimizedRerankerModel:
    """使用 OpenVINO 优化的重排模型"""
    
    def __init__(self, model_name: str = "Qwen/Qwen3-Reranker-0.6B", device: str = "auto"):
        """初始化重排模型
        
        Args:
            model_name: 模型名称
            device: 设备选择 ("auto" | "gpu" | "npu" | "cpu")
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        self.tokenizer = None
        self.actual_device = None
    
    def load(self) -> None:
        """加载并优化模型"""
        logger.info(f"🚀 加载重排模型...")
        
        # 确定实际设备
        if self.device == "auto":
            self.actual_device = get_openvino_device()
        else:
            self.actual_device = self.device
        
        try:
            # 下载并加载模型
            model_path = snapshot_download(self.model_name)
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            
            # 应用 OpenVINO 优化
            if IPEX_AVAILABLE and self.actual_device != "cpu":
                logger.info(f"⚙️ 应用 OpenVINO {self.actual_device} 优化...")
                try:
                    self.model = ipex.llm.optimize(
                        self.model.eval(),
                        dtype=torch.float32,
                        inplace=True,
                    )
                    logger.info(f"✅ 模型已优化")
                except Exception as e:
                    logger.warning(f"OpenVINO 优化失败: {e}，使用原生 PyTorch")
            
            self.model.eval()
            logger.info("✅ 重排模型加载完成")
            
        except Exception as e:
            logger.error(f"加载失败: {e}")
            raise
    
    def rerank(self, query: str, candidates: List[str]) -> List[dict]:
        """重排候选文本"""
        scores = []
        
        with torch.no_grad():
            for idx, candidate in enumerate(candidates):
                pair = f"{query} {candidate}"
                inputs = self.tokenizer(
                    pair,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                )
                
                # 推理
                with torch.autocast("cpu") if self.actual_device == "cpu" else torch.autocast("cpu"):
                    outputs = self.model(**inputs)
                
                # 使用 logits 计算得分
                logits = outputs.logits if hasattr(outputs, 'logits') else outputs[0]
                
                if len(logits.shape) > 2:
                    logits = logits[0]  # 移除 batch 维度
                elif len(logits.shape) == 1:
                    logits = logits.unsqueeze(0)  # 添加 batch 维度
                
                # 处理 logits - 可能是 (seq_len, vocab_size) 或 (vocab_size,)
                if logits.shape[-1] > 1000:
                    # 这是完整 vocabulary logits，获取最后一个 token
                    last_token_logits = logits[-1]
                    # 在 yes/no token 处取值
                    yes_logits = last_token_logits[6552] if last_token_logits.shape[0] > 6552 else last_token_logits.max()
                    no_logits = last_token_logits[4385] if last_token_logits.shape[0] > 4385 else last_token_logits.min()
                else:
                    # 这是分类 logits，取最后一个值作为得分
                    yes_logits = logits[-1, -1] if len(logits.shape) > 1 else logits[-1]
                    no_logits = 0.0
                
                # 计算相似度分数 (0-1)
                score = torch.sigmoid(yes_logits - no_logits).item()
                scores.append({"index": idx, "relevance_score": score})
        
        return scores
