# LangChain + Qwen 落地

## 组件分工

- LangChain：负责编排、structured output、消息组织、工具调用
- ChatQwen：负责评论结构化抽取与最终生成
- Qwen3-VL-Embedding：负责商品图像与文本召回
- Qwen3-VL-Reranker：负责精排

## 起步版本建议

- 先用 API 方式接入生成模型
- embedding 与 reranker 可逐步本地化
- 先做页级或对象级召回，不强行一开始就做区域级

## 最小可用技术组合

- ChatQwen
- Qwen3-VL-Embedding-2B
- Qwen3-VL-Reranker-2B
- Qdrant

## 为什么这样组合

- 降低第一阶段实施复杂度
- 保证原始模态召回能力
- 保留后续升级到更细粒度方案的空间

## 后续升级方向

- 更强 embedding 或 reranker
- 更复杂的区域级证据索引
- 更强的评估与错误分析工具链
