# 4 Methodology

## 4.1 System Architecture Overview

CuraView is an end-to-end medical hallucination detection framework with three core components working in concert.

The hallucination generation agent is built on LangChain 1.0, systematically generating diverse medical errors.

The GraphRAG knowledge graph constructs patient-specific knowledge bases from electronic health records (EHRs), supporting context-enhanced retrieval.

The hallucination detection agent leverages knowledge graphs to verify generated text and identify hallucinations based on evidence. These three components form a complete generation-verification-evaluation closed-loop system.

<a id="fig:system-architecture"></a>

![Figure 1. CuraView System Architecture Overview. The framework comprises three core components working in concert: the hallucination generation agent based on LangChain systematically generates medical errors; the GraphRAG knowledge graph constructs patient-specific knowledge bases from EHRs; the hallucination detection agent leverages knowledge graphs for evidence verification.](figures/figure_01.png)

*Figure 1. CuraView System Architecture Overview. The framework comprises three core components working in concert: the hallucination generation agent based on LangChain systematically generates medical errors; the GraphRAG knowledge graph constructs patient-specific knowledge bases from EHRs; the hallucination detection agent leverages knowledge graphs for evidence verification.*

### Data Flow

The system processes data through five stages.

**Data Preparation Phase** integrates multi-table MIMIC-IV data through transformation, generating unified patient records.

**Knowledge Graph Construction Phase** performs entity extraction, relationship identification, and community detection on patient data, ultimately storing the results in a database.

**Hallucination Generation Phase** begins with original discharge summary text, proceeding through sentence segmentation, applicability assessment, and hallucination generation to produce rewritten text and corresponding hallucination records.

**Hallucination Detection Phase** segments rewritten text into sentences and retrieves knowledge context through GraphRAG queries, combined with LLM reasoning to generate detection results.

**Comparative Evaluation Phase** integrates generation and detection results, computing recall, precision, and F1 scores, generating evaluation reports.

### Technical Framework

The agent functionality is implemented using the LangChain framework, with GraphRAG employed for knowledge graph construction and retrieval. Model deployment supports both API calls and local inference, respectively using large-scale commercial models and lightweight open-source models. Text processing employs the SaT (Segment any Text) model [43] combined with rule-based methods for sentence segmentation; graph construction uses community detection algorithms for hierarchical organization.

## 4.2 Hallucination Generation Agent

### Design Principles

The hallucination generation agent aims to systematically generate diverse medical error patterns while maintaining medical plausibility. We established four core principles:

**P1: Medical Plausibility** -Only generating hallucinations for sentences containing medical information, with generated hallucinations being medically plausible to avoid easy detection (for example, avoiding obviously impossible values like "blood pressure 500/300").

**P2: Type Diversity** -Covering seven clinical error types, each with independent generation strategies.

**P3: Controllable Sampling** -Through parametric configuration of rewriting ratio (default 40%), balancing data diversity with annotation cost.

**P4: Evidence Traceability** -Each hallucination is annotated with evidence grade (E1-E4) for subsequent detection evaluation.

Beyond supporting hallucination detection as the core function, this agent also possesses important data synthesis value: the systematic hallucination generation process can continuously construct high-quality medical hallucination annotated data, with each sample containing at minimum original text, hallucinated text, hallucination type, evidence grade, and detailed explanation; meanwhile, reasoning traces and knowledge retrieval records generated during the detection phase can further be deposited as distillation data for transferring the reasoning capabilities of large models to lightweight models. That is, generation and detection not only form a quality control closed-loop but also serve as data sources for subsequent model iteration.

### Two-Stage Sentence Filtering Mechanism

To ensure generation quality, we designed a two-stage sentence filtering workflow:

**Stage 1: Sentence Applicability Assessment.** The system first segments discharge summary text into individual sentences, then has an LLM assess whether each sentence is suitable for hallucination rewriting. Three core assessment criteria are: (1) whether the sentence contains verifiable medical facts (such as diagnoses, medications, lab values) rather than patient demographics or subjective descriptions; (2) whether maintaining medical plausibility is possible after rewriting, avoiding obviously impossible content; (3) whether sentence complexity is moderate, neither overly simple (such as "patient admitted") nor overly complex in ways that make quality control difficult. The system employs concurrent batch processing to improve efficiency and automatically retries upon API call failures.

**Stage 2: Hallucination Generation.** For sentences passing applicability assessment, the system executes the following steps: first, extracting relevant evidence information from the patient's complete EHR data, including diagnosis records, medication information, lab results, and vital signs; second, the LLM generates rewriting based on extracted evidence and the original sentence, following one of seven hallucination types, ensuring that generated errors are medically plausible but inconsistent with evidence; finally, the system constructs structured output including the modified hallucinated text, belonging hallucination type (such as diagnosis error, medication error, etc.), detailed explanation of modifications, and evidence grade annotation based on EHR evidence (E1-E4). Generated results undergo dual verification of format and logical consistency, with non-conforming results discarded or regenerated.

### Seven Hallucination Types

Table 1 provides our hallucination classification system and examples.

<a id="tab:hallucination-types"></a>

| Type | Definition | Original | Hallucination | Evidence |
| --- | --- | --- | --- | --- |
| diagnosis_error | Incorrect diagnosis | Diagnosed as pneumonia | Diagnosed as tuberculosis | E4 |
| medication_error | Incorrect medication/dosage | Aspirin 81mg | Aspirin 325mg | E4 |
| exam_result_error | Fabricated exam value | Blood glucose 96 mg/dL | Blood glucose 196 mg/dL | E4 |
| time_error | Time error | Admitted 1/5 | Admitted 1/15 | E4 |
| value_error | Incorrect vital sign | Blood pressure 120/80 | Blood pressure 180/120 | E4 |
| negation_error | Affirmation/negation reversal | No diabetes history | Diabetes history | E4 |
| invented_fact | Fabricated event | - | Underwent appendectomy | E3 |

*Table 1. Seven Hallucination Types and Examples*

### Evidence Grading System

This work adopts the E1-E4 evidence grading system defined in Section 3.3, implementing it as the sample annotation protocol during the generation phase. In concrete implementation, six types directly conflicting with existing EHR facts (diagnosis_error, medication_error, exam_result_error, time_error, value_error, negation_error) are annotated as E4; invented_fact, because it is not mentioned in evidence yet should still be considered suspicious error, is annotated as E3. Correspondingly, in subsequent evaluation, we treat E4 as the primary safety-critical outcome and E3+E4 as supplementary broad-coverage metrics.

## 4.3 GraphRAG Knowledge Graph Construction

### Entity and Relationship Extraction

Table 2 summarizes the entity types we define and their statistics. The system defines ten key relationship types connecting entities, including diagnosis relationships, medication relationships, symptom relationships, procedure relationships, vital sign relationships, lab test relationships, department relationships, and clinical indication relationships, among others.

<a id="tab:entity-types"></a>

| Entity Type | Description | Average per Patient | Example |
| --- | --- | --- | --- |
| PATIENT | Patient subject | 1.0 | "Patient" |
| DIAGNOSIS | Diagnosis | 3.2 | "Pneumonia" |
| MEDICATION | Medication | 5.7 | "Aspirin" |
| LAB_TEST | Test type | 2.8 | "CBC" |
| LAB_RESULT | Lab result | 6.5 | "Glucose 96" |
| VITAL_SIGN | Vital sign | 4.1 | "BP 120/80" |
| SYMPTOM | Symptom | 2.3 | "Chest pain" |
| PROCEDURE | Procedure | 1.8 | "ECG" |
| DEPARTMENT | Department | 1.0 | "Emergency" |

*Table 2. Entity Types and Statistics*

### Domain-Customized Prompt Engineering

Applying standard GraphRAG to medical data exhibits **over-granularity problems**. We resolved three major challenges through prompt engineering:

**Challenge 1: Over-extraction of Lab Tests**

*Problem*: The original prompt would identify each lab parameter as an independent entity, causing entity proliferation. Using the single-case statistics shown in Table 3 as a typical example, the original prompt produced 240 entities, with 35 being LAB_TEST entities.

*Solution*: The lab test normalization principle requires consolidating individual parameters into test types. For example, CBC encompasses WBC, RBC, HGB, etc.; liver function encompasses ALT, AST, etc.; renal function encompasses CREAT, BUN, etc.

*Result*: In the same case in Table 3, total entities decreased from 240 to 58, with LAB_TEST entities decreasing from 35 to 6.

**Challenge 2: Patient Entity Fragmentation**

*Problem*: The original prompt could create multiple patient entities, causing the knowledge graph to fragment into multiple disconnected subgraphs.

*Solution*: The patient entity uniqueness principle requires that the entire medical record contain only one patient entity, with all diagnoses, medications, and tests connected to this single entity.

**Challenge 3: Terminology Inconsistency**

*Problem*: The same concept could exist in multiple expression forms, resulting in entity duplication and relationship confusion.

*Solution*: The language consistency principle-standardizing entity names uniformly to ensure concept uniqueness. Table 3 demonstrates typical improvement before and after prompt optimization.

<a id="tab:prompt-optimization"></a>

| Metric | Before | After | Improvement |
| --- | --- | --- | --- |
| Total entities | 240 | 58* | ↓ 75.8% |
| LAB_TEST entities | 35 | 6* | ↓ 82.9% |
| PATIENT entities | 3 | 1* | ↓ 66.7% |
| Duplicate entities | 18 | 0* | ↓100% |
| Processing time (seconds) | 171 | 42* | ↓ 75.4% |
| Connected components | 7 | 1* | Full connectivity |

*Table 3. Comparison Before and After Prompt Optimization*

### Community Detection and Hierarchical Organization

We use community detection algorithms to partition the knowledge graph into topic communities. Communities are hierarchically organized from fine-grained (related to diagnoses, medications, tests, symptoms) to coarse-grained (overall patient information). For each community, an LLM generates summary descriptions, thus supporting global retrieval capabilities.

## 4.4 Hallucination Detection Agent

The hallucination detection agent verifies generated text through GraphRAG knowledge graph queries to identify statements inconsistent with patient EHR evidence. The detection process comprises two core parts: knowledge retrieval and LLM reasoning judgment. Figure 2 presents the complete detection pipeline architecture, with evidence grade determination details in Figure 3.

<a id="fig:detection-pipeline"></a>

![Figure 2. Complete Detection Pipeline Architecture of the Hallucination Detection Agent (Formalized Representation). Decomposing generated discharge summary D into sentence set {s_i}, GraphRAG retrieves evidence context C_i for each s_i; LLM f_θ outputs judgment and explanation (y_i, r_i), evidence grade is given by g(s_i, C_i) as E_i∈{E1…E4}, ultimately forming structured output O={(s_i, y_i, E_i, r_i)}.](figures/figure_02.png)

*Figure 2. Complete Detection Pipeline Architecture of the Hallucination Detection Agent (Formalized Representation). Decomposing generated discharge summary D into sentence set {s_i}, GraphRAG retrieves evidence context C_i for each s_i; LLM f_θ outputs judgment and explanation (y_i, r_i), evidence grade is given by g(s_i, C_i) as E_i∈{E1…E4}, ultimately forming structured output O={(s_i, y_i, E_i, r_i)}.*

<a id="fig:evidence-grading"></a>

![Figure 3. Evidence Grade (E1-E4) Determination Rules (g(s_i, C_i)). First determining conflict(s_i, C_i); if no conflict exists, bases support determination on support score σ(s_i, C_i) and threshold τ_s. For "Supported", E1/E2 are distinguished by evidence source (structured EHR fields vs. unstructured clinical text).](figures/figure_02-1.png)

*Figure 3. Evidence Grade (E1-E4) Determination Rules (g(s_i, C_i)). First determining conflict(s_i, C_i); if no conflict exists, bases support determination on support score σ(s_i, C_i) and threshold τ_s. For "Supported", E1/E2 are distinguished by evidence source (structured EHR fields vs. unstructured clinical text).*

For convenient expression of the detection process and determination rules in Figure 2 and Figure 3, this work makes the following notation conventions: Let the rewritten discharge summary be segmented into n sentences to be verified, with the i-th sentence denoted s_i; the evidence context retrieved by GraphRAG for s_i is denoted C_i; the judgment function f_θ(s_i, C_i) outputs hallucination label y_i and its reasoning r_i; the evidence grading function g(s_i, C_i) outputs evidence grade E_i∈{E1, E2, E3, E4}; σ_i = σ(s_i, C_i) represents the support score between sentence and evidence, τ_s represents the support determination threshold. After aggregating detection results for all sentences, we obtain structured output O = {(s_i, y_i, E_i, r_i)}_{i=1}^n.

### Knowledge Retrieval

The system first uses the SaT model [43] to segment rewritten text into individual sentences, ensuring alignment with sentence indexing in the generation phase. For each sentence, GraphRAG performs local knowledge queries: first retrieving the top 20 most relevant entity candidates based on vector similarity, then extending to one-hop neighbor nodes, and integrating entity attributes, relationships, and community reports to construct evidence context for subsequent judgment.

### LLM Reasoning Judgment

The LLM performs step-by-step reasoning based on retrieved evidence. First, it generates reasoning process, analyzing key information comparisons between sentences and evidence; second, it determines hallucination status to establish whether hallucination exists; then it identifies hallucination type, classifying into one of seven error patterns; finally, it assesses evidence grade, annotating as E1 through E4. In implementation, the system performs at most three automatic re-detection attempts when format errors or logical inconsistencies are observed. If repeated exceptions occur during re-detection, it falls back to the original result; if inconsistency persists after the retry budget is exhausted, the last available result is retained and logged rather than silently discarded. This design balances bounded execution in production settings with result traceability.

### Schema-Constrained Structured Output

To ensure reliability of structured outputs in downstream detection and evaluation workflows, this work adopts a schema-constrained generation strategy combining structured generation theory with engineering frameworks. Specifically, we use LangChain's structured output mechanism as the implementation foundation [36, 44], defining strongly-typed schemas with Pydantic, explicitly specifying types, constraints, and nesting relationships for fields such as reasoning, hallucination_status, hallucination_type, and evidence_grade.

At the system level, this work organizes structured output reliability as a unified pipeline, partitioned into three mutually connected constraint mechanisms. The first category is **schema constraints**: task-related outputs are first defined as strongly-typed schemas and connected through LangChain's structured output interface to unified output protocols, explicitly specifying field types, value ranges, and nesting relationships. The second category is **generation-side constraints**: above the unified schema protocol, the system organizes generation processes according to underlying model capabilities; for local models, we introduce JSON prefix constraints, result extraction and repair strategies and other stabilization approaches to reduce format risk in fixed JSON output. The third category is **post-generation validation constraints**: after generation, output results continue through JSON parsing, Pydantic type checking, three-layer validation, and inconsistency result re-checking workflows to ensure structural legality and business consistency. Existing research on structured output and constrained decoding indicates that compared to relying only on prompts, explicit structural constraints, schema-based generation, and decoding-stage restrictions can more stably enhance output structural legality and consistency [45, 46, 47]. Therefore, this work does not treat prompts themselves as the primary guarantee of structural correctness, instead positioning them after these three constraint mechanisms as auxiliary quality enhancement means.

From an implementation perspective, these three constraint categories are not mutually independent but rather serially connected as a single structured output pipeline. For each sentence to be detected, the system first passes the `HallucinationDetectionResult` schema as unified output protocol to the structured output interface; subsequently, the model generates candidate results under that protocol constraint, with local models further combining JSON prefix constraints and result extraction/repair strategies to reduce format errors in fixed JSON output scenarios; finally, candidate results enter JSON parsing, Pydantic type checking, three-layer validation and inconsistency result re-checking modules, generating standardized records directly usable for subsequent evaluation and batch processing. This design enables API and local deployment to operate under identical output protocols, positioning comparison of different model sizes on end-to-end structured result availability rather than solely on single-pass natural language response quality.

### Structured Output Validation

We ensure correctness of detection result formats and logical consistency: if hallucination is detected, evidence grade must be E3 or E4; if E3, the reasoning must explain why the statement is problematic despite the evidence not mentioning it; if E4 (contradiction), clear conflicting evidence must be provided; if no hallucination is detected, evidence grade must be E1 or E2.