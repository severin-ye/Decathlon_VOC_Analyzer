# LangChain Graph RAG JSON格式

**User:**   
**Created:**   
**Updated:**   
**Exported:** 3/18/2026 19:00:26  
**Link:** [https://chatgpt.com/share/69626001-ace0-8002-85d8-c6d753548e98](https://chatgpt.com/share/69626001-ace0-8002-85d8-c6d753548e98)  

## Prompt:
langchain和graph rag如何保证本地模型的输出符合指定的json格式

他们的实现和API版本好像有不一样。

详细了解原理和代码。

## Response:
为了更深入地分析，请问你更关注哪一方面：

1.  使用LangChain和Graph RAG时，如何提示（prompt）本地LLM严格输出JSON格式？
2.  它们在代码层面（如langchain.schema、output parser等）如何解析与验证输出格式？
3.  不同版本（或API层级）在实现上有哪些变化？
4.  是否有特定的本地模型或运行框架（如llama.cpp、vLLM、transformers）你正在使用？

请明确你更关注的点，也可以全部都要，我会一并研究。

## Prompt:
使用LangChain和Graph RAG时，如何提示（prompt）本地LLM严格输出JSON格式？

它们在代码层面（如langchain.schema、output parser等）如何解析与验证输出格式？

我在使用qwen3 14b

## Response:
好的，我将研究在使用 LangChain 和 Graph RAG 时，如何确保本地模型（如 Qwen3 14B）严格输出符合指定的 JSON 格式，包括：

*   提示词设计（Prompting）策略
*   LangChain 中的 output parser、schema 验证机制，以及 Graph RAG 的格式控制方法
*   不同版本的实现差异，尤其关注 Qwen3 14B 本地部署时的兼容性和限制

我会尽快将结果整理好。你这边可以继续提问或补充更多上下文。

## Prompt:
在 LangChain + Graph RAG 本地 RAG 系统中确保 LLM 输出 JSON 格式
===================================================

提示词设计策略
-------

要提高大语言模型（尤其是本地模型 Qwen3-14B）的输出 JSON 稳定性，首先需要精心设计提示词：

*   **明确要求仅输出 JSON：** 在系统/用户提示中明确指示模型**必须**用 JSON 格式给出答案，且不需任何额外说明或文本[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=%22crucial.%22%2C%20%22IMPORTANT%20NOTES%3A%5Cn,join%28filter%28None%2C%20base_string_parts)。例如：_“请直接以 JSON 格式给出回答，不要输出任何解释。”_
*   **指定 JSON 模板或字段：** 在提示中列出所需的 JSON 键和值格式。例如 GraphRAG 提示中写道：_“输出必须是包含若干 JSON 对象的列表，每个对象应含有键 `head`、`head_type`、`relation`、`tail`、`tail_type`。”_[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=,list%20in%20the%20user%20prompt)。对于问答任务，也可注明答案应置于 `"answer"` 字段中。Qwen 模型的官方建议是在提示里加入示例 JSON 结构来规范回答格式，比如要求模型输出：`{"answer": "C"}` 这样的格式[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=3,standardize%20model%20outputs%20when%20benchmarking)。
*   **提供格式示例：** 可以在提示中包含一个**示例 JSON**输出（Few-shot范例），让模型模仿该格式作答。这有助于模型理解期望的结构，提高遵循率[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=output%2C%20which%20will%20increase%20the,json%20in%20your%20chosen%20format)。
*   **强调不要偏离格式：** 重申除所要求的 JSON 外不应有多余内容（如自然语言解释、Markdown 代码块标记等）。GraphRAG 在提示中特别加注“IMPORTANT NOTES: - Don't add any explanation and text.” 来严格限定输出[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=%22crucial.%22%2C%20%22IMPORTANT%20NOTES%3A%5Cn,join%28filter%28None%2C%20base_string_parts)。
*   **必要时逐步引导：** 对于复杂请求，可以先让模型思考步骤（chain-of-thought），但最终回答时只保留 JSON。也可以将“reasoning”作为 JSON 内的一个字段。如果允许模型输出思考过程，务必确保它被包含在 JSON 结构中，否则应禁止模型在答案中显式输出推理过程。

通过以上策略的组合，能够在提示层面最大程度保证模型按照指定 JSON 模板作答。不过需要注意，**由于LLM的生成不确定性，无法百分之百保证严格的 JSON 格式**[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=Generally%20speaking%3A%20Due%20to%20the,head%20these%20are%20your%20options)——我们可以做到的是尽可能提高成功率，并辅以程序层面的校验和纠错。

LangChain 的结构化输出实现细节
--------------------

LangChain 提供了丰富的工具来**指导和验证** LLM 输出 JSON：

*   **Schema 定义与格式说明：** 可以使用 `langchain.output_parsers.StructuredOutputParser` 搭配 `langchain.output_parsers.ResponseSchema` 来定义输出结构。每个 `ResponseSchema` 定义一个字段名和描述。然后通过 `StructuredOutputParser.from_response_schemas(...)` 生成解析器，并调用 `parser.get_format_instructions()` 获取提示LLM的格式说明字符串[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=const%20response%20%3D%20await%20chain.invoke%28,this%20line)。这个说明通常会列出所需JSON的格式要求（字段名及说明），例如：“请以JSON格式输出，包含字段: ...”。将其插入提示模板中，让模型据此作答。格式说明会告知模型输出**严格的 JSON 对象**，没有其他多余文字[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=format_instructions%3A%20parser.getFormatInstructions%28%29%2C%20%2F%2F%20%3C,line)。
*   **Pydantic 模型解析：** 利用 Pydantic 数据模型直接约束输出结构。先定义一个 Pydantic `BaseModel` 子类来表示期望的输出schema，例如：
    ```
    class Movie(BaseModel):
        title: str = Field(..., description="电影标题")
        year: int = Field(..., description="上映年份")
        director: str = Field(..., description="导演")
    ```
    然后将此模型交给 LangChain 的输出解析器：
    ```
    from langchain.output_parsers import PydanticOutputParser
    parser = PydanticOutputParser(pydantic_object=Movie)
    format_instructions = parser.get_format_instructions()
    ```
    如上，`PydanticOutputParser` 会生成 JSON 格式的说明，并在解析时使用 Pydantic 验证模型字段类型[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=Copy)[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=model_with_structure%20%3D%20model,rating%3D8.8)。你也可以使用 `model.with_structured_output(Movie)` 将 LLM 与结构化输出绑定，这样调用模型时会自动应用该格式约束[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=model_with_structure%20%3D%20model,rating%3D8.8)。Pydantic 模型能够自动校验字段类型和必需字段，若模型输出缺少字段或类型不符，会抛出错误，帮助我们发现格式问题[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=Key%20considerations%20for%20structured%20output%3A)[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=,JSON%20Schema%20require%20manual%20validation)。
*   **PromptTemplate 与 OutputParser 整合：** 在构建 LangChain Prompt 时，可以通过 `partial_variables` 插入格式说明。例如：
    ```
    prompt = PromptTemplate(
        template="请回答问题，格式如下:\n{format_instructions}\n问题: {input}",
        input_variables=["input"],
        partial_variables={"format_instructions": format_instructions}
    )
    ```
    LangChain 在底层会将 `format_instructions` 插入最终提示，从而在每次询问中都包含对JSON格式的要求[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=template%3Dhuman_prompt_string%2C%20input_variables%3D%5B,examples%2C%20%7D%2C)。这样模型生成时始终有规范指导。生成结果返回后，我们调用 `parser.parse(output)` 来将LLM字符串解析为结构化数据对象。
*   **输出解析与错误处理：** `OutputParser` 负责将模型输出的文本转换为结构化对象。一旦解析成功，我们即可得到一个字典或 Pydantic 对象用于后续逻辑。如果解析失败（比如模型未按格式输出），我们需要**补救策略**：
    *   _正则提取/JSON修复：_ 可以实现在解析失败时，用正则从输出中提取出 `{...}` 内容，然后尝试 `json.loads` 解析，或借助类似 `json-repair` 的库自动修复一些格式小错误（如缺失引号/逗号等）[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=Make%20your%20application%20code%20more,and%20the%20last)。GraphRAG 的示例项目就安装了 `json-repair` 以便处理模型返回的非法 JSON[medium.com](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9#:~:text=pip%20install%20,community)。这种**后处理**可以将模型严格输出的成功率从 ~95% 提高到 ~99%[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=Prompt%20engeneering%20,to%2095)[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=Post,99)。
    *   _验证循环：_ 最终仍应对解析结果进行验证，确保符合预期 Schema。如果解析或校验未通过，可以自动触发模型重新回答。比如检测到输出非JSON或缺字段，就反馈模型要求严格按格式重答。这种**验证-重试**机制可确保接近100%的格式正确率[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=Validation%20Loop%20,to%20100)。实际应用中，可以将上述过程封装，实现失败就用强化提示重复提问直到获得合规JSON。
*   **LangChain 新版特性：** 2024年后，LangChain 对结构化输出做了进一步增强，引入了 `JsonOutputParser`、`TypedDict`支持、以及 `with_structured_output` 等简化接口[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=Key%20considerations%20for%20structured%20output%3A)。在一些模型集成中还支持原生的“JSON Mode”或OpenAI的函数调用模式。如果所用模型/接口支持这些模式，LangChain会直接利用它们严格地生成JSON；否则则退回到在提示中描述JSON Schema的方法[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=,be%20described%20in%20the%20prompt)。对于本地模型（如Qwen），通常采用提示中给schema的方式（相当于 `json_mode`）来引导，其背后依赖我们提供的格式说明和 OutputParser 进行解析。

Graph RAG 中的输出格式控制
------------------

Graph RAG（基于知识图谱的检索增强生成）流程中，有一个关键步骤是让模型从文档中**提取实体和关系**，构造成**图数据库三元组**形式。这一步强烈依赖模型输出符合特定的JSON结构，以便程序将结果解析为知识图谱。为此，Graph RAG 对本地模型输出格式也做了严格控制：

*   **定制提示模板：** Graph RAG 使用特定的 system prompt 和 human prompt 引导模型提取知识三元组。例如系统提示会说明模型的角色和任务：“你是一个用于构建知识图谱的算法，需要从给定文本中提取实体和关系，以 JSON 格式输出结果。” 并明确要求输出 JSON 列表，包含若干对象，每个对象有 `head`, `head_type`, `relation`, `tail`, `tail_type` 等键[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=,list%20in%20the%20user%20prompt)。这样的提示确保模型明白必须产出符合 schema 的结构化数据。
*   **Few-shot 示例和约束：** 提示往往还会提供**允许的实体类型、关系类型列表**，以及**提取示例**。例如 Graph RAG 可以在提示中列出预定义的实体类型和关系种类，附加一两个已知文本的示例解析对[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=,if%20rel_types%20else)[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=,join%28filter%28None%2C%20human_string_parts%29%29%20human_prompt%20%3D%20PromptTemplate)。模型据此学习如何用 JSON 对指定类型的实体/关系建模，有助于减少格式和内容偏差。同时在提示中明确“不允许输出未定义类型”，防止模型随意创造字段。
*   **LangChain Parser 集成：** Graph RAG 实现中会用 LangChain 的 `JsonOutputParser`/`PydanticOutputParser` 来验证模型输出。例如，上述提示模板会和一个 `UnstructuredRelation` 的 Pydantic 模型绑定，生成对应的 `JsonOutputParser`[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=system_message%20%3D%20SystemMessage,pydantic_object%3DUnstructuredRelation)。在 human prompt 部分，LangChain 把 `parser.get_format_instructions()` 插入提示，以提醒模型答案应该只包含所需 JSON 格式[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=template%3Dhuman_prompt_string%2C%20input_variables%3D%5B,examples%2C%20%7D%2C)。这样，模型的输出会被该解析器自动检查：如果模型没有完全遵守（如少了字段或JSON格式错误），解析器会抛出异常，便于我们后续处理。
*   **解析结果构建图谱：** 当模型成功返回符合schema的JSON（例如一组`{head, head_type, relation, tail, tail_type}`对象），LangChain 会将其解析为 `GraphDocument` 或类似的数据结构，其中包含提取的节点和关系列表。这些数据随后用于构建网络x图或 Neo4j 图。比如LangChain的 `LLMGraphTransformer` 会返回 `graph_documents`，其中 `.nodes` 和 `.relationships` 列表就是提取的图谱元素。我们只需迭代添加到图数据库即可[medium.com](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9#:~:text=for%20node%20in%20graph_documents_filtered)[medium.com](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9#:~:text=,type%2C)。
*   **错误处理和修复：** 即使有严格提示，一些本地模型仍可能输出不完美的 JSON（例如多了一些多余括号或解释）。Graph RAG 常用**自动纠错**手段，如在解析前尝试用 `json_repair` 修复格式，或用正则清洗非JSON部分[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=)。社区实践中，有开发者选择提取出JSON片段自行重组。例如若检测到模型输出了两段JSON，就可以取其中符合schema的部分重新组成最终JSON。如果某些字段格式不对，也可以通过字符串替换或正则调整。总之，在 Graph RAG 的实现里，会结合**格式校验+必要的纠错**，尽量保证最终喂给图谱构建模块的是合法完备的JSON数据。

值得一提的是，Graph RAG 模块在不同版本的 LangChain 中接口有所演进。例如早期版本使用 `GraphIndexCreator` 和 `GraphQAChain` 来创建和查询图谱[langchain-cn.readthedocs.io](https://langchain-cn.readthedocs.io/en/latest/modules/chains/index_examples/graph_qa.html#:~:text=from%20langchain,document_loaders%20import%20TextLoader)[langchain-cn.readthedocs.io](https://langchain-cn.readthedocs.io/en/latest/modules/chains/index_examples/graph_qa.html#:~:text=We%20can%20now%20use%20the,ask%20question%20of%20the%20graph)；后续的 `langchain_experimental.graph_transformers.LLMGraphTransformer` 提供了更灵活的选项（可指定允许的节点/关系类型等）[medium.com](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9#:~:text=llm_transformer_filtered%20%3D%20LLMGraphTransformer%28%20llm%3Dllm%2C%20allowed_nodes%3D%5B,convert_to_graph_documents%28%20documents)[medium.com](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9#:~:text=llm_transformer_filtered%20%3D%20LLMGraphTransformer%28%20llm%3Dllm%2C%20allowed_nodes%3D%5B,%29%20graph_documents_filtered%20%3D%20llm_transformer_filtered.convert_to_graph_documents)。但无论哪种实现，核心思想都是一致的：**通过精心设计提示和解析器，确保模型提取出的知识三元组严格符合预期的 JSON 模式**，从而可以被下游图数据库可靠地 ingest。新版本对这部分的 API 进行了优化，比如封装了 prompt+parser 的链，开发者只需提供文档和模型即可获得结构化图谱，无需手工处理JSON字符串。

不同版本的实现与 API 差异
---------------

LangChain 和 Graph RAG 在结构化输出这部分随着版本迭代有一些变化：

*   **LangChain 0.x vs 0.3+：** 较早版本中，开发者需要手动使用 `StructuredOutputParser` 或 `PydanticOutputParser` 来构建提示格式说明；而新版本提供了更高级的封装，如模型对象的 `.with_structured_output()` 方法[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=model_with_structure%20%3D%20model,rating%3D8.8)。例如在 LangChain 0.3+，可以直接调用 `llm.with_structured_output(MySchema)` 获得一个封装了输出解析的模型实例，然后用 `model.invoke(input)` 即可得到已解析好的结果对象。这背后利用了提供给模型的 JSON Schema 或函数调用功能。如果模型提供商有原生的 JSON 输出模式（如 OpenAI 的 _function calling_ 或 “JSON Mode”），LangChain 会通过参数启用它；否则就退而在提示里包含 schema 描述，让模型走文字提示路线[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=Key%20considerations%20for%20structured%20output%3A)。对于本地模型 Qwen3-14B，由于没有OpenAI那样的原生函数调用接口，实际上仍是采用提示+解析的方案（即相当于 `json_mode`）[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=,be%20described%20in%20the%20prompt)。
*   **Graph RAG 模块演进：** Microsoft 在2024年开源了 GraphRAG 思想的实现示例，引入了知识图谱用于RAG。LangChain 很快跟进提供了 `GraphIndexCreator` 和 `GraphQAChain`。在0.x版本，这些类的用法偏简单，内部也是调用 LLM 完成三元组提取[langchain-cn.readthedocs.io](https://langchain-cn.readthedocs.io/en/latest/modules/chains/index_examples/graph_qa.html#:~:text=from%20langchain,document_loaders%20import%20TextLoader)[langchain-cn.readthedocs.io](https://langchain-cn.readthedocs.io/en/latest/modules/chains/index_examples/graph_qa.html#:~:text=graph%20%3D%20index_creator)。到稍晚的LangChain 0.2.x和0.3，Graph RAG 功能被移入 `langchain_experimental` 或 `langchain_community` 模块中，增加了 `LLMGraphTransformer` 等，用于更复杂的场景（可过滤节点/关系类型、提取属性等）[medium.com](https://medium.com/data-science-in-your-pocket/graphrag-using-langchain-31b1ef8328b9#:~:text=llm_transformer_filtered%20%3D%20LLMGraphTransformer%28%20llm%3Dllm%2C%20allowed_nodes%3D%5B,convert_to_graph_documents%28%20documents)[github.com](https://github.com/langchain-ai/langchain/issues/26624#:~:text=node_fields%3A%20Dict,%28%20str%2C%20optional_enum_field%28%20node_labels)。同时引入了新的解析器如 `JsonOutputParser` 来替代旧有的 `PydanticOutputParser`，提升解析鲁棒性和易用性[reference.langchain.com](https://reference.langchain.com/python/langchain_core/output_parsers/#:~:text=JsonOutputParser%20%C2%B6.%20Bases%3A%20BaseCumulativeTransformOutputParser,no%20validation%20is)。从开发者视角，不同版本主要区别在于调用接口名有所变化，以及一些功能拆分到了 `langchain-core`, `langchain-community` 等子包。但总体而言，新版本对结构化输出支持更完善，文档中也强调了如何处理解析错误和验证，比如建议使用 `include_raw=True` 查看原始输出、或使用 `OutputFixingParser` 结合小模型来纠正格式[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=,JSON%20Schema%20require%20manual%20validation)。
*   **API变化示例：** 在旧版 LangChain，可能需要这样获取解析结果：
    ```
    parser = StructuredOutputParser.from_response_schemas([...])
    format_instr = parser.get_format_instructions()
    prompt = PromptTemplate(template="{question}\n{format_instr}", ...)
    output = llm(prompt.format(...))
    data = parser.parse(output)
    ```
    而在新版中，可以简化为：
    ```
    structured_llm = llm.with_structured_output(MySchema)
    result = structured_llm.invoke(user_input)
    print(result)  # 直接就是 Pydantic 对象或字典
    ```
    前者需要开发者手动插入格式说明并捕获解析异常，后者封装了这些步骤。同时，LangChain 新版允许指定 `method="json_schema"` 或 `"function_calling"` 等参数来控制用哪种机制实现结构化输出[docs.langchain.com](https://docs.langchain.com/oss/python/langchain/models#:~:text=Key%20considerations%20for%20structured%20output%3A)。
*   **版本兼容性提示：** 如果您在不同版本之间迁移，留意某些类名和模块路径可能改变。例如 `langchain.schema.BaseOutputParser` 在新版中可能位于 `langchain.output_parsers` 或 `langchain_core` 下；GraphRAG 的 `NetworkxEntityGraph` 在新版本中可能整合在统一的 `graphs` 子模块下等等。这些改动一般在发布说明中会注明。遇到接口错误时，可以查阅对应版本的文档或源码注释来更新用法。

总的来说，最新的 LangChain 和 Graph RAG 在确保输出JSON方面提供了更**自动化和健壮**的工具。但核心思路（提示工程 + 输出解析 + 验证重试）在各版本是一脉相承的。

Qwen3-14B 模型的支持与兼容性
-------------------

Qwen3-14B 作为本地大模型，在输出格式方面有一些特殊考量：

*   **聊天模型模式：** Qwen 属于对话模型（类似ChatGPT），在使用LangChain封装时应确保以聊天格式与其交互，并提供明确的系统消息指导格式。如果用的是 `ChatOllama` 或 HuggingFace Pipeline 加载 Qwen，应设置好`system_prompt`让模型知道只需输出 JSON，不要回复客套话。
*   **可能的格式偏差：** 根据社区经验，Qwen3-14B 在开启“推理解释”模式时可能导致输出出现**嵌套JSON**的不良行为。例如一位开发者报告，使用 `ChatOllama(model="qwen3:14b", reasoning=True)` 搭配 `with_structured_output` 时，模型输出会在本应单一的 JSON 前多加一个 `{`，变成类似 `{{"assistant": {...}}, {"reasoning": "..."} }` 这样的格式，直接导致 JSON 解析失败[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=Without%20reasoning%3A%20%7B%20,)。推测这是 Qwen 模型模板在生成理由内容时导致的冲突。解决方法：**禁用额外推理输出**（`reasoning=False`），或将 reasoning 也纳入 JSON 模板的一个字段，让模型把推理过程作为 JSON 中的字符串值返回，从而避免额外的括号[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=UP%20BY%20LANGGRAPH%3E)。
*   **中英输出问题：** Qwen-14B 是多语种模型。如果你的提示和内容是中文，模型很可能生成中文内容。但**JSON键尽量使用英文**并在提示中固定，以防模型将键翻译或改变格式。例如要求输出 `{"答案": "..."}` 不如统一要求输出 `{"answer": "..."}` 更稳妥——键名用英文能避免模型纠结语言而误输出其他变体。同时确保提示中示例JSON的引号、冒号等标点符号标准（英文状态），模型通常会模仿这些符号习惯。
*   **无原生JSON模式：** 与OpenAI新版模型不同，Qwen 并没有官方提供“一键JSON模式”接口。因此我们完全依赖提示词约束和后处理。幸运的是，Qwen在遵循格式方面表现尚可，只要提示清晰，大多数情况下能按要求输出[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=Also%3B%20you%20will%20always%20build,code%20as%20an%20end%20result)。但出错时就需要程序上做解析和修正（如上文所述的正则提取或重试机制）。不要指望模型**每次**都完美输出JSON，务必实现结果验证。
*   **模型行为差异：** Qwen 拥有较大的上下文长度和优秀的生成能力，但也可能出现一些特有行为。例如Qwen的“思考模式”（类似Chain-of-Thought）如果开启，可能更频繁地尝试解释过程。根据官方建议，在不需要推理过程时可以适当提高采样温度、避免贪心生成，以减少重复和意外输出[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=1)[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=,slight%20decrease%20in%20model%20performance)。同时，Qwen团队也建议在Benchmark时通过提示来**规范输出格式**（例如前述要求用 JSON 给出选择题答案的例子）[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=3,standardize%20model%20outputs%20when%20benchmarking)。这说明即便模型本身很强大，也需要通过**提示编排**来引导其格式。
*   **兼容 LangChain 工具：** 目前LangChain对Qwen的支持主要通过HF接口或Ollama等后端。如果使用 `langchain.chat_models.ChatOpenAI` 这类OpenAI接口是无法调用Qwen的，需要改用本地LLM接口（如 `HuggingFacePipeline` 或社区提供的 `ChatOllama` 类[langchain-ai.github.io](https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_adaptive_rag_local/#:~:text=,ChatOllama)）。这些接口大多兼容 `.with_structured_output` 和 OutputParser。如果发现某些方法不可用（例如早期版本LangChain可能不支持对接Qwen的structured输出），可以手动用 PromptTemplate+OutputParser 实现，原理相同。

**总结：** 在 LangChain + Graph RAG 本地系统中使用 Qwen3-14B 时，需特别关注提示设计和解析验证。利用LangChain的结构化输出工具，结合精心的JSON格式提示，再根据需要添加错误检测与重试逻辑，基本可以确保 Qwen 等本地模型输出符合指定的 JSON 格式[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=)[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=In%20the%20end%20you%20will,it%20has%20your%20expected%20format)。如有特殊模型行为（比如双大括号bug），通过调整提示或配置也可绕过。总体而言，尽管本地模型可能在格式遵循上不如API大模型稳定，但通过**提示工程 + LangChain解析器 + 后处理**的多层保证，我们依然能够构建一个健壮的本地 RAG 系统，可靠地得到结构化的 JSON 输出。

\*\*示例代码：\*\*下面用一个简化的例子展示如何将上述要点综合运用：

```
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

# 1. 定义期望JSON结构的Pydantic模型
class Answer(BaseModel):
    answer: str = Field(..., description="用户问题的简洁回答")

parser = PydanticOutputParser(pydantic_object=Answer)

# 2. 获取格式说明提示
format_instructions = parser.get_format_instructions()
# 假设 format_instructions 会生成类似:
# '请严格按照JSON格式输出，包含以下键:
# answer: 用户问题的回答 ...'

# 3. 构建提示模板，插入格式说明
prompt = PromptTemplate(
    template="你是知识库问答助手。\n请根据提供的上下文回答问题。\n{format_instructions}\n问题: {input}",
    input_variables=["input"],
    partial_variables={"format_instructions": format_instructions}
)

# 4. 将LangChain模型与提示模板、解析器结合
from langchain.llms import OpenAI  # 这里以OpenAI接口示例，本地模型请换相应类
llm = OpenAI(model_name="gpt-3.5-turbo", temperature=0)  # 本地模型用相应的Chat模型类
chain = prompt | llm | parser  # 串联 Prompt→LLM→Parser

# 5. 提供输入问题，运行链条获得结构化输出
query = "Graph RAG有什么作用？"
result = chain.invoke({"input": query})
print(result)
# 输出示例: Answer(answer="Graph RAG是一种使用知识图谱改进问答的技术。")
```

上面的代码演示了如何设置提示模板加入 JSON 格式说明，并使用 PydanticOutputParser 保证解析。同时要记得，**本地运行Qwen时需要使用相应的本地模型类替代 OpenAI**，如通过 HuggingFace 或 Ollama 接入模型。在实际应用中，还应包装 try/except 来捕获 `parser.parse` 可能抛出的格式错误，并做相应处理（如让模型重答或者程序修复JSON）。通过这些手段，就能最大程度确保无论模型如何发挥，您的系统最终拿到的都是符合规范的 JSON 数据。[reddit.com](https://www.reddit.com/r/LocalLLaMA/comments/1oeshaj/need_help_ive_been_breaking_my_head_over/#:~:text=)[stackoverflow.com](https://stackoverflow.com/questions/77407632/how-can-i-get-llm-to-only-respond-in-json-strings#:~:text=Validation%20Loop%20,to%20100)



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)