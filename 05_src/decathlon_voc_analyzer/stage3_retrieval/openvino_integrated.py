"""OpenVINO 直接集成 - 支持 Intel GPU/NPU 本地模型推理"""

import logging
import os
from typing import List

import numpy as np
import torch
from huggingface_hub import snapshot_download
from transformers import AutoModel, AutoModelForCausalLM, AutoTokenizer

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

try:
    from optimum.intel.openvino import OVModelForCausalLM, OVModelForFeatureExtraction
    OPTIMUM_OPENVINO_AVAILABLE = True
except ImportError:
    OPTIMUM_OPENVINO_AVAILABLE = False

try:
    import intel_extension_for_pytorch as ipex
    IPEX_AVAILABLE = True
except ImportError:
    IPEX_AVAILABLE = False

logger = logging.getLogger(__name__)


_DEVICE_ENV_VARS = ("OPENVINO_DEVICE", "OPENVINO_INFERENCE_DEVICE", "LOCAL_MODEL_DEVICE")
_DEVICE_PRIORITY = ("NPU", "GPU", "CPU")


def _normalize_device(device: str | None) -> str:
    if not device:
        return "AUTO"
    normalized = device.strip().upper()
    if normalized in {"GPU", "NPU", "CPU", "AUTO"}:
        return normalized
    return "AUTO"


def _env_requested_device() -> str | None:
    for name in _DEVICE_ENV_VARS:
        value = os.getenv(name)
        if value:
            return _normalize_device(value)
    return None


def _available_openvino_devices() -> list[str]:
    if not OPENVINO_AVAILABLE:
        return []
    try:
        return list(Core().available_devices)
    except Exception as e:
        logger.warning(f"OpenVINO 设备检测失败: {e}")
        return []


def get_openvino_device() -> str:
    """获取最佳 OpenVINO 设备"""
    requested = _env_requested_device()
    available_devices = _available_openvino_devices()
    logger.info(f"📱 OpenVINO 可用设备: {available_devices}")

    if requested and requested != "AUTO":
        if requested in available_devices or requested == "CPU":
            logger.info(f"✅ 使用环境变量指定的 OpenVINO 设备: {requested}")
            return requested
        logger.warning(f"环境变量指定了 {requested}，但 OpenVINO 当前不可用: {available_devices}")

    # 优先级：NPU > GPU > CPU。NPU 编译失败时，加载阶段会自动降级到 GPU。
    for device in _DEVICE_PRIORITY:
        if device in available_devices or device == "CPU":
            logger.info(f"✅ 自动选择 OpenVINO 设备: {device}")
            return device

    return "CPU"


def _openvino_device_candidates(preferred: str) -> list[str]:
    available_devices = _available_openvino_devices()
    candidates: list[str] = []

    if preferred == "AUTO":
        ordered = _DEVICE_PRIORITY
    elif preferred == "NPU":
        ordered = ("NPU", "GPU", "CPU")
    elif preferred == "GPU":
        ordered = ("GPU", "CPU")
    else:
        ordered = (preferred,)

    for device in ordered:
        if device == "CPU" or device in available_devices:
            candidates.append(device)

    return candidates or ["CPU"]


def _torch_device_for(device: str) -> str:
    if device.lower() == "gpu":
        try:
            if IPEX_AVAILABLE and ipex.xpu.is_available():
                return "xpu"
        except AttributeError:
            pass
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _score_from_logits(logits: torch.Tensor, token_true_id: int, token_false_id: int) -> np.ndarray:
    if isinstance(logits, np.ndarray):
        logits = torch.from_numpy(logits)
    batch_scores = logits[:, -1, :]
    true_vector = batch_scores[:, token_true_id]
    false_vector = batch_scores[:, token_false_id]
    pair_scores = torch.stack([false_vector, true_vector], dim=1)
    return torch.nn.functional.log_softmax(pair_scores, dim=1)[:, 1].exp().detach().cpu().numpy()


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
        self.uses_openvino = False
    
    def load(self) -> None:
        """加载并优化模型"""
        logger.info(f"🚀 加载嵌入模型...")
        
        # 确定实际设备
        if self.device.lower() == "auto":
            self.actual_device = get_openvino_device()
        else:
            self.actual_device = _normalize_device(self.device)
        
        try:
            if OPENVINO_AVAILABLE and OPTIMUM_OPENVINO_AVAILABLE:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
                errors: list[str] = []
                for device in _openvino_device_candidates(self.actual_device):
                    try:
                        logger.info(f"⚙️ 使用 OpenVINO 在 {device} 上加载嵌入模型...")
                        self.model = OVModelForFeatureExtraction.from_pretrained(
                            self.model_name,
                            export=True,
                            compile=True,
                            device=device,
                            trust_remote_code=True,
                        )
                        self.actual_device = device
                        self.uses_openvino = True
                        logger.info(f"✅ 嵌入模型已编译到 OpenVINO {self.actual_device}")
                        return
                    except Exception as e:
                        errors.append(f"{device}: {e}")
                        logger.warning(f"OpenVINO {device} 编译嵌入模型失败，尝试下一个设备: {e}")
                logger.warning("OpenVINO 嵌入模型编译全部失败，回退 PyTorch: " + " | ".join(errors))

            if OPENVINO_AVAILABLE and not OPTIMUM_OPENVINO_AVAILABLE:
                logger.warning("未安装 optimum-intel，无法把 Hugging Face 模型导出/编译到 OpenVINO；回退 PyTorch")

            # 下载并加载 PyTorch 后备模型
            model_path = snapshot_download(self.model_name)
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModel.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            
            torch_device = _torch_device_for(self.actual_device)
            self.model.to(torch_device)
            
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
                if not self.uses_openvino:
                    inputs = inputs.to(next(self.model.parameters()).device)
                
                # 推理
                outputs = self.model(**inputs)
                
                # 提取嵌入
                hidden_state = outputs.last_hidden_state
                if isinstance(hidden_state, np.ndarray):
                    embedding = hidden_state[0, 0, :].astype(np.float32).tolist()
                else:
                    embedding = hidden_state[0, 0, :].cpu().tolist()
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
        self.uses_openvino = False
        self._instruction = "Given a web search query, retrieve relevant passages that answer the query"
    
    def load(self) -> None:
        """加载并优化模型"""
        logger.info(f"🚀 加载重排模型...")
        
        # 确定实际设备
        if self.device.lower() == "auto":
            self.actual_device = get_openvino_device()
        else:
            self.actual_device = _normalize_device(self.device)
        
        try:
            if OPENVINO_AVAILABLE and OPTIMUM_OPENVINO_AVAILABLE:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    padding_side="left",
                    trust_remote_code=True,
                )
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token
                errors: list[str] = []
                for device in _openvino_device_candidates(self.actual_device):
                    try:
                        logger.info(f"⚙️ 使用 OpenVINO 在 {device} 上加载重排模型...")
                        self.model = OVModelForCausalLM.from_pretrained(
                            self.model_name,
                            export=True,
                            compile=True,
                            device=device,
                            trust_remote_code=True,
                        )
                        self.actual_device = device
                        self.uses_openvino = True
                        logger.info(f"✅ 重排模型已编译到 OpenVINO {self.actual_device}")
                        return
                    except Exception as e:
                        errors.append(f"{device}: {e}")
                        logger.warning(f"OpenVINO {device} 编译重排模型失败，尝试下一个设备: {e}")
                logger.warning("OpenVINO 重排模型编译全部失败，回退 PyTorch: " + " | ".join(errors))

            if OPENVINO_AVAILABLE and not OPTIMUM_OPENVINO_AVAILABLE:
                logger.warning("未安装 optimum-intel，无法把 Hugging Face 模型导出/编译到 OpenVINO；回退 PyTorch")

            # 下载并加载 PyTorch 后备模型
            model_path = snapshot_download(self.model_name)
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, padding_side="left", trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            torch_device = _torch_device_for(self.actual_device)
            self.model.to(torch_device)
            
            self.model.eval()
            logger.info("✅ 重排模型加载完成")
            
        except Exception as e:
            logger.error(f"加载失败: {e}")
            raise

    def _format_prompt(self, query: str, document: str) -> str:
        prefix = (
            '<|im_start|>system\n'
            'Judge whether the Document meets the requirements based on the Query and the Instruct provided. '
            'Note that the answer can only be "yes" or "no".<|im_end|>\n'
            '<|im_start|>user\n'
        )
        suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
        body = f"<Instruct>: {self._instruction}\n\n<Query>: {query}\n\n<Document>: {document}"
        return f"{prefix}{body}{suffix}"
    
    def rerank(self, query: str, candidates: List[str]) -> List[dict]:
        """重排候选文本"""
        pairs = [self._format_prompt(query, candidate) for candidate in candidates]
        token_true_id = self.tokenizer("yes", add_special_tokens=False).input_ids[0]
        token_false_id = self.tokenizer("no", add_special_tokens=False).input_ids[0]

        inputs = self.tokenizer(
            pairs,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=8192,
            add_special_tokens=False,
        )
        if not self.uses_openvino:
            inputs = inputs.to(next(self.model.parameters()).device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits if hasattr(outputs, "logits") else outputs[0]
            scores = _score_from_logits(logits, token_true_id, token_false_id)

        results = [
            {"index": idx, "relevance_score": float(scores[idx])}
            for idx in range(len(candidates))
        ]
        results.sort(key=lambda item: item["relevance_score"], reverse=True)
        return results
