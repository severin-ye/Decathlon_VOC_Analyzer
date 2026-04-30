# LangChain与Qwen

## 引用 1

### 外链

https://docs.langchain.com/oss/python/integrations/chat/qwen

### 对应内容整理

LangChain 的 ChatQwen 集成文档在原对话中承担了多个关键角色：

- 证明 ChatQwen 支持图像输入和视频输入
- 证明 ChatQwen 支持 structured output
- 证明 ChatQwen 支持 tool calling

### 本项目使用的部分

- 评论结构化抽取
- 最终综合意见生成
- 改进建议结构化输出

### 使用的原因

它是当前项目生成层与编排层最直接的官方依据。

### 本项目使用的思路

用 LangChain 组织消息与流程，用 ChatQwen 负责评论结构化输出和最终的证据约束总结，不让生成模型替代召回系统。

## 引用 2

### 外链

https://docs.langchain.com/oss/python/langchain/messages

### 对应内容整理

该文档说明了 LangChain 中多模态消息内容块的组织方式。

### 本项目使用的部分

- 商品图像证据与文本证据的消息打包方式

### 使用的原因

本项目最终要把商品图、商品文本和评论证据一起传给生成模型，因此需要一个稳定的多模态消息组织方法。

### 本项目使用的思路

后续系统实现时，使用该文档中的内容块思想，把图像证据、文字证据、来源标识一起打包到生成阶段输入中。

## 引用 3

### 外链

https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-dashscope

### 对应内容整理

该文档提供 Qwen 多模态生成 API 的调用入口和接入方式。

### 本项目使用的部分

- 生成模型的 API 接入依据

### 使用的原因

原始对话明确建议：先用 API 路线跑通生成层，再逐步把召回和 reranker 做成本地可控组件。

### 本项目使用的思路

生成层优先走 DashScope 或 Model Studio API，降低首版闭环难度。

## 引用 4

### 外链

https://www.alibabacloud.com/help/en/model-studio/models

### 对应内容整理

该文档提供 Qwen 多模态模型的上下文长度、单图限制和型号差异信息。

### 本项目使用的部分

- 生成模型选型依据
- 证据数量控制依据

### 使用的原因

本项目要把多张商品图和若干文本证据传给生成模型，因此必须明确输入上限和成本边界。

### 本项目使用的思路

把它用于约束证据包大小，例如在最终生成时只传少量高质量商品图和关键文本块，而不是把所有候选都送给模型。

## 引用 5

### 外链

https://github.com/QwenLM/Qwen3-VL-Embedding

### 对应内容整理

Qwen3-VL-Embedding 官方仓库在原对话中承担了检索与精排主线的主要依据：

- Embedding 模型负责 initial recall
- Reranker 模型负责 re-ranking stage
- 支持文本、图像、截图、视频与混合输入

### 本项目使用的部分

- 商品图像和商品文本统一向量化
- 粗召回与 reranker 的角色划分
- 2B 和 8B 模型的实施层选择逻辑

### 使用的原因

这是本项目 Native Multimodal 召回路线最直接的核心组件来源。

### 本项目使用的思路

MVP 先采用较轻量的 embedding 与 reranker 组合，先打通商品图文召回和评论驱动查询，后续再考虑更重模型和更细粒度视觉证据。
