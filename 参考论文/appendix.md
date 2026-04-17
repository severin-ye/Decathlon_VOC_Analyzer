# Appendix

本附录提供更详细的实验配置、提示模板、数据集构建说明与可复现性信息，以支持对本文结果的复核与复现。

## Appendix A: Experimental Setup

### A.1 Hardware and Software

所有实验在单机环境完成。本地推理主要使用单张 NVIDIA RTX 4090（24GB 显存），LoRA 微调使用单张 NVIDIA H200。服务器配备 Intel Xeon Platinum 8358（32 核）与 256GB 内存，存储为 2TB NVMe SSD。

软件环境如下：

- Python 3.10.12
- PyTorch 2.1.0
- Transformers 4.36.0
- LangChain 1.0.0
- GraphRAG 0.2.1
- LanceDB 0.3.2

### A.2 Model Hyperparameters

**Qwen 3 14b LoRA 微调：**

- 学习率：2e-5
- 批大小：8（梯度累积步数 = 4）
- 训练轮数：3
- 预热步数：100
- 最大序列长度：2048
- LoRA rank：16
- LoRA alpha：32

**推理参数：**

- 温度：0.3（检测），0.7（生成）
- top-p：0.9
- 最大输出 tokens：512
- 停止序列：`["\n\n\n"]`

## Appendix B: Prompt Templates

### B.1 Entity Extraction Prompt (Medical Customization)

我们使用如下“协议式”指令模板，从患者的 EHR 数据中抽取实体与关系，用于构建患者特定知识图谱。

**Instruction（指令）**

你是一名医学知识图谱抽取系统。请从输入的 EHR 记录中抽取医学实体与关系，并以 JSON 输出。

**Constraints（约束）**

1. **患者实体唯一性**
     - 为整个记录创建且仅创建一个 `Patient` 实体。
     - 不要创建 `Patient_1`、`Patient_2` 或多个患者实体。
     - 所有诊断、用药、检查都必须链接到这一个 `Patient`。

2. **化验检查归一化**
     - 将单项指标归并到检查面板中，例如：
         - CBC：WBC、RBC、HGB、HCT、PLT
         - 肝功能：ALT、AST、ALK PHOS、BILIRUBIN
         - 肾功能：CREAT、UREA N、BUN
     - 不要为每个指标创建单独的 `LAB_TEST` 实体。
     - 为具体数值创建 `LAB_RESULT` 实体，并通过关系指向对应 `LAB_TEST`。

3. **语言一致性**
     - 实体名称统一使用中文。
     - 英文保留在描述字段中。
     - 示例：`name="高脂血症"`, `description="HYPERLIPIDEMIA"`。

**Entity Types（实体类型）**

- PATIENT, DIAGNOSIS, MEDICATION, LAB_TEST, LAB_RESULT
- VITAL_SIGN, SYMPTOM, PROCEDURE, DEPARTMENT

**Relation Types（关系类型）**

- HAS_DIAGNOSIS, PRESCRIBED, SHOWS, UNDERWENT
- HAS_VITAL_SIGN, TESTED_BY, RESULT_OF, TREATED_IN

**Output Format（输出格式）**

输出 JSON，包含 `entities` 与 `relationships` 两个数组：

```json
{
    "entities": [
        {
            "id": "...",
            "type": "PATIENT|DIAGNOSIS|...",
            "name": "...",
            "description": "..."
        }
    ],
    "relationships": [
        {
            "source": "...",
            "target": "...",
            "type": "HAS_DIAGNOSIS|PRESCRIBED|...",
            "description": "..."
        }
    ]
}
```

**Why this design（设计动机）**

该模板通过“患者实体唯一性”和“化验面板归一化”约束，减少实体过度碎片化，并提高跨表证据对齐的一致性，从而为后续 GraphRAG 检索与事实核验提供更稳定的结构化支撑。

### B.2 Hallucination Detection Prompt

我们使用如下模板对出院小结中的单句陈述进行核验：给定句子与从知识图谱检索到的 EHR 证据上下文，判断该句是否为幻觉，并输出结构化解释。

**Inputs（输入）**

- `sentence`: 待核验的句子
- `evidence_context`: 检索到的 EHR 证据上下文

**Task（任务）**

1. 判断句子是否被证据支持。
2. 识别任何相互矛盾的信息。
3. 分配证据等级：
     - E1：由结构化 EHR 字段支持
     - E2：由非结构化文本支持
     - E3：证据未提及，但根据上下文判断应视为有问题
     - E4：与现有事实证据冲突（相互矛盾）

**Output Format（输出格式）**

输出 JSON：

```json
{
    "sentence_index": 0,
    "sentence": "...",
    "hallucination_detected": false,
    "evidence_grade": "E1|E2|E3|E4",
    "explanation": "...",
    "supporting_evidence": ["..."],
    "conflicting_evidence": ["..."],
    "confidence_score": 0.0
}
```

**Consistency Rule（一致性规则）**

若 `hallucination_detected = true`，则 `evidence_grade` 必须为 `E3` 或 `E4`。

## Appendix C: Error Analysis

基于对典型误判案例的定性复核，主要错误模式如下。

**False Negatives（遗漏的 E4 幻觉）**

- 医学同义词或缩写未能与 EHR 中的标准表述正确对齐。
- 需要跨时间点整合病程信息的陈述未被稳定识别为冲突。
- 生成句子依赖隐含临床含义，而非 EHR 中的显式记录。
- 图检索未返回足以支撑判别的关键证据。

**False Positives（正确陈述被标记）**

- 生成文本对病历中的已有暗示作了保守外推，但原文并未显式逐字记录。
- 语义等价表达在字符串层面未完全对齐。
- 时间范围或事件先后关系的表述存在歧义。
- 图谱抽取阶段的实体或关系误差传导到最终判别。

## Appendix D: Dataset Details

### D.1 Source Tables

我们基于 Discharge-Me / MIMIC-IV 的多表字段构建实验数据。下述“表级记录规模”反映的是完整原始表视图的规模，用于说明数据来源；其规模不等同于本文按 train、valid、test_phase_1、test_phase_2 切分后的实验目录规模，也不应直接理解为本文 250 名患者实验子集的实际规模。

**Diagnosis Table（diagnosis.csv）**

- 规模：143,285 条诊断记录（原始表视图）
- 关键字段：`subject_id`, `stay_id`, `icd_code`, `icd_version`, `icd_title`
- 示例：`10000032`, `J18.9`, `ICD-10`, “未特指病原体的肺炎”

**ED Stays and Triage Tables（edstays.csv / triage.csv）**

- 用途：提供急诊就诊、分诊与生命体征信息
- 关键字段（标识与时间）：`subject_id`, `stay_id`, `intime`, `outtime`
- 关键字段（生命体征）：`temperature`, `heartrate`, `resprate`, `o2sat`, `sbp`, `dbp`, `pain`, `acuity`

**Discharge Target Table（discharge_target.csv）**

- 用途：提供 `brief_hospital_course` 与 `discharge_instructions` 等目标 section 文本
- 关键字段：`subject_id`, `note_id`, `brief_hospital_course`, `discharge_instructions`
- 说明：是生成与核验任务的核心文本来源之一

**Radiology Table（radiology.csv）**

- 用途：补充放射学文本证据
- 关键字段：`subject_id`, `stay_id`, `text`, `charttime`
- 说明：为影像相关事实核验提供补充证据

### D.2 Data Preprocessing

我们采用如下预处理流程将多源表字段组织为 GraphRAG 可用的输入格式：

1. **多表连接**：在 `subject_id` 与 `stay_id` 上整合 diagnosis、discharge、discharge_target、edstays、radiology、triage 六类来源。
2. **去重**：移除重复的 stay 记录（348 例）。
3. **缺失值处理**：
     - 删除缺失出院文本的记录（1,203 例）。
     - 对 triage 中缺失的生命体征字段进行标准化处理。
4. **文本清洗**：
     - 移除 PHI 标记（例如 `[* * ... * *]`）。
     - 规范化空白字符。
     - 修正常见拼写错误。
5. **格式转换**：CSV → JSONL，以兼容 GraphRAG。

## Appendix E: Reproducibility Checklist

- Code Availability：项目代码计划发布于 https://github.com/[username]/CuraView
- Data Access：MIMIC-IV（需要 PhysioNet 凭证访问）
- Model Checkpoints：HuggingFace Hub `[username]/curaview-qwen3-14b`
- Training Configuration：详见附录 A.2
- Random Seed：所有实验固定为 42
- Hardware：LoRA 微调使用单张 NVIDIA H200；本地推理使用单张 RTX 4090（24GB）
- Training Time：约 48 小时（LoRA 微调）
- Dependencies：仓库 `requirements.txt`
