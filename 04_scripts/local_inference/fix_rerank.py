import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
file_path = PROJECT_ROOT / "05_src/decathlon_voc_analyzer/stage3_retrieval/openvino_integrated.py"
content = file_path.read_text()

old_code = '''    def rerank(self, query: str, candidates: List[str]) -> List[dict]:
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
                
                if len(logits.shape) > 1:
                    logits = logits[0]
                
                # 获取 yes/no token 的 logits
                yes_logits = logits[6552]  # Qwen3 中 'yes' token ID
                no_logits = logits[4385]   # Qwen3 中 'no' token ID
                
                # 计算相似度分数 (0-1)
                score = torch.sigmoid(yes_logits - no_logits).item()
                scores.append({"index": idx, "relevance_score": score})
        
        return scores'''

new_code = '''    def rerank(self, query: str, candidates: List[str]) -> List[dict]:
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
        
        return scores'''

content = content.replace(old_code, new_code)
file_path.write_text(content)
print("✅ 已修复 rerank 方法")
