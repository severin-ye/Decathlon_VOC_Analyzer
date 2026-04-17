# MS-Swift LoRA微调Qwen3

**User:**   
**Created:**   
**Updated:**   
**Exported:** 3/19/2026 11:53:04  
**Link:** [https://chatgpt.com/share/69626087-92c8-8002-bfa1-49425d7adb5c](https://chatgpt.com/share/69626087-92c8-8002-bfa1-49425d7adb5c)  

## Prompt:
ms-swift如何lora微调qwen3的模型

## Response:
请问您希望使用 MS-Swift 框架对 Qwen 3 模型进行 LoRA 微调，是否能补充以下信息以便我更准确地帮助您：

1.  您具体使用的 Qwen 3 模型版本（例如 Qwen3-7B、Qwen3-14B 等）？
2.  目标任务类型是什么（如文本分类、生成、对话等）？
3.  希望使用的硬件资源（如单卡 A100、消费级 GPU、TPU 等）？
4.  是否已有现成的训练数据格式和样例？
5.  对输出格式有无具体要求（如生成 checkpoint、推理部署兼容性等）？

提供这些信息后，我将为您整理一份完整的 LoRA 微调流程。

## Prompt:
Qwen3-14B
基于证据的幻觉识别 格式化输出
h200单卡

## Response:
了解，我将为您查找如何使用 MS-Swift 框架在单卡 H200 上对 Qwen3-14B 模型进行基于证据的幻觉识别任务的 LoRA 微调，并支持格式化输出。  
我会尽快整理出具体流程，包括环境配置、模型加载、数据格式、LoRA 设置与训练指令等细节。您可以继续和我交流其他问题。

## Prompt:
Qwen3-14B 幻觉识别任务的 LoRA 微调指南（MS‑Swift 框架）
========================================

环境配置
----

在单卡 H200 上进行 Qwen3-14B 模型 LoRA 微调，需要准备合适的软硬件环境。建议使用 **Ubuntu 22.04** 操作系统，**Python 3.10** 运行环境，以及支持 H200 GPU 的 NVIDIA 驱动和 CUDA 库（例如 CUDA **11.8** 或更新版本）[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E5%9C%A8%E9%83%A8%E7%BD%B2%20DeepSeek,8%EF%BC%8C%E5%AE%83%E8%83%BD%E5%85%85%E5%88%86%E5%8F%91%E6%8C%A5NVIDIA%20GPU%E7%9A%84%E5%B9%B6%E8%A1%8C%E8%AE%A1%E7%AE%97%E8%83%BD%E5%8A%9B%EF%BC%8C%E5%8A%A0%E9%80%9F%E6%A8%A1%E5%9E%8B%E7%9A%84%E8%AE%AD%E7%BB%83%E4%B8%8E%E6%8E%A8%E7%90%86%E8%BF%87%E7%A8%8B%E3%80%82)。安装 **PyTorch 2.1** 或以上版本，并确保 CUDA 对应匹配（H200 对应最新 CUDA 版本）。另外，需要安装 MS‑Swift 框架及相关依赖：

*   \*\*MS‑Swift 安装：\*\*可以通过源码安装 MS‑Swift。在终端执行：
    ```
    pip install git+https://github.com/modelscope/ms-swift.git 
    ```
    或手动克隆仓库后 `pip install -e .` 进行安装[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=)。安装完成后，确保 `swift --help` 可以运行。
*   \*\*其他依赖：\*\*根据 Qwen3 模型要求，安装 Hugging Face Transformers 和 PEFT 库的新版本。例如：
    ```
    pip install transformers>=4.51.3 accelerate>=0.24.0 datasets 
    pip install peft>=0.6.0 bitsandbytes>=0.41.0
    ```
    以上依赖包括 Hugging Face 模型库（需 **≥4.51.0** 以支持 Qwen3 模型）[volcengine.csdn.net](https://volcengine.csdn.net/694d04a85b9f5f31781ad070.html#:~:text=pip%20install%20pytorch%20torchvision%20torchaudio,c%20nvidia)、PEFT LoRA 工具、Accelerate 分布式支持，以及 `bitsandbytes`（如果计划使用8-bit量化来节省显存）。
*   \*\*CUDA 和驱动：\*\*确保已安装适用于 H200 的 CUDA 驱动（如 CUDA 12.x）及 CuDNN 等。H200 拥有大显存（80GB以上），足以容纳14B模型的微调。如需进一步优化显存，可考虑安装 **Flash-Attention** 和 **Liger Kernel** 等（MS‑Swift 提供可选支持[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=pip%20install%20transformers)），以提升长序列训练效率。

配置好环境后，验证 PyTorch 能识别 H200 GPU，并正确安装 MS‑Swift。例如，在 Python 中运行 `import swift` 无错误。

模型加载方式及兼容性
----------

**Qwen3-14B** 是阿里云 Qwen 系列的新一代 14B 参数大模型[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=,and%20131%2C072%20tokens%20with%20YaRN)。它已在 Hugging Face 提供权重（模型ID为 `"Qwen/Qwen3-14B"`），使用 Apache-2.0 开源许可证[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=arxiv%3A%202505)。在 MS‑Swift 框架中，可以通过 **Hugging Face** 或 **ModelScope** 社区加载模型：

*   **直接加载 Hugging Face 模型：** 使用 `swift sft` 等命令时，通过参数 `--model Qwen/Qwen3-14B --use_hf true` 来指定模型。这会利用 Hugging Face Hub 下载 Qwen3-14B 权重并加载[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=,model%20%3Cmodel_id%2Fmodel_path)。确保 transformers 版本满足要求，否则可能出现 `'qwen3' KeyError` 等错误[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=The%20code%20of%20Qwen3%20has,transformers)（transformers 4.51 已内置对 Qwen3 的支持）。加载时 MS‑Swift 会自动处理 Qwen3 模型的自定义代码（若需要，可设置 `trust_remote_code=True`）。
*   **使用 ModelScope 加载：** MS‑Swift 默认优先从 ModelScope 社区下载模型和数据集[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=,model%20%3Cmodel_id%2Fmodel_path)。如果 Qwen3-14B 在 ModelScope 平台上提供，可以直接使用 `--model modelscope/<模型名称>`。否则，通过 `--use_hf true` 切换到 Hugging Face 来源。模型首次加载后会缓存在本地路径供后续使用。

\*\*模型兼容性：\*\*Qwen3-14B 完全兼容 Hugging Face 的 `AutoModelForCausalLM` 接口。加载后模型支持最长 **32K** 上下文长度，具备“思考”（推理链）模式和普通对话模式[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=following%20key%20features%3A)[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=,and%20131%2C072%20tokens%20with%20YaRN)。建议使用 **bfloat16** 或 **float16** 精度加载模型以节省显存（在 MS‑Swift 中通过参数如 `--torch_dtype bfloat16` 设置）。H200 GPU 原生支持 bfloat16，使用该精度可充分利用其算力。若使用 8-bit 量化微调（QLoRA），需要 `bitsandbytes` 支持并在加载模型时设置 `load_in_8bit=True`[volcengine.csdn.net](https://volcengine.csdn.net/694d04a85b9f5f31781ad070.html#:~:text=%23%20%E5%85%B3%E9%94%AE%EF%BC%9A8,model)，不过在单卡 H200 场景通常无需8-bit也能微调14B模型。

加载完成后，可通过简单生成测试确保模型正常。例如，使用 Hugging Face 接口:

```
from transformers import AutoModelForCausalLM, AutoTokenizer
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-14B")
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-14B", torch_dtype="auto").cuda()
out = model.generate(**tok("你好", return_tensors='pt').to('cuda'), max_new_tokens=20)
print(tok.decode(out[0]))
```

如果输出连贯中文，则表示模型加载成功。

LoRA 配置参数
---------

**LoRA**（Low-Rank Adaptation）是一种高效微调方法，通过为模型的权重增加低秩矩阵来注入新知识，同时冻结原模型大部分参数。微调 Qwen3-14B 时，可使用 LoRA 显著减少需要训练的参数量。在 MS‑Swift 中，通过 `--train_type lora` 启用 LoRA 微调，并可配置以下关键超参数：

*   **秩 (rank)：** LoRA 矩阵的秩大小，通常用参数 `--lora_rank` 指定。例如设置 `r=8`[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93lora_rank%EF%BC%9A%E8%AE%BE%E7%BD%AE%20LoRA%20%E7%9A%84%E7%A7%A9%EF%BC%88rank%EF%BC%89%EF%BC%8C%E7%94%A8%E4%BA%8E%E6%8E%A7%E5%88%B6%20LoRA%20%E5%B1%82%E7%9A%84%E5%8F%82%E6%95%B0%E6%95%B0%E9%87%8F%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA,16%20%E6%AD%A5%20%E2%80%93eval_steps%EF%BC%9A%E6%AF%8F%E9%9A%94%E5%A4%9A%E5%B0%91%E6%AD%A5%E8%BF%9B%E8%A1%8C%E4%B8%80%E6%AC%A1%E8%AF%84%E4%BC%B0%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%E6%AF%8F%20100%20%E6%AD%A5%E8%AF%84%E4%BC%B0%E4%B8%80%E6%AC%A1)表示每个被插入 LoRA 的权重增加秩为8的低秩矩阵。秩越大，LoRA容量越强，但训练参数也越多。常用值有 4、8、16 等，经验上 8 已能取得较好效果[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93lora_rank%EF%BC%9A%E8%AE%BE%E7%BD%AE%20LoRA%20%E7%9A%84%E7%A7%A9%EF%BC%88rank%EF%BC%89%EF%BC%8C%E7%94%A8%E4%BA%8E%E6%8E%A7%E5%88%B6%20LoRA%20%E5%B1%82%E7%9A%84%E5%8F%82%E6%95%B0%E6%95%B0%E9%87%8F%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA,16%20%E6%AD%A5%20%E2%80%93eval_steps%EF%BC%9A%E6%AF%8F%E9%9A%94%E5%A4%9A%E5%B0%91%E6%AD%A5%E8%BF%9B%E8%A1%8C%E4%B8%80%E6%AC%A1%E8%AF%84%E4%BC%B0%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%E6%AF%8F%20100%20%E6%AD%A5%E8%AF%84%E4%BC%B0%E4%B8%80%E6%AC%A1)。
*   **缩放因子 (alpha)：** LoRA 的缩放系数，使用参数 `--lora_alpha` 设置。例如 `alpha=32`[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93lora_rank%EF%BC%9A%E8%AE%BE%E7%BD%AE%20LoRA%20%E7%9A%84%E7%A7%A9%EF%BC%88rank%EF%BC%89%EF%BC%8C%E7%94%A8%E4%BA%8E%E6%8E%A7%E5%88%B6%20LoRA%20%E5%B1%82%E7%9A%84%E5%8F%82%E6%95%B0%E6%95%B0%E9%87%8F%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA,16%20%E6%AD%A5%20%E2%80%93eval_steps%EF%BC%9A%E6%AF%8F%E9%9A%94%E5%A4%9A%E5%B0%91%E6%AD%A5%E8%BF%9B%E8%A1%8C%E4%B8%80%E6%AC%A1%E8%AF%84%E4%BC%B0%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%E6%AF%8F%20100%20%E6%AD%A5%E8%AF%84%E4%BC%B0%E4%B8%80%E6%AC%A1)。LoRA 插入的低秩更新会乘以该因子再加回模型，以控制更新幅度。alpha 通常与 rank 成比例调整（如经验公式 $\\text{effective rank} = \\frac{\\alpha}{r}$）。在rank=8时设置 alpha=32 是常见配置[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93lora_rank%EF%BC%9A%E8%AE%BE%E7%BD%AE%20LoRA%20%E7%9A%84%E7%A7%A9%EF%BC%88rank%EF%BC%89%EF%BC%8C%E7%94%A8%E4%BA%8E%E6%8E%A7%E5%88%B6%20LoRA%20%E5%B1%82%E7%9A%84%E5%8F%82%E6%95%B0%E6%95%B0%E9%87%8F%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA,16%20%E6%AD%A5%20%E2%80%93eval_steps%EF%BC%9A%E6%AF%8F%E9%9A%94%E5%A4%9A%E5%B0%91%E6%AD%A5%E8%BF%9B%E8%A1%8C%E4%B8%80%E6%AC%A1%E8%AF%84%E4%BC%B0%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%E6%AF%8F%20100%20%E6%AD%A5%E8%AF%84%E4%BC%B0%E4%B8%80%E6%AC%A1)。
*   **目标模块 (target modules)：** 指定应用 LoRA 的模型层。可以选择模型中的部分线性层插入 LoRA。例如，常见做法是只对注意力层的投影矩阵（如 `q_proj` 和 `v_proj`）应用 LoRA[volcengine.csdn.net](https://volcengine.csdn.net/694d04a85b9f5f31781ad070.html#:~:text=lora_config%20%3D%20LoraConfig,%E9%9C%80%E8%A6%81%E9%80%82%E9%85%8D%E7%9A%84%E6%A8%A1%E5%9D%97)，以有效捕获注意力模式而不干扰过多参数。MS‑Swift 提供快捷选项，如 `--target_modules all-linear` 表示将 LoRA 应用于模型中的**所有线性层**[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=,logging_steps%205)。这种设置能最大程度地覆盖可能产生幻觉的层，但也增加了一定显存开销和参数量。若希望精细控制，可通过列出模块名称列表（例如 `--target_modules "q_proj,k_proj,v_proj,o_proj"` 等）来只针对注意力矩阵和输出投影插入 LoRA。对于 Qwen3-14B，**all-linear**通常可行，或仅限 **Q,K,V**投影以减少内存占用。
*   **LoRA Dropout：** LoRA 层的随机失活比率，一般默认为0（不丢弃）。MS‑Swift 默认 LoRA dropout 为0，如需正则化可设置 `--lora_dropout` 参数（如0.05）但通常影响不大。
*   **学习率：** LoRA 层通常使用较高的学习率。经验上 LoRA 微调可用 **1e-4** 级别学习率[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=,save_steps%20100)[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93model%EF%BC%9A%E6%8C%87%E5%AE%9A%E9%A2%84%E8%AE%AD%E7%BB%83%E6%A8%A1%E5%9E%8B%E7%9A%84%E5%90%8D%E7%A7%B0%E6%88%96%E8%B7%AF%E5%BE%84%20%E2%80%93train_type%20lora%20%EF%BC%9A%E6%8C%87%E5%AE%9A%E8%AE%AD%E7%BB%83%E7%B1%BB%E5%9E%8B%E4%B8%BA%20LoRA%EF%BC%88Low,%E5%B1%82%E7%9A%84%E7%BC%A9%E6%94%BE%E6%AF%94%E4%BE%8B%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%2032%20%E2%80%93gradient_accumulation_steps%EF%BC%9A%E8%AE%BE%E7%BD%AE%E6%A2%AF%E5%BA%A6%E7%B4%AF%E7%A7%AF%E6%AD%A5%E6%95%B0%EF%BC%8C%E7%94%A8%E4%BA%8E%E5%9C%A8%E5%B0%8F%E6%89%B9%E6%AC%A1%E6%83%85%E5%86%B5%E4%B8%8B%E6%A8%A1%E6%8B%9F%E5%A4%A7%E6%89%B9%E6%AC%A1%E8%AE%AD%E7%BB%83%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%2016%20%E6%AD%A5)，比全参数微调更高，以加速低秩适应。MS‑Swift 中通过 `--learning_rate` 指定，例如 `1e-4`[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=,save_steps%20100)。也可使用学习率调度策略（`--lr_scheduler_type` 等）按需要调整。
*   **优化器：** 默认使用 AdamW 优化 LoRA 参数即可。如显存充裕，可结合 8-bit Adam 等加速。

在 MS‑Swift CLI 中，上述参数可以这样指定，例如：`--lora_rank 8 --lora_alpha 32 --target_modules all-linear --learning_rate 1e-4`。DeepSeek 微调教程中的示例也采用了 **rank=8**、**alpha=32** 的配置[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=,logging_steps%205)[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93lora_rank%EF%BC%9A%E8%AE%BE%E7%BD%AE%20LoRA%20%E7%9A%84%E7%A7%A9%EF%BC%88rank%EF%BC%89%EF%BC%8C%E7%94%A8%E4%BA%8E%E6%8E%A7%E5%88%B6%20LoRA%20%E5%B1%82%E7%9A%84%E5%8F%82%E6%95%B0%E6%95%B0%E9%87%8F%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA,16%20%E6%AD%A5%20%E2%80%93eval_steps%EF%BC%9A%E6%AF%8F%E9%9A%94%E5%A4%9A%E5%B0%91%E6%AD%A5%E8%BF%9B%E8%A1%8C%E4%B8%80%E6%AC%A1%E8%AF%84%E4%BC%B0%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%E6%AF%8F%20100%20%E6%AD%A5%E8%AF%84%E4%BC%B0%E4%B8%80%E6%AC%A1)。这些值在幻觉识别任务上通常效果良好。如果目标任务更复杂或数据量较大，可以适当尝试提高 rank 或调整 target modules 范围来拟合更多知识。

_提示：_ LoRA 参数的选择需要在不过拟合和保留原有模型能力之间权衡。由于幻觉识别任务需要模型保持强大的事实判断能力，建议 **保持 LoRA 的规模适中**。太高的 rank 可能导致模型过度拟合微调数据而遗忘常识知识。MS‑Swift 支持通过 `--merge_lora` 将 LoRA 权重并入模型[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%23%20merge,max_model_len%208192)，微调后如果需要部署单一模型文件，可以考虑在验证后执行合并。

幻觉识别任务的数据格式
-----------

**基于证据的幻觉识别任务**通常要求模型读入一段证据文本和一个断言（或回答），判断该回答是否为幻觉（即不符合证据事实），并输出判断结果以及依据证据的解释。这可被视作一个**有上下文支撑的问答/判断**任务。为了微调 Qwen3-14B，使其具备根据证据检测幻觉的能力，需要准备相应格式的训练数据。

MS‑Swift 使用 **标准消息格式** 来组织对话数据，每条数据包含一个 `messages` 列表，其中交替记录用户和助手角色的消息[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/Customization/Custom-dataset.html#:~:text=The%20standard%20dataset%20format%20for,is%20used%20for%20grounding%20tasks)。具体到幻觉识别任务，我们可以按以下方式构造数据集中的每个样本（存储为 JSON 或 JSONL，每行一个对话）：

*   **User 提示 (`"role": "user"`):** 包含问题、模型回答和支撑证据。可以将它组织成一个文本，包括：**证据段落**+**用户的断言或问题**+（可选）**要求模型判断的指令**。为了清晰起见，可以在提示中加入标识符。例如：
    ```
    {"role": "user", "content": 
      "【证据】据世界银行数据，2021年中国GDP约为17.7万亿美元。\n
       【断言】中国2021年的GDP是5万亿美元。\n
       请根据以上证据判断该断言是否幻觉，并给出理由。"}
    ```
    在此例中，`content`字段包含了证据和待判断的断言，以及指示模型输出所需格式的请求。您也可以用其他方式组织，如明确提出问题“上述断言是否与证据相符？”等。关键是确保模型在提示中获得**足够的信息**：既包括需要验证的内容，也包括用于验证的**事实证据**。
*   **Assistant 响应 (`"role": "assistant"`):** 包含模型的回答，应该格式化为**清晰的判断和解释**。为了鼓励模型输出易于解析的结果，可以在训练数据中使用固定模板。例如，可以让回答以“是/否”开头表明是否幻觉，随后给出基于证据的简短解释说明理由。也可以模仿思维链的格式，先输出“思考:”部分，然后“结论:”部分。例如：
    ```
    {"role": "assistant", "content": 
      "思考：证据显示中国2021年GDP约为17.7万亿美元，5万亿美元明显不符。\n\n
       回答：不，该断言是幻觉。依据证据，中国2021年GDP约17.7万亿，美金5万亿的说法错误。"}
    ```
    在该回答中，“思考”部分让模型显式展示推理过程，“回答”部分给出最终判断。这类似于 Qwen3 模型的\*\*<think>思考模式**输出，只是用明文标识替代特殊标记[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=%7B,)。训练时包含这样的格式，有助于模型学会在回答时先基于证据分析，再给出结论，从而**输出格式规范\*\*且有依据。

完整的一条训练数据可以包含上述 user 和 assistant 两条消息，例如：

```
{
  "messages": [
    {
      "role": "user",
      "content": "【证据】据世界银行数据，2021年中国GDP约为17.7万亿美元。\n【断言】中国2021年的GDP是5万亿美元。\n请根据以上证据判断该断言是否幻觉，并给出理由。"
    },
    {
      "role": "assistant",
      "content": "思考：证据显示中国2021年GDP约17.7万亿美元，因此5万亿美元的断言缺乏事实依据。\n\n回答：不，该断言属于幻觉。根据证据，中国2021年GDP约17.7万亿美元，并非5万亿美元。"
    }
  ]
}
```

每个 JSON 对象代表一组 QA 交换。需要将所有这样的对象组成列表，保存为 `.json` 或每行一个 JSON 的 `.jsonl` 文件，供微调时加载。

**注意事项：**

*   **字段要求：**MS‑Swift 自动识别 `messages` 字段，因此确保使用此键。对于幻觉检测，不需要 `label` 等独立标签字段，因为我们打算让模型生成判断而非纯分类。如果改用**序列分类任务**思路，也可以将断言放在 user 内容，设置 `"label": 0/1` 表示真假[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/Customization/Custom-dataset.html#:~:text=Single)。但那样模型输出只是标签，不易融入解释，故推荐用生成式方式包含解释。
*   \*\*多轮对话：\*\*通常幻觉判断是一问一答，dataset 中每条消息对就够用。如果某些数据有人机多轮对话背景，也可包含在 `messages` 中多轮交互（MS‑Swift 支持多轮消息串联）。不过大多数幻觉检测语料是单轮判断。
*   \*\*特殊格式：\*\*如果希望模型输出 JSON 等特殊格式，可在 user 提示中显式要求格式并在示例中体现。例如要求模型回答形如：`{"hallucination": true, "evidence": "…"}。`那么在训练集中 assistant 内容就按照该 JSON 样式书写，模型即可学习模仿。总之，**训练数据的输出格式**决定了微调后模型的输出习惯。

准备好数据集（例如保存在文件 _dataset.json_），可利用 ModelScope 或 Hugging Face 加载器验证格式是否正确，也可以编写简单脚本读取几条样本，确保 `messages` 列表结构无误[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/Customization/Custom-dataset.html#:~:text=The%20standard%20dataset%20format%20for,is%20used%20for%20grounding%20tasks)。

微调训练脚本样例
--------

有了模型和数据，即可使用 MS‑Swift 提供的命令行工具 **swift** 开始微调。MS‑Swift 针对不同任务提供子命令，例如 `swift sft` 用于有监督微调（Supervised Fine-Tuning）。下面给出在 **单卡 H200** 上对 Qwen3-14B 进行 LoRA 微调的示例脚本，并解释各参数含义：

```
CUDA_VISIBLE_DEVICES=0 swift sft \
  --model Qwen/Qwen3-14B \              # 使用Qwen3-14B基础模型（HuggingFace路径）
  --use_hf true \                      # 指定从HuggingFace下载模型
  --train_type lora \                  # 使用LoRA高效微调
  --dataset /path/to/dataset.json \    # 本地数据集路径（JSON或JSONL格式）
  --torch_dtype bfloat16 \             # 模型计算采用bfloat16精度
  --num_train_epochs 3 \               # 训练轮数，例如3轮
  --per_device_train_batch_size 1 \    # 每块GPU的batch大小，单卡H200可尝试1-2视显存而定
  --gradient_accumulation_steps 8 \    # 梯度累积步数，累积8步相当于全局batch=8
  --learning_rate 1e-4 \               # LoRA微调学习率
  --lora_rank 8 \                      # LoRA秩r=8:contentReference[oaicite:30]{index=30}
  --lora_alpha 32 \                    # LoRA缩放alpha=32:contentReference[oaicite:31]{index=31}
  --target_modules all-linear \        # LoRA作用于所有线性层:contentReference[oaicite:32]{index=32}
  --max_length 2048 \                  # 单次输入最大长度（视任务需要和显存可调）
  --warmup_ratio 0.05 \                # 训练热身比例（5%训练步数做学习率热启动）
  --logging_steps 5 \                  # 每隔5步日志记录一次:contentReference[oaicite:33]{index=33}
  --save_steps 100 \                   # 每100步保存一次检查点:contentReference[oaicite:34]{index=34}
  --save_total_limit 2 \               # 最多保存2个最近的检查点:contentReference[oaicite:35]{index=35}
  --output_dir ./output/Qwen3-14B \    # 输出权重保存目录
  --dataloader_num_workers 4           # 数据加载线程
```

上述脚本中，`CUDA_VISIBLE_DEVICES=0` 指定使用单块GPU（ID为0的H200）。核心参数如模型路径、train\_type、dataset、LoRA超参数等都已在命令中指定[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,lora_alpha%2032)。\*\*需要注意：\*\*如果数据集或模型需要自定义加载（比如私有模型或非JSON格式数据），可参考 MS‑Swift 官方文档修改相应参数或预处理[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=,dataset%20%3Cdataset_path)。例如，非标准字段名的数据，可以用 `--columns` 参数映射，但我们的数据已经按标准 `messages` 格式无需额外指定。

运行上述命令，MS‑Swift 将开始训练：它会自动加载模型和数据，应用 LoRA 初始化低秩权重，然后逐步执行优化。在日志中可以看到每步的 loss 和每隔 `logging_steps` 的日志输出，以及周期性的评估（如果提供了验证集）和保存行为。根据经验，Qwen3-14B 每步迭代在单卡 H200 上耗时取决于 batch 大小和序列长度（H200 算力很强，batch=1, seq=2048 时每步可能数百毫秒到1秒级）。**3个epoch**跑完具体时间视数据规模而定（例如几千样本的数据集可能在一小时内完成）。

**优化与调整：** 如果在训练中发现显存占用接近上限，可以**减少 batch** 或 **增大梯度累积**来平衡。例如显存不足时，将 `per_device_train_batch_size` 改为1并增加 `gradient_accumulation_steps` 等效增大整体批次而不超显存[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=3)。MS‑Swift 也支持 DeepSpeed ZeRO 等技术，若单卡也想利用 CPU offload 可加参数 `--deepspeed zero3` 等，但在 H200 上通常无需。若追求更高速度，可以尝试开启 `--attn_impl flash_attn`（需要预先安装 Flash Attention 库）。这些优化选项在 MS‑Swift 文档中有详细说明[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=pip%20install%20transformers)。

训练完成后，输出目录（如 `./output/Qwen3-14B`）下会生成带时间戳或checkpoint编号的子目录，例如 _checkpoint-1000/_ 等，包含 LoRA 微调产生的权重。根据 `save_total_limit`，只保留最近的若干个检查点[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E2%80%93gradient_accumulation_steps%EF%BC%9A%E8%AE%BE%E7%BD%AE%E6%A2%AF%E5%BA%A6%E7%B4%AF%E7%A7%AF%E6%AD%A5%E6%95%B0%EF%BC%8C%E7%94%A8%E4%BA%8E%E5%9C%A8%E5%B0%8F%E6%89%B9%E6%AC%A1%E6%83%85%E5%86%B5%E4%B8%8B%E6%A8%A1%E6%8B%9F%E5%A4%A7%E6%89%B9%E6%AC%A1%E8%AE%AD%E7%BB%83%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%2016%20%E6%AD%A5%20%E2%80%93eval_steps%EF%BC%9A%E6%AF%8F%E9%9A%94%E5%A4%9A%E5%B0%91%E6%AD%A5%E8%BF%9B%E8%A1%8C%E4%B8%80%E6%AC%A1%E8%AF%84%E4%BC%B0%EF%BC%8C%E8%BF%99%E9%87%8C%E8%AE%BE%E7%BD%AE%E4%B8%BA%E6%AF%8F%20100,robot%E2%80%9D%20%E5%BE%AE%E8%B0%83%E8%AE%AD%E7%BB%83%E7%BB%93%E6%9E%9C%E5%A6%82%E4%B8%8B%EF%BC%9A%20Image%3A%20%E5%9C%A8%E8%BF%99%E9%87%8C%E6%8F%92%E5%85%A5%E5%9B%BE%E7%89%87%E6%8F%8F%E8%BF%B0)。最终一个完整 LoRA 权重（例如 _checkpoint-last_ 或最高编号的 checkpoint）即是我们需要的微调结果。

输出格式控制方法
--------

在幻觉识别任务中，**控制模型输出的格式**尤为重要。我们希望模型不仅给出正确的判断，还按照预期的模板呈现结果（例如先说明推理过程再下结论，或输出固定短语等）。为实现这一点，可以采取以下措施：

**1\. 利用提示模板（Prompt Template）：** 在微调数据中，显式地将所需格式体现在示例里，使模型学习这种响应风格。例如，正如前文数据格式部分所述，我们可以在 Assistant 的示例答案中包含“思考：…\\n\\n回答：…”这种结构[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=%7B,)。模型微调后会倾向于复制这一模式。在推理时，我们也可以在用户提示里提醒所需格式，如在用户消息中结尾添加类似“请按照‘是/否 + 理由’的格式作答。”的说明。这种 **指令提示** 配合已微调的权重，可以显著提高输出格式的一致性。MS‑Swift 支持在推理时添加系统消息或用户提示来影响格式，例如训练时也可加入 `"role": "system"` 的消息为每条对话设定固定风格。你可以利用 `--system "<指令>"` 参数在微调或推理阶段统一添加系统提示[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=,robot)。例如：

```
swift sft ... --system "请先思考再回答。回答格式：思考过程+最终结论。"
```

这样模型会在训练中始终接收到该规范要求，从而更严格地遵循格式。

**2\. 使用 Qwen 的思维链模式：** Qwen3 系列模型独有的 _Thinking_ 模式允许输出带有 `<think>...</think>` 标签的思考内容[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=,except%20ValueError%3A%20index%20%3D%200)。在推理时默认开启逻辑思考，模型会将内部推理过程放在 `<think>` 标签中，再输出最终答案[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%7B%22model%22%3A%22DeepSeek,create)。我们可以利用这一特性来格式化输出：让模型把对证据的分析当作 _思考_ 内容输出，再给出回答。例如，在微调时保留或模拟这种格式 —— 即 Assistant 内容中先 `<think>推理…</think>\n\n实际回答`。微调后推理，可以通过 MS‑Swift 的 `--response_prefix` 参数控制是否显示思考链[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=Non)：设置一个 `<think>\n\n</think>\n\n` 前缀等价于禁止输出推理过程，仅给最终回答[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=%2A%20%60,to%20setting%20enable_thinking%20to%20False)。相反，保留 `<think>` 则让模型显式输出推理。根据需求选择其中一种方案。如果希望最终应用中用户只看见结论，可以利用推理后解析去除 `<think>` 段。[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=,except%20ValueError%3A%20index%20%3D%200)中的示例展示了如何分割 Qwen 输出的思考内容。总之，**充分利用 Qwen3-14B 的思考模式**能够帮助检测幻觉时输出更可信赖的解释。

**3\. 指令微调（Instruction Tuning）：** LoRA 微调本身就是一种指令微调形式：在我们提供的数据中，用户明确要求模型进行幻觉判断并格式化回答。通过这些定制的指令训练，模型学习到了新的指令模式。如果需要更复杂的格式，例如输出成 JSON、Markdown 表格等，可以准备相应的示例对话（few-shot）或在训练数据中纳入格式要求。比如要求模型输出：

```
{ "hallucination": <true/false>, "analysis": "<理由>" }
```

则在训练集中让 assistant 恰好按照这样的 JSON 格式作答。经过足够样本学习，模型能够在推理时严格遵循 JSON 模板输出[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=%7B,)。若格式特别严格（如代码片段），也可以考虑在**系统消息**中开启相应模式（比如一些模型支持 `<|im_start|>system\n<formatting rules>\n<|im_end|>`的提示）。

**4\. 人类反馈与渐进优化：** 输出格式的细微调整有时需要靠经验反复试验。如果发现模型偶尔偏离格式，可以使用少量高权重的新数据（或增加 epoch）进行“格式强化”训练，或者在推理时结合**温度控制**和**解析检查**。将温度设低（甚至0）可减少随机性，使输出更一致[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,max_new_tokens%202048)。也可以生成多次输出选择最符合格式的一条。MS‑Swift 方便地支持设置 `--temperature`，在推理时我们可将其置为 **0** 以得到确定性的回答[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,max_new_tokens%202048)。

综上，在模型微调和使用过程中，通过在**训练数据**中示范、使用**系统/用户提示**指导，以及借助**Qwen3特性**，都能有效控制输出格式。例如，一份社区提供的 Qwen3 自我认知微调示例就展示了在数据中使用“Thought:… Answer:…”模板，从而训练出在回答问题时先输出内在思考再回答的模型[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/BestPractices/Qwen3-Best-Practice.html#:~:text=%7B,)。

推理与验证流程
-------

微调完成后，需要对模型进行推理测试和效果验证，以确认其幻觉识别能力达标。以下是典型的推理/验证流程：

1.  **加载微调权重：** 对于 LoRA 微调的模型，有两种方式使用微调结果：
    *   **直接加载 LoRA 适配器：** 使用 MS‑Swift CLI 的 `swift infer` 命令，指定 `--adapters` 参数为微调生成的 LoRA 检查点路径。这样会将 LoRA 权重应用到原基础模型上进行推理[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,max_new_tokens%202048)。例如：
        ```
        CUDA_VISIBLE_DEVICES=0 swift infer \
          --model Qwen/Qwen3-14B --use_hf true \
          --adapters ./output/Qwen3-14B/checkpoint-1000 \
          --stream true --temperature 0 --max_new_tokens 1024
        ```
        这里 `--model` 再次指定基础模型且 `--use_hf true`，`--adapters` 指向 LoRA 权重目录（其中包含 `adapter_model.bin` 等以及 `args.json`配置）。MS‑Swift 会自动读取配置将 LoRA 合并到模型推理[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=%2A%20Here%2C%20%60,load_args%20false)。`--stream true` 表示流式输出以便交互查看，`--temperature 0` 确保结果稳定[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,max_new_tokens%202048)。
    *   **合并生成新模型：** 若希望将 LoRA 权重合并进原模型得到完整权重，可以使用 `swift export --merge_lora true` 或在推理时加入 `--merge_lora true` 参数[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%23%20merge,max_model_len%208192)。例如：
        ```
        swift infer --model Qwen/Qwen3-14B --adapters ./output/Qwen3-14B/checkpoint-1000 \
          --merge_lora true --infer_backend vllm --max_model_len 8192 --max_new_tokens 1024
        ```
        这将在推理开始前将 LoRA 与原模型权重合并，并利用 vLLM 引擎加速推理[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%23%20merge,max_model_len%208192)。合并后的模型权重会输出到对应 checkpoint 目录（名称通常带有 _merged_ 标记）[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=)。后续可以直接使用合并后的模型文件进行部署或加载，无需再提供 LoRA 适配器。
2.  **构造推理输入：** 按照训练时的格式准备输入。例如：
    ```
    {"messages": [
        {"role": "user", "content": "【证据】...<证据文本>...\\n【断言】...<待判定句子>...\\n请判断上述断言是否幻觉，并解释原因。"}
    ]}
    ```
    使用 CLI 时，可以直接在命令行通过交互式方式输入（因为上面用了 `--stream true`，可以在提示符下键入user内容）。或者利用 HTTP 接口调用：MS‑Swift 支持通过 `swift deploy` 启动一个OpenAI兼容服务，然后使用 `/v1/chat/completions` API调用[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E6%88%91%E4%BB%AC%E5%8F%AF%E4%BB%A5%E4%BD%BF%E7%94%A8cli%E5%91%BD%E4%BB%A4%E8%84%9A%E6%9C%AC%E8%B0%83%E7%94%A8%E6%A8%A1%E5%9E%8B%E6%9C%8D%E5%8A%A1%EF%BC%8C%E5%9C%A8%E7%BB%88%E7%AB%AF%E4%B8%AD%E8%BE%93%E5%85%A5%E4%BB%A5%E4%B8%8B%E5%91%BD%E4%BB%A4%EF%BC%9A)。DeepSeek 框架示例中提供了如何用 `curl` 命令调用本地部署模型的参考[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=curl%20http%3A%2F%2Flocalhost%3A8000%2Fv1%2Fchat%2Fcompletions%20%5C%20,0)。开发者也可以编写 Python 脚本，使用 Transformers 接口加载模型和 LoRA 权重（PEFT库可用于将 LoRA 加载到 HF 模型）然后进行 `.generate()` 推理。
3.  **获取并解析输出：** 模型会返回类似训练格式的回答，包括判断和解释。如果使用 Qwen3 思考模式，可能包含 `<think>...</think>` 内容。可以通过简单的字符串处理将其去除，或根据之前约定的格式进一步解析（例如正则检查是否包含“是”或“否”关键词判断模型判定）。确保输出与预期格式一致，如果不一致，可能需要调整提示或模型版本。
4.  **验证效果：** 准备一些**验证集**样本，手工标注正确与否，与模型输出比较。如果训练时没有专门的验证集，可从训练集中留出一部分或利用公开基准（如 FACTCC、TruthfulQA 等）。计算模型在这些样本上的**准确率**、**召回率**等指标。如果输出带有解释，人工核对解释是否合理。针对**幻觉检测**任务，常用指标有**正确分类率**（模型判定幻觉/非幻觉是否正确）以及**根据证据解释的质量**。因为解释评估较主观，可主要关注判断对错。
    如果结果不理想，考虑以下措施：增加微调数据量或轮数、调整 LoRA 超参数（例如提高 rank）或者在提示中加入更多指导。一些研究表明融合**检索增强**（RAG）可以降低幻觉发生率[amazon.science](https://www.amazon.science/blog/new-tool-dataset-help-detect-hallucinations-in-large-language-models#:~:text=models%20www,setting%20raises%20three%20chief), 但本任务强调识别幻觉，因此模型性能主要取决于微调数据覆盖的案例和质量。
5.  **部署与推理优化：** 验证满意后，可将模型用于实际应用。MS‑Swift 支持将模型一键部署为服务（`swift deploy`）并提供 Web UI。也可以将合并后的模型权重上传 Hugging Face 或 ModelScope 供调用[qwen.readthedocs.io](https://qwen.readthedocs.io/en/latest/training/ms_swift.html#:~:text=Merge%20LoRA%20weights%3A)[qwen.readthedocs.io](https://qwen.readthedocs.io/en/latest/training/ms_swift.html#:~:text=swift%20export%20%5C%20,use_hf%20false)。在推理时，为提升性能，可使用 **vLLM** 等推理加速后端[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%23%20merge,max_model_len%208192)或者模型量化后的权重。H200 GPU 非常强大，但如果需要同时服务多个请求，适当调整 `--max_new_tokens` 以限制单次回答长度，或使用批量推理接口。MS‑Swift 在推理阶段同样支持多GPU并行和张量并行，若将来扩展到多卡部署，可参考官方指南配置。

最后，充分利用社区资源来完善微调流程。阿里团队发布了 Qwen3 技术报告和使用文档，其中包含许多**最佳实践**[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=,and%20131%2C072%20tokens%20with%20YaRN)。社区也有不少教程和案例，例如 _DeepSeek-R1 微调实战_ 博客详细演示了 MS‑Swift 微调 Qwen 蒸馏模型的全过程[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,lora_alpha%2032)[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E7%9B%B4%E6%8E%A5%E5%8A%A0%E8%BD%BD%E5%BE%AE%E8%B0%83%E5%90%8E%E7%9A%84%E6%9D%83%E9%87%8D%E6%96%87%E4%BB%B6%EF%BC%8C%E5%BF%AB%E9%80%9F%E9%AA%8C%E8%AF%81%E5%BE%AE%E8%B0%83%E6%95%88%E6%9E%9C%E6%98%AF%E5%90%A6%E7%94%9F%E6%95%88%E3%80%82)。这些资料提供了有益的经验参考。如果需要 Colab Notebook 演示，可留意 ModelScope 或 HuggingFace 社区是否有人分享了 Qwen3-14B LoRA 微调的笔记。本指南所附引用的资源中，包括了官方文档和社区教程链接，便于深入学习。

**参考资料：**

*   MS‑Swift 官方仓库及文档[swift.readthedocs.io](https://swift.readthedocs.io/en/latest/GetStarted/Quick-start.html#:~:text=swift%20sft%20%5C%20,per_device_train_batch_size%201)
*   Qwen3 模型 HuggingFace 页面与使用示例[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=from%20transformers%20import%20AutoModelForCausalLM%2C%20AutoTokenizer)[huggingface.co](https://huggingface.co/Qwen/Qwen3-14B#:~:text=%7B,to%28model.device)
*   DeepSeek 技术社区博文：_基于MS‑Swift框架的微调实践_[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=CUDA_VISIBLE_DEVICES%3D0%20,lora_alpha%2032)[deepseek.csdn.net](https://deepseek.csdn.net/67ec9c8ab40ce155396ce77b.html#:~:text=%E7%9B%B4%E6%8E%A5%E5%8A%A0%E8%BD%BD%E5%BE%AE%E8%B0%83%E5%90%8E%E7%9A%84%E6%9D%83%E9%87%8D%E6%96%87%E4%BB%B6%EF%BC%8C%E5%BF%AB%E9%80%9F%E9%AA%8C%E8%AF%81%E5%BE%AE%E8%B0%83%E6%95%88%E6%9E%9C%E6%98%AF%E5%90%A6%E7%94%9F%E6%95%88%E3%80%82)
*   火山引擎社区文章：_Qwen3模型LoRA微调全攻略_[volcengine.csdn.net](https://volcengine.csdn.net/694d04a85b9f5f31781ad070.html#:~:text=%E9%A6%96%E5%85%88%E6%98%AF%E4%BE%9D%E8%B5%96%E5%AE%89%E8%A3%85%EF%BC%9A)[volcengine.csdn.net](https://volcengine.csdn.net/694d04a85b9f5f31781ad070.html#:~:text=lora_config%20%3D%20LoraConfig,%E9%9C%80%E8%A6%81%E9%80%82%E9%85%8D%E7%9A%84%E6%A8%A1%E5%9D%97)（介绍小参模型的LoRA微调方法，也有环境依赖说明）



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)