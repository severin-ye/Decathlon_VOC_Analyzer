# API、配置、LLM 与提示词层

## 模块定位

本模块对应 `app/`、`llm/` 和 `prompts/`。其中 `app/api` 提供 FastAPI 接口，`app/core/config.py` 管理环境变量和路径，`app/core/runtime_policy.py` 控制运行降级策略，`llm/gateway.py` 封装 Qwen 调用，`prompts/registry.py` 和提示词 Markdown 文件统一管理业务提示词。

论文中可将该模块定义为“系统接口与模型接入层”。它不直接创造 VOC 洞察，但决定系统如何被调用、如何接入模型、如何控制降级以及如何保证提示词版本可追踪。

## 主要创新点

1. API 与批处理共享服务层：FastAPI routes 调用的服务与工作流批处理使用同一组 service，避免 API 逻辑和实验逻辑分叉。
2. 运行策略显式化：`RuntimeExecutionPolicy` 使用 `allow_degradation` 和 `full_power` 控制是否允许从真实模型降级到 heuristic。严格实验可以阻止静默降级，开发调试则允许离线跑通。
3. OpenAI 兼容 Qwen 网关：`QwenChatGateway` 优先使用 `langchain_openai.ChatOpenAI` 的 structured output；不可用时退回 OpenAI SDK 的 JSON mode。该设计降低了框架依赖风险。
4. 提示词集中注册：所有业务提示词集中在 `05_src/decathlon_voc_analyzer/prompts/`，并通过 registry 获取。问题生成缓存还会绑定 prompt digest，保证提示词变化会触发重新生成。
5. 模型与后端可配置：配置层集中管理 qwen-plus、embedding、reranker、VL reranker、CLIP、本地模型、Qdrant、输出目录和超时参数，便于论文实验描述与复现。

## 具体实现

`config.py` 使用 Pydantic Settings 从 `.env` 和环境变量读取配置。重要路径包括数据根目录、标准化输出目录、方面输出目录、索引目录、报告目录、feedback 目录、replay 目录和 HTML 输出目录。模型配置包括 `qwen_plus_model`、`qwen_embedding_model`、`qwen_reranker_model`、`qwen_vl_reranker_model`、`clip_vl_embedding_model` 和本地 Qwen3 系列模型名。

`runtime_policy.py` 提供三类关键函数。`resolve_llm_permission()` 判断当前请求是否可调用 LLM；如果缺少 API Key 且允许降级，则返回 warning 并改用 heuristic；如果严格模式禁止降级，则抛出 `RuntimePolicyError`。`handle_llm_failure()` 处理调用失败。`validate_full_power_prerequisites()` 在满血模式下检查 Qdrant、本地 embedding、本地 reranker 和本地多模态 reranker 是否满足要求。

`QwenChatGateway.invoke_json()` 接收 LangChain prompt template 和变量，返回 JSON dict。若可用，它通过 LangChain 的 `with_structured_output(schema)` 获得结构化结果；否则使用 OpenAI SDK 的 `response_format={"type":"json_object"}`。这使评论抽取、问题生成和报告生成都可以共享同一模型调用网关。

`app/api/main.py` 注册 `/health`、dataset、index、reviews 和 analysis 路由。README 中列出的主要接口包括 `/api/v1/dataset/overview`、`/api/v1/dataset/normalize`、`/api/v1/index/overview`、`/api/v1/index/build`、`/api/v1/reviews/extract` 和 `/api/v1/analysis/product`。

## 与文献思路的关系

结构化输出能力是 LLM 工程化的重要基础 [1]。本项目通过 schema、JSON mode 和 prompt registry 把 LLM 限定为结构化组件。

LangChain 的 Qwen 集成文档说明了 structured output 和消息封装能力 [2]。本项目使用 OpenAI 兼容 API 与 LangChain 封装，以便在不同部署环境下保持调用方式一致。

RAG 系统要求模型调用、检索、缓存和评估之间保持配置可复现 [3]。本模块通过集中配置和运行策略让论文实验能够明确区分模型版本、后端类型和降级状态。

## 可写入论文的表述

本文将模型接入、提示词管理和运行策略从业务逻辑中解耦。系统通过统一网关调用 Qwen 系列模型，并使用 schema 和 JSON mode 约束输出格式；同时通过运行策略显式控制是否允许自动降级。这一设计使系统既能在开发环境中离线验证，也能在论文实验中保持严格、可复现的模型执行条件。

## 参考文献

[1] Liu, Y. et al. Are LLMs Good at Structured Outputs? Information Processing & Management, 2024.

[2] LangChain. ChatQwen Integration Documentation. 2024.

[3] Lewis, P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020.
