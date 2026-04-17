# 并行化调用大模型API

**User:**   
**Created:**   
**Updated:**   
**Exported:** 3/19/2026 11:53:57  
**Link:** [https://chatgpt.com/share/69625fd2-3424-8002-86ad-5a3e14822757](https://chatgpt.com/share/69625fd2-3424-8002-86ad-5a3e14822757)  

## Prompt:
使用api进行大模型调用时, 可不可以并行化就是同时的发送多个询问请求。然后呢同时等待他们回复。

## Response:
可以，而且**在工程实践中这是非常常见、也是强烈推荐的做法**。  
在使用 API 调用大模型（LLM, Large Language Model）时，**并行（Parallel / Concurrent）发送多个请求并同时等待返回**是完全可行的，但需要**区分并发模型、实现方式与约束条件**。

下面我从**概念 → 可行性 → 常见实现方式 → 注意事项 → 典型应用场景**，系统性地给你讲清楚。

* * *

一、结论先行（TL;DR）
-------------

*   ✅ **可以并行化调用大模型 API**
*   ✅ 可以 **同时发送多个请求、同时等待返回**
*   ⚠️ 需要注意：
    *   API **速率限制（Rate Limit）**
    *   **并发数（Concurrency）** 与 **吞吐量（Throughput）**
    *   **超时（Timeout）** 与 **失败重试（Retry）**
    *   **顺序一致性** 与 **结果对齐**

* * *

二、为什么可以并行？（从系统角度理解）
-------------------

大模型 API（如 OpenAI / Azure / Claude / Qwen API）在工程上都是：

*   **HTTP(S) 网络请求**
*   **无状态（Stateless）**
*   **请求之间相互独立**

因此它天然支持：

*   并发（Concurrency）
*   异步（Async）
*   批量调度（Batching）

你可以把每一次 LLM 调用理解为：

> “向一个远程计算服务提交一次作业（Job），等它算完再返回结果”

既然是**独立作业**，那就可以同时提交多个。

* * *

三、常见并行方式（非常重要）
--------------

### 1️⃣ Python 异步并行（推荐 ⭐⭐⭐⭐⭐）

适合你这种**研究 / 工程混合场景**，尤其是 GraphRAG、多 Agent。

#### 核心思想

*   使用 `asyncio`
*   同时发出多个请求
*   用 `await` 一起等结果

#### 示例（伪代码，概念清晰）

```
import asyncio

async def call_llm(prompt):
    response = await llm_api_call(prompt)
    return response

async def main():
    prompts = [
        "总结病历 A",
        "总结病历 B",
        "总结病历 C"
    ]

    tasks = [call_llm(p) for p in prompts]
    results = await asyncio.gather(*tasks)

    for r in results:
        print(r)

asyncio.run(main())
```

✅ 特点：

*   高吞吐
*   资源利用率高
*   非阻塞（Non-blocking）

📌 **这是目前主流 LLM 工程的标准做法**

* * *

### 2️⃣ 多线程 / 线程池（ThreadPoolExecutor）

适合：

*   API SDK **不支持 async**
*   快速工程落地

```
from concurrent.futures import ThreadPoolExecutor

def call_llm(prompt):
    return llm_api_call(prompt)

prompts = ["A", "B", "C"]

with ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(call_llm, prompts))
```

⚠️ 注意：

*   Python 有 GIL，但 **IO 密集型（网络请求）没问题**
*   不如 async 精细可控

* * *

### 3️⃣ 多进程（不推荐，除非特殊情况）

*   创建和销毁成本高
*   不适合频繁 API 请求
*   一般不用于 LLM API 调用

* * *

四、你必须注意的几个“工程级问题”
-----------------

### ⚠️ 1. API 速率限制（Rate Limit）

几乎所有 LLM API 都有限制，例如：

*   每分钟请求数（RPM, Requests Per Minute）
*   每分钟 Token 数（TPM, Tokens Per Minute）

如果你并行太多：

*   ❌ 会返回 `429 Too Many Requests`
*   ❌ 或被限流、暂时封禁

#### 解决方案

*   控制并发数（Semaphore）
*   请求队列（Queue）
*   指数退避重试（Exponential Backoff）

* * *

### ⚠️ 2. 并发 ≠ 无限制并行

正确姿势是：

```
有限并发（bounded concurrency）
```

例如：

```
sem = asyncio.Semaphore(5)

async def call_llm_with_limit(prompt):
    async with sem:
        return await call_llm(prompt)
```

* * *

### ⚠️ 3. 返回顺序与输入对齐问题

并行后：

*   返回顺序 ≠ 发送顺序（尤其是 `asyncio.as_completed`）

解决方案：

*   保留索引
*   使用结构化返回（JSON with id）

```
{
  "task_id": 12,
  "response": "..."
}
```

* * *

### ⚠️ 4. 超时、失败、部分成功

现实情况一定会出现：

*   某些请求超时
*   某些请求失败
*   某些成功、某些失败

工程上要接受：

> **Partial Failure（部分失败）是常态**

解决方案：

*   retry（重试）
*   fallback 模型
*   标记失败样本

* * *

五、并行调用在你研究中的典型用途（非常契合你当前方向）
---------------------------

结合你现在在做的 **GraphRAG / 医学文本 / 幻觉审查**：

### ✅ 1. 多句子并行判别幻觉

```
一句话 = 一个 LLM 判别请求
→ 并行跑 50 句
```

### ✅ 2. 多 Agent 并行

*   hallucination detection agent
*   error classification agent
*   evidence extraction agent

👉 每个 Agent 对同一输入 **并行推理**

* * *

### ✅ 3. 多模型并行（ensemble / preference）

```
Qwen-7B
Qwen-14B
GPT-4
Claude
```

并行生成 → 聚类 → 偏好排序  
（这正是你现在 UPA 思路里的关键）

* * *

六、一句话工程总结（你可以直接用在设计文档里）
-----------------------

> 在大模型 API 调用中，由于请求之间相互独立且服务端为无状态架构，客户端可以通过异步 I/O 或受控并发机制并行发送多个请求并同时等待返回，从而显著提升吞吐量与整体系统效率。但需要结合速率限制、并发上限与失败重试机制进行工程化控制。

* * *

如果你愿意，**下一步我可以直接帮你**：

*   写一份 **“并行 LLM 调用模块设计规范”**
*   或直接给你 **GraphRAG / 医学 Agent 并行调用的标准代码模板**
*   或结合 **Qwen API + asyncio** 给你一个可直接复用的实现

你可以直接告诉我你现在用的是：

*   OpenAI / Azure / Qwen / 本地 Ollama
*   单模型并行？还是多模型并行？

## Prompt:
asyncio是真并发, 还是让Ai回答多个问题？

我害怕如果是后者的话，因为上下文和他同时要处理的逻辑变得更多，所以说他的回复质量会下降。

## Response:
你的担心很专业，而且关键点在于：**asyncio 的“并发”发生在客户端（client-side），不是让同一个模型在一次推理里同时处理多个问题。**因此一般**不会因为“同时问多个问题”而降低单次回答质量**——只要你不是把多个问题塞进同一个 prompt 里。

下面把这个问题讲透：

* * *

1) asyncio 到底是在做什么：真并发还是“一个请求里多问题”？
-----------------------------------

### ✅ asyncio 做的是：**并发发送多个独立请求（request）**

*   你发出 N 个 HTTP 请求（每个请求一个 prompt、一个上下文）
*   这些请求在网络 I/O 上并行等待
*   服务端会把它们当作 **N 次独立推理** 来处理

也就是说：

> asyncio 并不是让“同一个模型的一次推理”同时回答多个问题；  
> 它只是让你“同时提交多个作业”。

### ❌ 会导致质量下降的情况是：**把多个问题合并进同一个请求**

例如你写一个 prompt：“请同时回答 A、B、C、D……”，这会：

*   增加上下文长度（context length）
*   增加指令复杂度（instruction complexity）
*   造成注意力稀释（attention dilution）
*   更容易漏答、答非所问、格式不稳

这才是你担心的“上下文更多 → 质量下降”的来源。

* * *

2) 并行请求会不会“共享一个上下文”，互相干扰？
-------------------------

一般情况下：**不会**。

因为 API 调用是\*\*无状态（stateless）\*\*的：

*   每个请求带自己的 messages / prompt
*   服务端不会把多个请求拼在一起推理
*   也不会让一个请求“知道”另一个请求的内容

所以**请求之间不会相互污染上下文**。

* * *

3) 那并行请求有没有可能间接影响质量？
--------------------

有，但原因不是“模型同时思考多个问题”，而是**系统层面的资源与限流**：

### 情况 A：触发限流 / 排队

*   并发太高 → 429/503
*   或服务端内部排队 → 延迟上升、超时增多
*   质量不一定降，但**失败率**、**超时截断**可能上升

### 情况 B：你自己设置了共享的“生成预算”

*   比如你为了省钱，把 `max_tokens` 设得很低
*   并发多时你更容易同时跑很多请求，**更容易出现输出被截断**（看起来像质量下降）

### 情况 C：你在做“多轮对话”却并发了同一个会话

如果你把同一段对话历史（同一个 conversation）并发发多条续写请求：

*   每条请求各自独立推理没问题
*   但你会拿到多个“分叉的后续”，需要你在客户端选择哪条作为下一轮上下文
*   这不是质量下降，是**会话分支管理**问题

* * *

4) 一个直观类比（帮助你快速建立正确直觉）
----------------------

*   **asyncio 并发**：像你同时给 10 个学生各发一张试卷（10 次独立答题）
*   **一个请求里多问题**：像你给 1 个学生一张试卷上有 10 道超复杂大题，要求一次写完（更容易写崩）

你担心的是第二种，而 asyncio 通常是第一种。

* * *

5) 实操建议：如何“并行但不降质”
------------------

### ✅ 推荐策略 1：一请求一任务（Task isolation）

*   每个 prompt 只解决一个清晰子任务
*   例如：一句话幻觉判别 / 一段证据抽取 / 一条出院小结要点提取

### ✅ 推荐策略 2：有限并发（Bounded concurrency）

*   用 semaphore 控制并发数，比如 5～20（视你的 RPM/TPM 而定）
*   这样避免限流和超时

### ✅ 推荐策略 3：结构化输出 + task\_id

*   每个请求返回带 id 的 JSON
*   客户端轻松对齐结果，不会乱序造成误判

* * *

6) 你这个场景下最关键的一句话
----------------

> **asyncio 并发不会让模型“同时处理更多上下文”，因为每次推理仍然是独立请求；质量下降通常来自“把多个任务塞进一个 prompt”或“限流/超时/截断”。**

* * *

如果你告诉我你现在用的具体接口（例如 Qwen 的哪个 SDK / OpenAI / 自建网关），以及你希望并行的任务类型（句子切分、幻觉判别、证据抽取、总结等），我可以直接给你一个**带限流、重试、超时、结构化返回**的并发调用模板，适合你现在 GraphRAG + 医疗文本流水线用。

## Prompt:
那对于多个不一样的prompt进行多个请求应该怎么样做呢？

## Response:
对于“多个不一样的 prompt → 多个请求”的最佳做法，本质上是搭一层**并发调度器（dispatcher）**：把每个 prompt 封装成一个独立任务（task），用**有限并发**并行发出请求，并且做好**结果对齐、重试、超时、限流**。

下面我给你一套**通用、可直接套用**的工程方案（以 Python 为例，适用于 OpenAI/兼容 OpenAI 的网关/Qwen 的 OpenAI 兼容接口等）。

* * *

1) 设计目标：你需要的能力
--------------

*   多个 prompt（每个可能不同 system/user、不同参数）
*   并发执行（asyncio.gather）
*   控制并发上限（Semaphore）
*   自动重试（尤其 429/503/超时）
*   结果稳定对齐（task\_id）
*   可选：按不同“模型/温度/输出格式”独立配置

* * *

2) 推荐数据结构：每个请求一个 RequestSpec
----------------------------

每条请求建议长这样（你可以把它当成“作业描述”）：

*   `task_id`: 唯一 id
*   `messages`: 该请求的 system/user 等上下文
*   `model / temperature / max_tokens`: 该请求独立参数

这样可以保证：**不同 prompt 不会被你无意合并**，也方便对齐结果。

* * *

3) 可复用代码模板（asyncio + 有限并发 + 重试 + 对齐）
------------------------------------

> 说明：下面示例用 `httpx` 直接发 HTTP，通用性最好。你只需要改成你的 endpoint 和 key 即可。  
> 如果你用的是某个 SDK，也可以保留同样的并发/重试外壳，把内部 `request_chat_completion()` 换成 SDK 调用。

```
import asyncio
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

@dataclass
class RequestSpec:
    task_id: str
    model: str
    messages: List[Dict[str, str]]  # [{"role": "system", "content": ...}, ...]
    temperature: float = 0.2
    max_tokens: int = 512
    extra: Optional[Dict[str, Any]] = None  # 允许你放 response_format 等扩展字段

@dataclass
class ResponseItem:
    task_id: str
    ok: bool
    content: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class LLMDispatcher:
    """
    并发调度器：负责
    - 有限并发
    - 重试（指数退避+抖动）
    - 超时
    - 结果对齐
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        concurrency: int = 8,
        timeout_s: float = 60.0,
        max_retries: int = 5,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.sem = asyncio.Semaphore(concurrency)
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    async def request_chat_completion(self, client: httpx.AsyncClient, spec: RequestSpec) -> Dict[str, Any]:
        """
        发一次请求：这里使用 OpenAI Chat Completions 兼容接口路径示例。
        如果你的服务是 /v1/responses 或别的路径，改这里即可。
        """
        url = f"{self.base_url}/v1/chat/completions"

        payload: Dict[str, Any] = {
            "model": spec.model,
            "messages": spec.messages,
            "temperature": spec.temperature,
            "max_tokens": spec.max_tokens,
        }
        if spec.extra:
            payload.update(spec.extra)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = await client.post(url, json=payload, headers=headers, timeout=self.timeout_s)
        resp.raise_for_status()
        return resp.json()

    def _extract_text(self, data: Dict[str, Any]) -> str:
        """
        兼容常见返回结构：chat.completions -> choices[0].message.content
        """
        return data["choices"][0]["message"]["content"]

    async def _run_one(self, client: httpx.AsyncClient, spec: RequestSpec) -> ResponseItem:
        async with self.sem:
            for attempt in range(self.max_retries + 1):
                try:
                    data = await self.request_chat_completion(client, spec)
                    text = self._extract_text(data)
                    return ResponseItem(task_id=spec.task_id, ok=True, content=text, raw=data)
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    # 常见可重试：429(限流)、500/502/503/504(服务端/网关问题)
                    retryable = status in {429, 500, 502, 503, 504}
                    if not retryable or attempt == self.max_retries:
                        return ResponseItem(task_id=spec.task_id, ok=False, error=f"HTTP {status}: {e.response.text}")
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    # 网络/超时通常可重试
                    if attempt == self.max_retries:
                        return ResponseItem(task_id=spec.task_id, ok=False, error=f"Network/Timeout: {repr(e)}")
                except Exception as e:
                    # 其它异常一般不重试，或你也可以按需策略化
                    return ResponseItem(task_id=spec.task_id, ok=False, error=f"Unexpected: {repr(e)}")

                # 指数退避 + 抖动（jitter），避免“同一时间一起重试”造成雪崩
                backoff = (2 ** attempt) * 0.5
                jitter = random.random() * 0.25
                await asyncio.sleep(backoff + jitter)

            return ResponseItem(task_id=spec.task_id, ok=False, error="Exhausted retries")

    async def run(self, specs: List[RequestSpec]) -> List[ResponseItem]:
        async with httpx.AsyncClient() as client:
            tasks = [self._run_one(client, s) for s in specs]
            # gather 会保持结果顺序与 specs 一致（对齐方便）
            return await asyncio.gather(*tasks)

# -------------------- 使用示例 --------------------
async def main():
    dispatcher = LLMDispatcher(
        base_url="https://YOUR-ENDPOINT",
        api_key="YOUR-KEY",
        concurrency=8,
        timeout_s=60,
        max_retries=5,
    )

    specs = [
        RequestSpec(
            task_id="p1",
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "你是医学文本抽取助手。"},
                {"role": "user", "content": "从这段出院小结中提取诊断与用药要点：..."},
            ],
            temperature=0.0,
            max_tokens=600,
        ),
        RequestSpec(
            task_id="p2",
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "你是句子切分器。"},
                {"role": "user", "content": "把下面文本切分为句子并编号输出：..."},
            ],
            temperature=0.0,
            max_tokens=400,
        ),
        RequestSpec(
            task_id="p3",
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "你是事实一致性审查员。"},
                {"role": "user", "content": "给定原文与生成摘要，标出不一致句子并说明：..."},
            ],
            temperature=0.2,
            max_tokens=800,
        ),
    ]

    results = await dispatcher.run(specs)

    for r in results:
        if r.ok:
            print(f"[{r.task_id}] OK\n{r.content}\n")
        else:
            print(f"[{r.task_id}] FAIL: {r.error}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

### 这段模板解决了你最关心的点

*   **每个 prompt 独立请求** → 不会“上下文变大导致质量下降”
*   **有限并发** → 不会一上来就把自己打到 429
*   **自动重试** → 429/503/超时更稳
*   **结果对齐** → `task_id` 清晰对应

* * *

4) 并行请求的“正确粒度”怎么选？
------------------

给你三个工程经验规则：

*   **规则 1：每个请求只做一个明确子任务（single responsibility）**
    *   例如：“句子切分”就只做切分，不要顺便总结+审查+改写
*   **规则 2：尽量让不同请求之间互不依赖**
    *   如果有依赖，就分成两层：
        *   第 1 层并行：抽取 / 切分
        *   第 2 层并行：审查 / 纠错（用第 1 层结果）
*   **规则 3：并发上限先小后大**
    *   例如从 5、8、12 逐步提高
    *   观察 429/超时比例再调

* * *

5) 你接下来只需要回答我一个信息，我就能把模板“落到你现用栈上”
---------------------------------

你现在调用大模型的方式是哪一种？

*   A) OpenAI 官方 API
*   B) Qwen（阿里）官方 API
*   C) OpenAI 兼容网关（比如你自己搭的、或 vLLM/OneAPI/火山等兼容）
*   D) 本地（Ollama/vLLM）但暴露了 HTTP 接口

你只要告诉我你用的是哪种（以及 endpoint 形态大概像什么），我就能把上面 `base_url / path / payload` 精确改成你能直接跑的版本。

## Prompt:
你搜索一下qwen的asyncio如何使用, 创建详细的包含代码的使用指南。
并且举一个实际的例子，从逻辑的层面不含代码讲解它是怎么样运作的。

## Response:
已思考 12s

下面给你一份\*\*“Qwen（通义千问）在 Python 中用 asyncio 并行调用”的详细使用指南\*\*，包含两条主流路线：

*   路线 A：**DashScope Python SDK 的异步接口**（官方文档明确提供 `AioGeneration` 示例）[AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/text-generation)
*   路线 B：**OpenAI 兼容协议 + openai-python 异步客户端**（把 `base_url` 指到 DashScope 的 compatible endpoint）[AlibabaCloud+1](https://www.alibabacloud.com/help/en/model-studio/qwen-api-reference)

并且我会给一个**不含代码**、从逻辑层面解释“它到底怎么运作”的真实例子。

* * *

0) 关键前提：并行不会让“一个请求的上下文更大”
-------------------------

你这里的“多个不同 prompt → 多个请求”属于**多个独立推理**，不会把多个 prompt 混到同一个上下文里；因此**不会因为并行而必然降质**。你担心的“上下文变复杂导致降质”，主要发生在**把多个任务塞进同一个 prompt**时。

* * *

路线 A：DashScope SDK（官方异步）— 推荐优先用这个
---------------------------------

### 1) 安装与版本要求

官方说明：**DashScope SDK 异步文本生成只在 Python 支持，且版本要求 ≥ 1.19.0**。[AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/text-generation)

```
pip install -U dashscope
```

（如果你想固定版本，也可以：`pip install "dashscope>=1.19.0"`）

### 2) 配置 API Key 与区域 endpoint

*   API Key 通常放在环境变量 `DASHSCOPE_API_KEY`
*   endpoint（区域）常见有：
    *   国际站（新加坡）：`https://dashscope-intl.aliyuncs.com/api/v1`（DashScope 协议）
    *   中国站（北京）：`https://dashscope.aliyuncs.com/api/v1`（DashScope 协议）  
        官方示例里直接设置 `dashscope.base_http_api_url`。[AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/text-generation)

### 3) 最小可运行：并发请求（asyncio.gather）

官方文档给了一个非常标准的写法：`AioGeneration.call(...)` + `asyncio.gather(*tasks)`。[AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/text-generation)

```
import asyncio
import os
import platform
import dashscope
from dashscope.aigc.generation import AioGeneration

# 国际站（新加坡）；如用北京区改为 https://dashscope.aliyuncs.com/api/v1
dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

async def ask(question: str) -> str:
    resp = await AioGeneration.call(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        result_format="message",
    )
    return resp.output.choices[0].message.content

async def main():
    questions = ["Who are you?", "What can you do?", "How is the weather?"]
    tasks = [ask(q) for q in questions]
    results = await asyncio.gather(*tasks)
    for q, r in zip(questions, results):
        print("Q:", q)
        print("A:", r)
        print("-" * 40)

if __name__ == "__main__":
    # Windows 下官方示例建议设置事件循环策略
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
```

> 注意：并发情况下**返回顺序可能与发送顺序不同**（官方文档也提醒了这一点），但用 `gather` 并 `zip` 对齐通常最省心。[AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/text-generation)

### 4) 工程化增强：限制并发（避免 429 限流）

当你一次并发 50/100 条请求时，很容易撞到 **RPM/TPM 限制**，最佳实践是“有限并发”。

```
import asyncio

SEM = asyncio.Semaphore(8)  # 同时最多 8 个请求，按你的额度调整

async def ask_limited(question: str) -> str:
    async with SEM:
        return await ask(question)
```

然后把 `ask(q)` 换成 `ask_limited(q)` 即可。

* * *

路线 B：OpenAI 兼容协议（兼容 openai-python 的 Async 客户端）
----------------------------------------------

如果你的工程里已经大量使用 `openai-python` / LangChain（OpenAI-style client），那走兼容协议会更丝滑。

### 1) 关键 endpoint

官方 Qwen API reference 给出 OpenAI compatible base\_url：[AlibabaCloud](https://www.alibabacloud.com/help/en/model-studio/qwen-api-reference)

*   新加坡：`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
*   北京：`https://dashscope.aliyuncs.com/compatible-mode/v1`

### 2) openai-python 本身支持异步客户端

openai-python 官方仓库说明：提供同步与异步客户端（基于 httpx）。[GitHub](https://github.com/openai/openai-python?utm_source=chatgpt.com)

### 3) 最小可运行：AsyncOpenAI 并发

```
import asyncio
import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",  # 或北京区
)

async def ask(question: str) -> str:
    resp = await client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content

async def main():
    qs = ["写一个Python冒泡排序", "解释Transformer注意力机制", "给我3个实验设计点子"]
    results = await asyncio.gather(*[ask(q) for q in qs])
    for q, r in zip(qs, results):
        print(q, "\n", r, "\n")

asyncio.run(main())
```

* * *

一个真实例子（不含代码）：它在逻辑层面怎么运作？
------------------------

以你做的医学方向很常见的任务举例：  
**“对一份出院小结拆成 30 句，每句做事实一致性（factual consistency）审查”**

逻辑流程是这样的（完全不依赖具体 SDK）：

1.  **任务拆分（Task Split）**  
    你把 30 句话分别封装成 30 个独立请求：
    *   每个请求的 prompt 只包含：该句子 + 对应证据片段 + 统一审查规则
    *   这样每次推理上下文都很小，质量稳定
2.  **创建协程任务（Coroutine Tasks）**  
    你在本地事件循环（Event Loop）里创建 30 个“待执行的网络请求任务”。  
    这些任务还没“占用 CPU 算力”，它们只是被调度。
3.  **并发发出请求（Concurrent Dispatch）**  
    asyncio 会尽快把这些 HTTP 请求都发出去（或在你设定的并发上限内分批发出）。  
    关键点：
    *   你的程序不会“一个一个阻塞等待”
    *   而是把等待网络返回的时间重叠起来（这就是吞吐提升的来源）
4.  **等待返回（Await Responses）**  
    当某个请求先返回，事件循环就立刻把控制权交给对应任务去处理响应；其他还没返回的任务继续“挂起等待”。
5.  **结果汇总与对齐（Collect & Align）**  
    你把每条返回结果按 `sentence_id`（或 task\_id）对齐回原句子位置。  
    这样即使返回顺序乱了，也不会影响你的后处理。
6.  **进入下一阶段（Pipeline Next Step）**  
    比如把被判定为不一致的句子送去“错误类型分类（error classification）”或“纠错生成（correction）”阶段，同样可以再并行。

> 这整个过程里，“并发”发生在**你本地的请求调度与网络等待**层面；  
> 每个请求到服务端仍然是一次独立推理，不会因为你同时发了 30 个请求就把 30 句混成一个上下文。

* * *

最常见的坑（你做工程一定会遇到）
----------------

1.  **429 限流**：并发数太大 → 用 Semaphore 限制并发 + 重试退避
2.  **超时**：网络或服务端排队 → 给每次请求设 timeout
3.  **顺序错乱**：并发返回顺序不稳定 → 用 `task_id/sentence_id` 对齐（不要依赖返回顺序）
4.  **过度合并 prompt**：想省请求数把 30 句塞一条 prompt → 质量更容易不稳（你担心的情况）

* * *

如果你告诉我你现在用的是哪一种调用方式（DashScope SDK 还是 OpenAI 兼容协议），以及你希望的并发规模（比如 8、32、128），我可以直接给你一份“可直接复制进项目”的版本：带 **限流、重试（指数退避）、超时、失败回收、日志与统计（latency/成功率）**，更适合你现在的 GraphRAG/医学流水线。



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)