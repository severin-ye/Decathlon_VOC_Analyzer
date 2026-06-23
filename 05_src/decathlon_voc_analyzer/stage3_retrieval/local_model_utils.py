"""本地小参数模型推理工具模块

支持 Qwen3 系列小参数模型的加载和推理：
- Qwen3-Embedding-0.6B：文本嵌入
- Qwen3-Reranker-0.6B：文本重排
- Qwen3-VL-2B：多模态（图像+文本）重排
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from transformers import (
    AutoModel,
    AutoModelForCausalLM,
    AutoProcessor,
    AutoTokenizer,
    Qwen3VLForConditionalGeneration,
)

logger = logging.getLogger(__name__)


def resolve_device(device: str) -> str:
    """将 'auto' 设备字符串转换为实际设备字符串
    
    Args:
        device: 设备选择（"cuda"、"xpu"、"cpu" 或 "auto"）
        
    Returns:
        实际设备字符串（"xpu"、"cuda"、"cpu" 中的一个）
    """
    if device == "auto":
        # 优先级：XPU (Intel GPU) > CUDA > CPU
        try:
            import intel_extension_for_pytorch as ipex
            if ipex.xpu.is_available():
                return "xpu"
        except (ImportError, AttributeError):
            pass
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


class LocalEmbeddingModel:
    """Qwen3-Embedding-0.6B 本地嵌入模型"""

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", device: str = "auto"):
        """初始化嵌入模型
        
        Args:
            model_name: 模型名称或本地路径
            device: 设备选择（"cuda"、"cpu" 或 "auto"）
        """
        self.model_name = model_name
        self.device = resolve_device(device)
        self.model = None
        self.tokenizer = None

    def load(self) -> None:
        """加载模型和分词器"""
        if self.model is not None:
            return
        logger.info(f"Loading Qwen3-Embedding from {self.model_name} on {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            torch_dtype=torch.float32,
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Qwen3-Embedding model loaded on {self.device}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """获取文本嵌入向量
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表（每条文本一个向量）
        """
        if self.model is None:
            self.load()

        # Qwen3-Embedding 预期为单个文本或列表，返回 (batch_size, embedding_dim)
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :]  # 使用 [CLS] 位置

        # 转为 float32 并归一化
        embeddings_np = embeddings.detach().cpu().numpy().astype(np.float32)
        normalized = embeddings_np / (np.linalg.norm(embeddings_np, axis=1, keepdims=True) + 1e-8)
        return normalized.tolist()

    def embed_single(self, text: str) -> list[float]:
        """获取单条文本的嵌入"""
        return self.embed([text])[0]


class LocalRerankerModel:
    """Qwen3-Reranker-0.6B 本地重排模型"""

    def __init__(self, model_name: str = "Qwen/Qwen3-Reranker-0.6B", device: str = "auto"):
        """初始化重排模型
        
        Args:
            model_name: 模型名称或本地路径
            device: 设备选择（"cuda"、"cpu" 或 "auto"）
        """
        self.model_name = model_name
        self.device = resolve_device(device)
        self.model = None
        self.tokenizer = None
        self._instruction = "Given a web search query, retrieve relevant passages that answer the query"

    def load(self) -> None:
        """加载模型和分词器"""
        if self.model is not None:
            return
        logger.info(f"Loading Qwen3-Reranker from {self.model_name} on {self.device}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, padding_side="left", trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            torch_dtype=torch.float32,
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Qwen3-Reranker model loaded on {self.device}")

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

    def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: Optional[int] = None,
    ) -> list[dict[str, object]]:
        """对文档进行重排
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_n: 返回的前N个结果（None 则返回所有）
            
        Returns:
            包含 index 和 relevance_score 的字典列表
        """
        if self.model is None:
            self.load()

        if top_n is None:
            top_n = len(documents)

        pairs = [self._format_prompt(query, doc) for doc in documents]
        token_true_id = self.tokenizer("yes", add_special_tokens=False).input_ids[0]
        token_false_id = self.tokenizer("no", add_special_tokens=False).input_ids[0]

        inputs = self.tokenizer(
            pairs,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=8192,
            add_special_tokens=False,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            batch_scores = outputs.logits[:, -1, :]
            true_vector = batch_scores[:, token_true_id]
            false_vector = batch_scores[:, token_false_id]
            pair_scores = torch.stack([false_vector, true_vector], dim=1)
            scores = torch.nn.functional.log_softmax(pair_scores, dim=1)[:, 1].exp().detach().cpu().numpy()

        # 创建排序结果
        results = [
            {"index": i, "relevance_score": float(scores[i])}
            for i in range(len(documents))
        ]
        # 按分数降序排列
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:top_n]


class LocalMultimodalRerankerModel:
    """Qwen3-VL-2B 本地多模态重排模型"""

    def __init__(self, model_name: str = "Qwen/Qwen3-VL-2B-Instruct", device: str = "auto"):
        """初始化多模态重排模型
        
        Args:
            model_name: 模型名称或本地路径
            device: 设备选择（"cuda"、"cpu" 或 "auto"）
        """
        self.model_name = model_name
        self.device = resolve_device(device)
        self.model = None
        self.processor = None

    def load(self) -> None:
        """加载模型和处理器"""
        if self.model is not None:
            return
        logger.info(f"Loading Qwen3-VL from {self.model_name} on {self.device}")
        # 注意: 这里假设 Qwen3-VL-2B 与 Qwen2.5-VL 兼容
        # 如果需要调整，根据官方文档修改
        self.processor = AutoProcessor.from_pretrained(self.model_name, trust_remote_code=True)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            self.model_name,
            torch_dtype=torch.float32,
            trust_remote_code=True,
        )
        self.model.to(self.device)
        self.model.eval()
        logger.info(f"Qwen3-VL model loaded on {self.device}")

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, object]],
        top_n: Optional[int] = None,
    ) -> list[dict[str, object]]:
        """对图像候选进行多模态重排
        
        Args:
            query: 查询文本
            candidates: 候选列表，每个包含 {"index": int, "text": str, "image_path": str}
            top_n: 返回的前N个结果
            
        Returns:
            包含 index 和 relevance_score 的字典列表
        """
        if self.model is None:
            self.load()

        if top_n is None:
            top_n = len(candidates)

        scores = []

        for candidate in candidates:
            index = candidate.get("index", 0)
            text_hint = candidate.get("text", "")
            image_path = candidate.get("image_path")

            # 构造多模态输入
            # 提示词要求模型给出相关性分数
            prompt = (
                f"Score the relevance of this image to the query on a scale of 0.0 to 1.0. "
                f"Query: {query}\nImage context: {text_hint}\n"
                f"Return only a JSON object with a single 'score' field, e.g., {{'score': 0.8}}"
            )

            try:
                if image_path and Path(image_path).exists():
                    image = Image.open(image_path).convert("RGB")
                    inputs = self.processor(
                        text=prompt,
                        images=[image],
                        return_tensors="pt",
                    ).to(self.device)
                else:
                    # 如果图像不存在，使用纯文本
                    inputs = self.processor(text=prompt, return_tensors="pt").to(self.device)

                with torch.no_grad():
                    outputs = self.model.generate(
                        **inputs,
                        max_new_tokens=50,
                        do_sample=False,
                    )

                response_text = self.processor.decode(outputs[0], skip_special_tokens=True)

                # 尝试解析JSON并提取分数
                try:
                    result = json.loads(response_text)
                    score = float(result.get("score", 0.0))
                except (json.JSONDecodeError, ValueError, TypeError):
                    # 如果解析失败，尝试提取数字
                    import re

                    numbers = re.findall(r"\d+\.?\d*", response_text)
                    score = float(numbers[0]) / 100.0 if numbers else 0.0

                score = max(0.0, min(1.0, score))
                scores.append({"index": index, "relevance_score": score})

            except Exception as e:
                logger.warning(f"Error scoring candidate {index}: {e}")
                scores.append({"index": index, "relevance_score": 0.0})

        # 按分数降序排列
        scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scores[:top_n]


# 全局模型实例缓存
_embedding_model: Optional[LocalEmbeddingModel] = None
_reranker_model: Optional[LocalRerankerModel] = None
_multimodal_reranker_model: Optional[LocalMultimodalRerankerModel] = None


@lru_cache(maxsize=1)
def get_embedding_model(model_name: str = "Qwen/Qwen3-Embedding-0.6B") -> LocalEmbeddingModel:
    """获取或创建嵌入模型实例"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = LocalEmbeddingModel(model_name)
    return _embedding_model


@lru_cache(maxsize=1)
def get_reranker_model(model_name: str = "Qwen/Qwen3-Reranker-0.6B") -> LocalRerankerModel:
    """获取或创建重排模型实例"""
    global _reranker_model
    if _reranker_model is None:
        _reranker_model = LocalRerankerModel(model_name)
    return _reranker_model


@lru_cache(maxsize=1)
def get_multimodal_reranker_model(
    model_name: str = "Qwen/Qwen3-VL-2B-Instruct",
) -> LocalMultimodalRerankerModel:
    """获取或创建多模态重排模型实例"""
    global _multimodal_reranker_model
    if _multimodal_reranker_model is None:
        _multimodal_reranker_model = LocalMultimodalRerankerModel(model_name)
    return _multimodal_reranker_model
