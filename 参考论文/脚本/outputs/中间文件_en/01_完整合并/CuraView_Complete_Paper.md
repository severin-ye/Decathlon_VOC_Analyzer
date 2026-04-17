# CuraView: A Multi-Agent Framework for Medical Hallucination Detection with GraphRAG-Enhanced Knowledge Verification

Severin Ye
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
6severin9@gmail.com

Xiao Kong
School of Computer Science and Engineering
Kyungpook National University
Daegu, Republic of Korea
kongx7546@knu.ac.kr

Xiaopeng He
West China School of Medicine
Sichuan University
Chengdu, China
hxp19180945016@stu.wchscu.cn

Guangsu Yan
School of Computer Science and Technology
Shandong University
Jinan, China
202300800569@mail.sdu.edu.cn

# Abstract

Clinical summaries, such as discharge summaries, require extracting key information from lengthy electronic health records (EHRs), which is labor-intensive when done manually. Large language models can enhance generation efficiency; however, they are prone to producing "faithfulness hallucinations"-statements that contradict the source records-which pose safety risks in medical settings. To address this, we present **CuraView**: a system that constructs a GraphRAG-based knowledge graph from patient-level EHRs and implements a closed-loop generation-detection pipeline with sentence-level evidence retrieval and classification (E1-E4), yielding structured and interpretable evidence chains of supporting or contradictory information. We evaluate our approach on a subset of 250 patients from the Discharge-Me benchmark, with 50 patients used for testing. Our fine-tuned Qwen3-14B detection model achieves an **F1 score of 0.831** on the safety-critical E4 metric, with **90.9% recall** and **76.5% precision**, and an **F1 score of 0.823** on the E3+E4 metric; on E4 detection, it delivers a **50.0% relative improvement** over the base model and outperforms RAGTruth-style and QAGS-style baselines. These results indicate that evidence-chain-based graph retrieval verification can effectively improve the factual reliability of clinical summaries while producing reusable annotated data for subsequent training and distillation.

Keywords-clinical summaries; factual consistency; hallucination detection; GraphRAG; knowledge graph

# 1 Introduction

Large language models (LLMs) have revolutionized artificial intelligence applications across diverse domains and show particularly transformative potential in healthcare. Recent models such as GPT-4, Med-PaLM 2, and their clinical variants have demonstrated notable capabilities in medical question answering. Notably, Med-PaLM was the first AI system to exceed the passing threshold (>60%) on USMLE-style questions in the MedQA benchmark [1], and Med-PaLM 2 further improved performance on this benchmark to 86.5% [2]. Concurrently, GPT-4 has shown strong competitiveness on official USMLE practice materials and the MultiMedQA benchmark [3]. More importantly, LLM use has begun to extend beyond benchmark QA into workflow-relevant clinical tasks, including diagnostic assistance, clinical documentation, radiology report generation, discharge summary generation, and patient education [4, 5, 6]. Among these tasks, discharge summary generation has already matured into a shared-task setting [6], while studies on physician time allocation and documentation burden show that documentation automation corresponds to a concrete operational need [8, 9]. Industry forecasts also indicate substantial economic upside for medical AI [7], but commercial potential does not automatically translate into bedside adoption. The central barrier is the “clinical trust gap” created by hallucinations: if generated content cannot be consistently verified against patient-level evidence, clinicians and institutions are unlikely to rely on it in real workflows.

However, this promising outlook faces a critical obstacle: *hallucinations*-the generation of plausible-sounding yet factually incorrect information. While hallucinations in general-domain LLMs may merely cause inconvenience, medical hallucinations pose severe risks to patient safety and clinical trust [10]. Prior surveys and empirical studies show that LLMs can produce fluent but factually wrong recommendations in medical QA, summarization, and clinical-support settings [5, 11]. Hallucinations in medical LLMs manifest as confidently stated but actually incorrect medical information, ranging from misdiagnosis to fabricated test results. Through systematic analysis of error patterns in clinical documentation, we identified seven key hallucination types covering error patterns in diagnosis, medication, test results, temporal information, numerical values, negation, and fabricated facts (detailed definitions provided in Section 3.2). The risks from medical AI are particularly severe. A single medication dosage error can be fatal; missing a cancer diagnosis may delay life-saving treatment; fabricated test results may trigger unnecessary interventions. Existing research also indicates that hallucinations in medical text generation exhibit marked task dependence, with error patterns, evaluation granularity, and risk profiles varying across tasks, so there is no unified "medical LLM hallucination rate" metric. This paper defers the more nuanced task variations and relevant literature to a unified discussion in Section 2.1, emphasizing here only this point: once errors enter the clinical documentation generation scenario, their risk directly translates to patient safety concerns, necessitating specialized detection mechanisms targeting patient-level factual evidence.

Current medical hallucination research exhibits four critical limitations, which motivate our work. **L1: Lack of systematic generation.** Existing medical hallucination benchmarks remain highly dependent on manual curation and expert annotation, such as Med-HALT [12], which is costly and limited in scale. No prior work has provided an **automated** hallucination generation framework capable of creating diverse medical errors at scale. **L2: Missing patient-specific context.** Most research evaluates hallucinations on generic medical questions, cross-patient aggregated corpora, or general clinical generation tasks, without organizing **individualized patient data** from electronic health records (EHRs) directly as verifiable factual evidence [13, 14]. For example, detecting whether "the patient takes aspirin" is a hallucination requires knowledge of the patient's allergy history and current medications-context that existing benchmarks typically lack. **L3: Insufficient evidence support.** Most existing medical hallucination research reports question-level accuracy, sentence-level hallucination rates, or document-level error burden, but rarely provides structured explanations for patient-level verification that clarify **why** a statement is incorrect or **what evidence** contradicts it [15, 16, 17]. This limits the development of interpretable detection methods. **L4: Focus on evaluation only.** Prior work has emphasized **evaluating** the hallucination rates of existing models [12], but has not provided an **end-to-end system** for generating, detecting, and explaining hallucinations in production environments. These four limitations are not isolated; rather, they directly motivate our four research questions: L1 leads to RQ1 on systematic hallucination generation, L2 to RQ2 on patient-specific knowledge graph construction, L3 to RQ3 on evidence-enhanced detection, and L4 to RQ4 on end-to-end framework design.

To build a clinically viable medical hallucination detection system, we must address four fundamental research questions: **RQ1: Systematic generation of diverse medical hallucinations.** Existing medical hallucination detection benchmarks are limited in scale and diversity [12]. Manual annotation of hallucinations is costly, requiring expert clinicians to identify subtle errors across thousands of patients. Moreover, real-world medical errors exhibit diverse patterns-from obvious factual contradictions to subtle clinical implausibility-requiring systematic coverage. **RQ2: Patient-specific knowledge graph construction.** Electronic health records contain rich patient information across heterogeneous tables (diagnoses, medications, test results, vital signs, clinical notes), but converting this into structured knowledge suitable for hallucination verification is non-trivial. **RQ3: Knowledge-graph-enhanced detection with context enrichment.** Given a patient's knowledge graph, detecting hallucinations requires reasoning over complex entity relationships and temporal constraints. **RQ4: End-to-end framework design.** A complete hallucination detection system requires seamless coordination among multiple components with different technical requirements. These research questions give rise to corresponding technical challenges: **C1:** For RQ1, we need an automated hallucination generation framework that can: (1) create diverse error types reflecting realistic clinical mistakes; (2) maintain medical plausibility to avoid trivial detection; (3) preserve sentence-level granularity for fine-grained evaluation; (4) provide ground truth labels with evidence-based explanations. **C2:** For RQ2, we need a knowledge graph construction pipeline that can: (1) extract medical entities and relationships from multi-table EHR data; (2) handle clinical terminology variation and abbreviations; (3) capture the temporal evolution of patient conditions; (4) enable cross-patient knowledge aggregation while protecting patient privacy; (5) scale to tens of thousands of patients. **C3:** For RQ3, we need a detection mechanism that can: (1) efficiently retrieve relevant knowledge graph context (avoiding exhaustive search over large graphs); (2) perform multi-hop reasoning to verify complex clinical statements; (3) differentiate supporting, unsupported, and contradictory statements with confidence scores; (4) generate human-interpretable explanations citing specific EHR evidence. **C4:** For RQ4, we need a system architecture that can: (1) orchestrate hallucination generation and detection agents using consistent data formats; (2) support both API-based and local model deployments for flexibility; (3) enable efficient batch processing over large patient cohorts; (4) implement robust validation to ensure generation-detection consistency; (5) provide comprehensive evaluation metrics comparing system performance across different configurations.

To address these challenges, we propose **CuraView**, a multi-agent framework for medical hallucination detection with GraphRAG-enhanced knowledge verification. We use GraphRAG rather than vanilla RAG because clinical verification is not simply a matter of retrieving similar text; it requires recovering patient-specific relational structure across diagnoses, medications, test results, and temporal information. GraphRAG organizes these distributed pieces of multi-table EHR evidence into a queryable relational graph, making it more suitable for sentence-level factual verification. CuraView addresses the four limitations above as follows: For **L1**, it provides an automated hallucination generation framework with seven error types; for **L2**, it constructs patient-specific knowledge graphs grounded in EHRs; for **L3**, it implements evidence-grade annotation (E1-E4) to provide interpretable detection results; for **L4**, it delivers a complete end-to-end generation-detection-evaluation pipeline. Our work makes the following key contributions:

- Contribution 1: A taxonomy of medical hallucinations oriented toward clinical documentation
- Contribution 2: An end-to-end multi-agent framework
- Contribution 3: GraphRAG-driven medical knowledge graphs
- Contribution 4: A unified structured output reliability pipeline
- Contribution 5: A comprehensive evaluation framework

# 2 Related Work

Before detailing the CuraView methodology, we first survey existing research on medical hallucination detection, knowledge graph-augmented generation, and multi-agent systems to establish the positioning and innovation of this work.

## 2.1 Hallucination in Medical Large Language Models

### Capabilities and Limitations of Medical Large Language Models

Recent years have witnessed significant advances in applying large language models (LLMs) to the medical domain. In terms of core medical reasoning benchmarks, **Med-PaLM** [1] was the first AI system to exceed the passing score on USMLE-style questions in MedQA, and **Med-PaLM 2** [2] further pushed multiple medical QA benchmarks to state-of-the-art performance. Concurrently, **GPT-4** demonstrated strong competitiveness on USMLE official practice materials and MultiMedQA [3]. In the domain-adaptation direction, **Clinical Camel** [18] and **PMC-LLaMA** [19] showed that continued training on medical corpora can improve performance in clinical note generation and medical question answering. Taken together, these studies establish that medical LLMs can answer and generate, but not yet that they can be trusted to produce patient-grounded clinical documents in high-risk settings.

However, these impressive benchmark results mask a critical weakness: *hallucination*. Ji et al. [20] provided a comprehensive survey of hallucinations in natural language processing, categorizing them into **factual hallucinations** (contradicting established knowledge) and **faithfulness hallucinations** (inconsistent with source documents). In the medical context, both types of hallucinations pose serious risks.

### Medical Hallucination Benchmarks

**Med-HALT** [12] introduced the first systematic medical hallucination benchmark, covering 1,755 questions across five medical specialties. They found that even state-of-the-art models like GPT-4 exhibited hallucination rates of 10-15% on factual medical questions. Critically, hallucinations often accompanied high confidence scores, making them particularly dangerous in clinical settings.

Furthermore, real-world cases have documented public instances of AI-generated medical advice containing dangerous hallucinations [12, 20], indicating that the risk is not confined to benchmark environments but translates directly into practical demand for reliable detection mechanisms.

**Asgari et al.** [16] advanced the evaluation granularity from "question-level accuracy" to **sentence-level clinical summary safety assessment**. Among 12,999 clinician-annotated sentences, they reported sentence-level hallucination rates of 1.47% and omission rates of 3.45%, with 44% of hallucinations classified as critical errors. This demonstrates that while absolute hallucination rates may be lower in relatively structured clinical note summary tasks, when errors do occur, their clinical risk is not insignificant.

**Williams et al.** [17] examined **discharge summary narrative generation**. Rather than reducing the problem to a single hallucination rate, this work examined inaccuracy, omission, and hallucination as three error categories, comparing the total unique errors per document. Results showed that LLM-generated versions contained an average of 2.91 unique errors, higher than the 1.82 errors in physician-authored versions. This suggests that the discharge summary context is better suited to measuring risk via "errors per document" rather than a single sentence-level hallucination rate.

The recent **Discharge Me** shared task further advanced discharge summary generation from single case studies to a unified benchmark [6]. Within that benchmark, **EPFL-MAKE** handled extremely long medical records through context window expansion and dynamic information selection [21], whereas **UF-HOBI** adopted a two-stage hybrid pipeline of extracting key clinical concepts and then generating coherent paragraphs [22]. These works demonstrate that discharge summary generation has become a clearer task family, but the main goal remains better document generation rather than sentence-level patient-grounded verification with explicit evidence.

In **radiology report generation**, risks are more pronounced. **Artsi et al.** [23] conducted a systematic review of 15 studies and found that all models exhibited varying degrees of hallucinations, misdiagnoses, or report inconsistencies; further, the review noted missing clinical details were reported in 12/15 studies, showing that errors in this field involve not only "fabrication" but also "omission" and "mismatch".

**RadFlag** [24] provided finer-grained analysis of radiology report hallucinations from a sentence-level detection perspective. This study reported that approximately 40% of generated sentences in high-performing radiology report generation models may contain hallucinations; in its report-level assessment, reports flagged as high-risk by the system averaged 4.2 true hallucinations, while accepted reports averaged 1.9. This further demonstrates that hallucination density and report-level risk in radiology tasks may be significantly higher than in other more structured medical text generation scenarios.

In summary, existing literature better supports a **task-dependent, evaluation-granularity-dependent** understanding: "hallucination" in medical question-answering, clinical summaries, discharge summaries, and radiology report generation is not a single metric directly comparable across domains. The fine-grained taxonomy proposed in Section 3.2 of this work focuses on sentence-level errors in clinical documents and emphasizes alignment with patient-specific EHR evidence, thus complementing prior work focused on question-answering or radiology summaries.

## 2.2 Knowledge Graphs and Retrieval-Augmented Generation

### Foundations of Retrieval-Augmented Generation

Retrieval-augmented generation (RAG) [25] introduced a paradigm shift in LLM applications by combining neural retrieval with language generation. Classic RAG architectures use dense passage retrieval (DPR) to fetch relevant documents from a corpus for generation by models like BART based on retrieved context. This approach significantly improved performance on knowledge-intensive tasks such as open-domain question-answering.

Subsequent work extended RAG to fact verification and domain-specific question answering. **RARR** [26] focused on retrieval-supported revision of model outputs using external evidence; in medical scenarios, **MedRAG** [27] systematically compared different medical RAG configurations; in the biomedical domain, **BioRAG** [28] combined scientific literature, domain-specific embeddings, and knowledge hierarchies to support complex reasoning. Although these works demonstrate clear value of retrieval augmentation in professional domains, their core remains primarily built on **flattened document retrieval**, which is insufficient for explicitly modeling structured relationships among medical concepts. For example, in discharge-summary verification, the system must do more than retrieve a sentence stating that a patient is taking a medication; it must also relate that medication to allergy history, discontinuation records, or abnormal laboratory findings documented elsewhere. Flat retrieval may return locally similar snippets, but it often fails to recover such cross-source relationships reliably.

### GraphRAG: Graph-Structured Retrieval Augmentation

Microsoft's **GraphRAG** [29] addresses the limitation of traditional RAG in modeling document structural relationships by converting documents to knowledge graphs before retrieval. The method employs a two-level indexing architecture: entity-level indices (local search) for retrieving specific entities and their direct relationships, while community-level indices (global search) aggregate knowledge from communities detected by the Leiden algorithm, providing broader contextual understanding.

GraphRAG's graph construction process comprises four key steps: first, extracting entities and relationships from text using large language models to construct an initial knowledge graph; second, applying the Leiden community detection algorithm to identify semantically related entity clusters; subsequently, generating summary descriptions for each community; finally, constructing hybrid vector indices combining structured graph knowledge and unstructured text. Compared to standard RAG, this graph-structured approach can capture complex multi-hop reasoning relationships and discover potential thematic patterns in document collections through community structure.

Overall, existing research exhibits a technological evolution from no explicit external evidence, to flattened retrieval augmentation, to graph-structured retrieval augmentation. In medical contexts, recent work on **Medical Graph RAG** further demonstrates that connecting patient documents to trustworthy medical sources while combining graph retrieval and response refinement can significantly enhance evidence base and reliability [30]; correspondingly, medical RAG systems surveys also indicate that external knowledge sources are an important technical path for mitigating medical hallucinations and enhancing transparency [31]. In medical hallucination detection scenarios requiring patient-specific evidence verification, multi-hop relationship reasoning, and cross-source information integration, this trajectory explains why GraphRAG is more suitable than retrieval-free or flat text segment-based retrieval approaches as the methodological foundation for this work.

### Medical Knowledge Graphs

Medical ontologies and knowledge graphs provide structured representations of clinical knowledge:

-   **UMLS (Unified Medical Language System)** [32]: Integrates over 200 medical terminology sets, enabling semantic interoperability, but lacks patient-specific information

-   **SNOMED-CT** [33]: A comprehensive clinical terminology system with hierarchical relationships

-   **ICD Coding** [34]: International Classification of Diseases standard

**EHR-based Knowledge Graph Construction:** Rotmensch et al. [13] automatically constructed disease knowledge graphs from EHR data, discovering novel disease associations through ICD codes and clinical notes. Finlayson et al. [14] developed entity linking methods for clinical notes, aligning mentions with UMLS concepts.

**Challenges in Medical Knowledge Graph Construction:**

1.  **Terminology Variants**: Abbreviations, colloquialisms, spelling errors in clinical notes

2.  **Temporal Modeling**: Evolution of disease progression and treatment history

3.  **Privacy Protection**: Trade-offs between de-identification and knowledge completeness

4.  **Cross-patient Aggregation**: Balancing knowledge sharing with privacy protection

Beyond general ontological resources, recent surveys on **combining SNOMED CT with large language models** also show that terminological knowledge can be introduced into downstream NLP and NLG processes through input augmentation, additional fusion modules, or retrieval-based knowledge injection, bringing performance improvements in many tasks [35]. This also provides methodological basis for this work's subsequent integration of structured medical terminology with patient-level knowledge graphs.

### Positioning of Our Approach

**Key Distinctions:**

1.  **Patient-Specific Knowledge Graphs**: Individualized graphs are constructed for each patient rather than relying on general medical knowledge bases

2.  **Verification-Oriented Evidence Semantics**: An E1-E4 evidence grading scheme is used to support sentence-level factual verification

3.  **Multi-Table EHR Integration**: Heterogeneous sources such as diagnoses, medications, laboratory results, and vital signs are unified

4.  **Dynamic Patient-Grounded Evidence Organization**: Evidence is structured around each patient's actual records rather than static general-purpose ontologies

## 2.3 Multi-Agent Systems and LLM Applications

### LLM Agent Frameworks

**LangChain** [36] provides a modular framework including prompt templates, LLM wrappers, tool-calling interfaces, and memory management. We built CuraView's generation and detection agents on LangChain 1.0 to ensure scalability.

**AutoGPT** [37] demonstrated autonomous goal decomposition with long-term memory and internet access. **ReAct** [38] introduced the "reasoning + action" paradigm, alternating between chain-of-thought and tool-calling in iterative reasoning.

Recent agent literature also indicates that parameter scale is not the only determinant of tool-oriented agent performance. On structured subtasks such as function calling, multi-turn tool use, and workflow orchestration, smaller models optimized through high-quality agent data synthesis, supervised fine-tuning, or rule-based reward learning can achieve performance comparable to or even exceeding larger general-purpose models [39, 40, 41]. More specifically, **ToolACE** [39] focuses on function-calling ability, **APIGen-MT** [40] emphasizes multi-turn agent interaction, and **Nemotron-Research-Tool-N1** [41] highlights the gains from rule-based reward learning for tool use. Together, they support a broader point: in agent settings, task specialization, structured interfaces, and training data quality can matter more on some subtasks than raw parameter scale alone.

### Comparison with Existing Work

Among existing medical multi-agent systems, representative works like **MedAgents** [42] primarily focus on diagnosis and treatment tasks, relying on general medical knowledge bases (PubMed, textbooks, etc.) for reasoning, yet lack verification mechanisms for LLM-generated content quality. These systems face two critical limitations in handling patient-specific scenarios: first, they cannot leverage individualized electronic health records (EHRs) for precise reasoning; second, they lack systematic detection mechanisms for hallucination issues in generated content. Methodologically, CuraView's dual-agent design combines two emerging directions. On the one hand, adversarial sample generation continually constructs more challenging errors, improving detector robustness. On the other hand, the LLM-as-a-judge paradigm suggests that evidence-centered structured evaluation is better suited to high-risk quality control than a single open-ended response. Under this view, the separation between the generation agent and the detection agent is not merely an engineering decomposition, but a principled way to support two complementary tasks: producing hard cases and performing evidence-driven verification.

CuraView achieves key breakthroughs on four dimensions: **(1) Task Positioning** -the first multi-agent system focused on hallucination detection and quality control rather than traditional diagnosis and treatment support; **(2) Knowledge Sources** -constructing patient-specific EHR knowledge graphs to provide individualized evidence rather than relying on generalized medical literature; **(3) Agent Collaboration** -employing an adversarial generation-detection architecture that systematically challenges the detection agent's robustness with generated samples; **(4) Data Contribution** -simultaneously producing training and distillation data resources during the adversarial process. The emphasis here is on distinctions from existing work, with specific system implementation detailed in Section 4.

Furthermore, compared to existing medical agent systems remaining primarily at the levels of prompt engineering, general tool-calling, or single model output, CuraView emphasizes systematic usability of structured outputs-whether generation results can stably enter subsequent verification, evaluation, and batch processing workflows. This engineering distinction represents an important divergence from general medical agent frameworks, with complete mechanisms detailed in Section 4.

# 3 Problem Definition: Medical Hallucination Definition, Classification, and Evidence Grading

## 3.1 Definition of Hallucination

In the context of large language models (LLMs), *hallucination* refers to the phenomenon where model-generated content appears plausible but actually contradicts established knowledge or source documents [20]. Ji et al. categorized hallucinations into two types: **factual hallucination** (contradicting established knowledge) and **faithfulness hallucination** (inconsistent with source documents).

This study focuses on **faithfulness hallucinations** in the medical domain, particularly those arising from errors in clinical documentation generation. Unlike the general domain, medical hallucinations pose a direct threat to patient safety-a single medication dosage error can be fatal, missing a cancer diagnosis may delay life-saving treatment, and fabricated test results may trigger unnecessary interventions.

As illustrated in the introduction, the existing literature has repeatedly observed medical hallucination risks in tasks such as clinical summaries, discharge summaries, and radiology reports; however, error rates, severity, and evaluation granularity vary markedly across tasks, so there is no unified "medical LLM hallucination rate" metric [12, 20, 16, 17, 23, 24]. Rather than repeating the statistical details of each task, this section focuses on the definitional content that directly underpins the subsequent methods in this paper: the hallucination taxonomy and evidence grading system for the clinical documentation scenario.

## 3.2 Medical Hallucination Taxonomy

Based on systematic analysis of error patterns in clinical documentation, we classify medical hallucinations into seven types, each corresponding to different levels of clinical risk:

1.  **Diagnostic Errors**: Misidentification of disease, such as mistakenly writing "pneumonia" as "tuberculosis". Such errors may lead to completely incorrect treatment plans and carry extremely high clinical risk.

2.  **Medication Errors**: Errors in medication or dosage, such as mistakenly writing "aspirin 81mg" as "aspirin 325mg". Dosage errors can lead to drug toxicity or treatment failure and represent a significant threat to patient safety.

3.  **Test Result Errors**: Fabricated or incorrect test values, such as mistakenly writing "blood glucose 96mg/dL" as "blood glucose 196mg/dL". Such errors may trigger unnecessary emergency interventions or delay necessary treatment.

4.  **Temporal Errors**: Inconsistencies in temporal information, such as mistakenly writing "admitted yesterday" as "admitted last week". Temporal errors affect understanding of the disease course and decisions regarding treatment timing.

5.  **Numerical Errors**: Errors in vital sign values, such as mistakenly writing "blood pressure 120/80mmHg" as "blood pressure 180/120mmHg". Such errors may trigger erroneous emergency responses or obscure genuine critical situations.

6.  **Negation Errors**: Reversal of affirmative/negative relationships, such as mistakenly writing "no history of diabetes" as "history of diabetes". A seemingly minor change in negation can completely alter the patient's medical risk assessment.

7.  **Fabricated Facts**: Completely invented clinical events, such as adding non-existent surgical records. These errors typically have no mention in the evidence but should be regarded as suspicious or incorrect based on the model's judgment of context and clinical knowledge, representing a typical E3-class hallucination.

This taxonomy differs from prior work [13, 20] by focusing on **sentence-level** errors in **clinical documentation**, enabling fine-grained assessment and localization.

## 3.3 Evidence Grading System

To quantify the detectability and clinical impact of hallucinations, we introduce a four-level evidence grading system (E1-E4):

-   **E1 (Strong Support)**: The statement has explicit EHR evidence support, such as corresponding diagnostic codes, medication records, or test results in the patient's records.

-   **E2 (Weak Support)**: The statement has indirect evidence support, such as information that can be inferred from related facts, but lacks direct documentation. For example, even if the record lacks an explicit diagnosis code for diabetes, a statement such as "the patient has diabetes" may still be treated as a typical E2 (Weak Support) case when the patient is on long-term glucose-lowering medication such as metformin.

-   **E3 (No Support)**: The statement is not mentioned in the EHR evidence and lacks direct support, yet should be regarded as problematic based on the model's judgment of context; typical scenarios include entirely fabricated information, addition of nonexistent events, or inclusion of facts not present in the medical record.

-   **E4 (Contradiction)**: The statement directly contradicts explicit factual evidence in the EHR, such as diagnoses, medications, laboratory values, or negation relationships inconsistent with the records. This is the most critical safety level, representing errors that can be definitively determined by evidence.

This study focuses on detecting **E3 (No Support)** and **E4 (Contradiction)** hallucinations, as these two categories represent clinical statements requiring systematic verification. Among these, E4-level hallucinations are the primary focus for patient safety concerns, while E3-level hallucinations represent suspicious statements not mentioned in the evidence but judged by the model to be problematic.

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

# 5 Experimental Design

## 5.1 Dataset

### Discharge-Me Dataset

We evaluate CuraView on the Discharge-Me dataset. Discharge-Me is part of the BioNLP 2024 clinical text generation shared task, constructed from the MIMIC-IV clinical database for Emergency Department (ED) discharge summary section generation, rather than the official submodule of MIMIC-IV v2.2 [48, 6]. In our experimental implementation, we use its corresponding structured processing version covering emergency department visit records from Beth Israel Deaconess Medical Center between 2011 and 2019, from which we extracted authentic clinical documents and structured medical records available for retrieval and verification.

In this work, we distinguish three levels of data usage: target text, generation reference text, and auxiliary verification information during the detection phase. The brief_hospital_course in discharge_target constitutes the target text for sentence-level hallucination generation and detection; correspondingly, the complete discharge record text serves as the primary factual reference during the generation phase, constraining the model from producing statements that can be definitively identified as incorrect by the original discharge record.

The dataset includes six categories of source information:

-   **diagnosis**: ICD-9/ICD-10 diagnostic codes

-   **discharge**: Complete discharge record text, serving as the primary factual reference text in the current generation pipeline

-   **discharge_target**: Contains target sections including brief_hospital_course and discharge_instructions, where brief_hospital_course is the primary examination target text for the main experiment

-   **edstays**: Emergency department stay records

-   **radiology**: Radiology report text

-   **triage**: Triage information and vital sign fields, including temperature, heartrate, resprate, o2sat, sbp, dbp, pain, acuity

We include only brief_hospital_course from discharge_target in the main experiment for hallucination generation and detection, excluding discharge_instructions from formal evaluation. The primary reason is that brief_hospital_course has a clearer correspondence with the original discharge record, making it more suitable for constructing sentence-level errors that can be directly verified; in contrast, discharge_instructions primarily involves post-discharge behavioral recommendations, follow-up requirements, and patient education information, which would be difficult to constrain with sentence-level evidence within the current closed-loop data. Therefore, we focus evaluation on brief_hospital_course with relatively complete evidence chains; future work could incorporate external medical knowledge graphs as well as guideline-based and pharmaceutical knowledge resources to provide more stable normative references for discharge_instructions, enabling fact screening and consistency verification for discharge guidance content.

### Data Partitioning

We constructed an experimental subset containing 250 patients from the Discharge-Me dataset and employed fixed patient-level partitioning for training and testing:

-   **Training + Validation Set**: Patients 1-200 (200 patients)

    -   Training Set: 95% of Patients 1-200

    -   Validation Set: 5% of Patients 1-200

-   **Test Set**: Patients 201-250 (50 patients)

Table 4 provides detailed dataset statistics.

<a id="tab:dataset-stats"></a>

| Data Item | Corresponding Data |
| --- | --- |
| Fixed Experimental Subset | 250 patients |
| Qwen 3 plus Raw Distillation Data Pool | Patients 1-200, 4600 samples |
| Patient-level Evaluation Partition | Patients 1-200 for training/validation, Patients 201-250 for testing |
| Test Sentences to be Examined | Patients 201-250, 1103 sentences total for examination |
| Curated Data Training Subset | Data subset obtained through quality filtering of Patients 1-200 |

*Table 4. CuraView Experimental Data Partitioning and Sample Scale.*

### Data Source Notes

The official Discharge-Me benchmark is constructed from MIMIC-IV, targeting discharge summary section generation tasks [48, 6]. Considering: (1) computational costs of GraphRAG knowledge graph construction and indexing; (2) labor intensity of manual quality verification and error analysis; (3) research focus on method verification rather than large-scale deployment, we constructed a fixed experimental subset covering 250 patients, with Patients 1-200 for training/validation and Patients 201-250 for testing. The Qwen 3 plus raw distillation data pool (Raw Data) in this work refers to 4600 training/validation samples within the Patients 1-200 range; the patient_201-250 test scope contains 1103 sentences for examination; curated data refers to the training subset retained after quality filtering within the Patients 1-200 range. Specifically, we retained only six evidence-grade and label-consistent categories, E1_F_F, E1_T_T, E2_F_F, E2_T_T, E3_F_F, and E4_T_T, while filtering low-quality cases such as E3_T_T (insufficient-evidence positives) and E4_F_T (false-positive detections). The training framework also supports optional metadata-based weighted sampling, where reward_type and priority are used to assign larger sampling weights to more critical samples; however, to avoid conflating data curation effects with sampling policy, all main-result models reported in this paper use standard random sampling rather than weighted sampling. Future work can scale to larger complete benchmark data.

### Evaluation Subset

To conduct in-depth performance analysis, the test set contains 50 patients (Patients 201-250). This configuration facilitates manual verification and detailed case analysis while supporting the method verification-focused experimental objectives of this work. All main experimental results are based on test data from these 50 patients.

### Sentence-level Ground Truth Construction

This study adopts a generation-stage-as-ground-truth strategy for constructing sentence-level gold labels. Each rewritten sentence is accompanied by a structured record containing the original sentence index, the hallucinated rewrite, the hallucination type, and its E3/E4 evidence grade. Rather than manually re-annotating the entire test set, the evaluation stage uses these generation-side records as sentence-level gold labels and compares them directly with detector outputs. As an additional check, on an independently sampled subset, agreement between automated labels and manual review was approximately X%. The advantage of this design is that the labels are tightly aligned with the error-injection process, but its limitation is that boundary cases may still be influenced by automated rules; we therefore discuss this issue explicitly in the limitations section.

## 5.2 Evaluation Models

The main experiment evaluates four model configurations, covering both API and local deployment modes:

### Baseline Model

**Qwen 3 plus (API)**: Large-scale commercial API model provided by Alibaba Cloud, with undisclosed parameter scale. As a high-performance baseline, it represents the performance ceiling of cloud-based API deployment.

Additionally, in literature-style reference comparison experiments, we employ Qwen 3 plus as the LLM-as-a-judge model to drive both RAGTruth-style and QAGS-style sentence-level factual consistency baselines. Both reference baselines use the same 50 test patients as the main experiment (patient_201-250, total 1103 sentences for examination), with F1, Recall, and Precision reported directly from experimental results, without introducing additional adjustments or version migration corrections.

### Local Models

**Qwen 3 14b (base)**: Open-source foundation model with 14 billion parameters, without domain-specific medical fine-tuning. Used to assess the baseline capability of general-purpose LLMs.

**Qwen 3 14b (Original Data Fine-tuning)**: Model fine-tuned on the raw data pool before quality filtering, used to assess the impact of training data quality on fine-tuning effectiveness; training uses standard random sampling without additional sample weighting.

**Qwen 3 14b (Curated Data Fine-tuning)**: Model fine-tuned on the training data subset after quality filtering; this subset retains only high-quality evidence-label consistent samples and removes insufficient-evidence or anomalous detection cases. Although the training system supports weighted sampling based on reward_type and priority, this main-result model also disables that option so that the comparison against raw-data fine-tuning reflects data quality rather than sampling-policy differences. This is our primary model.

We employ Qwen 3 14b as the main local hallucination detection module. This choice reflects both the consideration of open-source controllability and the demonstrated performance of the Qwen model family on related hallucination detection tasks. Existing research shows that on RAG-oriented hallucination detection benchmarks, the Qwen2.5 series overall outperforms various Llama-series open-source models; with further task-oriented optimization, Qwen models have achieved performance approaching closed-source strong baselines in Chinese scenarios [49]. In mixed-context hallucination evaluation tasks, Qwen2.5-14B also demonstrates strong competitiveness in chain-of-thought reasoning settings, indicating good potential in tasks requiring multi-evidence reasoning for error discrimination [50]. These results indicate that the Qwen model family has strong competitiveness in related open-source hallucination detection and evaluation tasks.

Furthermore, LLM-as-a-judge research shows that high-quality open-source evaluation models have achieved usability in high-risk scenarios, and even task-specific aligned open-source evaluation models can surpass some closed-source models [51, 52]. While systematic hallucination detection evaluation specifically for Qwen 3 remains limited, the performance of Qwen2.5 series on relevant benchmarks provides indirect evidence for selecting Qwen 3 14b; our final adoption of Qwen 3 14b as the core model for the complete local detection solution is further based on comprehensive consideration of our 8b/14b comparison results under unified structured output framework, fine-tuning performance, and deployment constraints.

Beyond the main 14b experiment, we also conducted exploratory fine-tuning trials on Qwen 3 8b under the same MS-SWIFT LoRA training framework. The 8b track not only reused LoRA training settings similar to the 14b main experiment but also tested multiple hyperparameter schemes tailored for small model capacity, including conservative optimization groups, more aggressive regularization groups, and data partition adjustment groups; representative configurations of the conservative optimization group include learning rate 2e-5, LoRA rank 8, and LoRA alpha 16. Comparison between 8b and 14b was completed under the same structured output pipeline: detection agents unified organized output patterns through LangChain's structured output interface, and results subsequently entered JSON parsing and repair, Pydantic type validation, three-layer verification, and inconsistency recheck workflows, with local models additionally incorporating JSON prefix constraints and other generation-side stabilization strategies [36, 44]. Related results and engineering differences are reported in Section 5.

In VRAM analysis, we estimate model weight VRAM by combining parameter count and numerical precision. The Qwen3 technical report indicates that the Qwen3 series contains multiple dense models, with model scales relevant to this work including Qwen 3 8b, Qwen 3 14b, and Qwen 3 32b [53]. For such dense Transformer models, considering only model weights themselves, each parameter typically occupies 2 bytes in FP16/BF16 settings; this estimation approach is supported by mixed-precision training and large language model VRAM modeling research [54, 55, 56]. Therefore, the theoretical weight VRAM for Qwen 3 8b, Qwen 3 14b, and Qwen 3 32b are approximately 16 GB, 28 GB, and 64 GB respectively. It should be emphasized that these values correspond only to model weights themselves and do not include additional VRAM occupied during inference such as KV cache, activations, CUDA context, temporary buffers, and framework overhead, making actual deployment VRAM typically higher than the above theoretical values [55, 56]. Given that actual overhead exceeds theoretical estimates, we employ 8-bit quantization in local deployment to further compress runtime VRAM, enabling 14b models to complete inference on consumer-grade GPUs such as NVIDIA RTX 4090 (24GB VRAM). All models use unified inference configurations to ensure fair comparison.

## 5.3 Evaluation Metrics

### Primary Metrics

We use standard binary classification metrics to evaluate hallucination detection performance, including Precision, Recall, and F1 score. TP (True Positive) represents correctly detected hallucinations, FP (False Positive) represents false alarm hallucinations, and FN (False Negative) represents missed hallucinations.

### Stratified Metrics

Considering varying severity levels of medical hallucinations, we introduce stratified evaluation metrics:

**F1 (E3+E4)**: Comprehensive F1 score for all hallucinations with evidence not mentioned (E3) and those explicitly contradicting factual evidence (E4), serving as a supplementary metric covering broader hallucination scope to evaluate overall system detection capability.

**F1 (E4)**: F1 score for hallucinations at contradiction level (E4) only, the primary safety metric in this work, since E4-level hallucinations represent erroneous information identifiable through EHR factual evidence.

**Recall (E4)**: Recall for E4-level hallucinations, measuring the system's ability to detect safety-critical errors. In clinical applications, high recall is crucial, as missing dangerous errors could threaten patient safety.

Stratified metrics enable assessment of system performance across different risk-level hallucinations, providing guidance for clinical deployment strategies.

## 5.4 Experimental Results and Analysis

## 5.5 Main Experimental Results

Table 5 and Table 6 present model performance comparisons on 50 test patients for the primary safety result E4-level hallucinations and supplementary metric E3+E4 respectively.

<a id="tab:main-results-e4"></a>

| Model | F1 (E4) | E4 Recall | E4 Precision |
| --- | --- | --- | --- |
| Qwen 3 plus | 0.791 | 0.745 | 0.842 |
| Qwen 3 14b (base) | 0.554 | 0.430 | 0.779 |
| Fine-tuning (Original) | 0.803 | 0.748 | 0.867* |
| Fine-tuning (Curated) | 0.831* | 0.909* | 0.765 |

*Table 5. E4-level Hallucination Detection Performance (Safety-Critical Primary Result)*

<a id="tab:main-results-all"></a>

| Model | F1 (E3+E4) | Recall | Precision |
| --- | --- | --- | --- |
| Qwen 3 plus | 0.658 | 0.833 | 0.544 |
| Qwen 3 14b (base) | 0.777 | 0.749 | 0.808 |
| Fine-tuning (Original) | 0.753 | 0.841* | 0.681 |
| Fine-tuning (Curated) | 0.823* | 0.835 | 0.812* |

*Table 6. Overall Hallucination Detection Performance (E3+E4)-Supplementary Metric*

**Model Details:**

-   `Qwen 3 plus`: Qwen 3 plus API (baseline)

-   `Qwen 3 14b (base)`: Qwen 3 14b foundation model (not fine-tuned)

-   `Fine-tuning (Original)`: Fine-tuning using original data

-   `Fine-tuning (Curated)`: Fine-tuning using curated data ⭐ **Overall Best**

Experimental results reveal several key findings.

First, when measured by the primary safety metric E4, the fine-tuning (curated) model achieves the best performance with F1=0.831; on the supplementary E3+E4 metric, its comprehensive F1 also reaches 0.823, demonstrating the importance of high-quality training data.

Second, fine-tuning significantly improves E4 detection performance, elevating F1 from the base model's 0.554 to 0.831, a relative improvement of +50.0%, crucial for safety-critical medical error detection.

Furthermore, all models are tested on 50 patients to ensure evaluation consistency, with the best model achieving E4 recall=90.9% and precision=76.5%, demonstrating good precision-recall balance.

<a id="fig:performance-comparison"></a>

![Figure 4. Performance comparison of four model configurations under E4 primary result metrics. The fine-tuning (curated) model achieved the most balanced performance across F1, Recall, and Precision E4 metrics.](figures/figure_03.png)

*Figure 4. Performance comparison of four model configurations under E4 primary result metrics. The fine-tuning (curated) model achieved the most balanced performance across F1, Recall, and Precision E4 metrics.*

Figure 4 compares the three key metric performances of four model configurations under E4 primary results. The fine-tuning (curated) model achieves F1=0.831, recall=90.9%, and precision=76.5% in this evaluation, with overall best performance. While Qwen 3 plus exhibits higher precision (84.2%), its E4 recall is 74.5%; although fine-tuning (original) achieves precision of 86.7%, its recall drops to 74.8%. In contrast, the fine-tuning (curated) model achieves superior overall balance in safety-critical detection.

### Comparison with Reference Baselines

To make comparison closer to original literature settings, we retain two literature-style reference baselines: RAGTruth-style Structured EHR Baseline and QAGS-style Structured EHR Baseline. Both use the same 50 test patients as the main experiment (patient_201-250, total 1103 sentences for examination), employing Qwen 3 plus as the judge model. CuraView reports E4 and E3+E4 system-level evaluation results.

<a id="tab:baseline-comparison"></a>

| Method | Evaluation Setting | F1 | Recall | Precision |
| --- | --- | --- | --- | --- |
| CuraView | E4 (Safety-Critical) | **0.831** | **0.909** | **0.765** |
| CuraView | E3+E4 (Extended Evaluation) | **0.823** | 0.835 | **0.812** |
| RAGTruth-style Structured EHR Baseline | Literature-style Sentence-level Consistency | 0.639 | **0.839** | 0.516 |
| QAGS-style Structured EHR Baseline | Literature-style Sentence-level Consistency | 0.631 | **0.850** | 0.502 |

*Table 7. Comparison of CuraView and two literature-style reference baselines on 50 test patients (patient_201-250, total 1103 sentences for examination). For CuraView, E4 and E3+E4 system-level evaluation results are reported; for RAGTruth-style and QAGS-style, literature-style sentence-level consistency results are reported. Metric order is unified as F1, Recall, Precision.*

Table 7 shows that by overall performance, CuraView outperforms both literature-style reference baselines on both system-level evaluation results. Specifically, CuraView achieves F1=0.831, Recall=0.909, Precision=0.765 in safety-critical E4 evaluation; in evaluation covering E3+E4, it maintains F1=0.823, Recall=0.835, Precision=0.812. In contrast, while RAGTruth-style and QAGS-style achieve recalls of 0.839 and 0.850 respectively, their precisions are only 0.516 and 0.502, with final F1 scores of 0.639 and 0.631 respectively.

This comparison indicates that the two literature-style methods lean toward high-recall broad-spectrum screening, whereas CuraView achieves better precision-recall balance under patient-specific evidence chain constraints. Especially in E4 safety-critical evaluation, CuraView's F1 of 0.831 is notably higher than the two reference baselines' 0.639 and 0.631; even extending to E3+E4 evaluation, CuraView's F1 remains at 0.823, indicating its advantage is not limited to a single narrowly-defined evaluation standard but reflected in overall patient-level factual verification capability.

<a id="fig:baseline-comparison"></a>

![Figure 5. Comparison of CuraView and two literature-style reference baselines on 50 test patients (patient_201-250, total 1103 sentences for examination). The first two bar groups correspond to CuraView's F1, Recall, and Precision under E4 and E3+E4 evaluations, with the latter two bar groups corresponding to RAGTruth-style and QAGS-style baselines.](figures/figure_03b.png)

*Figure 5. Comparison of CuraView and two literature-style reference baselines on 50 test patients (patient_201-250, total 1103 sentences for examination). The first two bar groups present CuraView's F1, Recall, and Precision under E4 and E3+E4 evaluations, with the latter two bar groups presenting RAGTruth-style and QAGS-style literature-style reference results.*

Figure 5 further visualizes this difference. It can be seen that the two literature-style baselines are slightly higher in Recall but notably lower in Precision than CuraView, thus overall F1 is significantly reduced. For safety-critical scenarios, this difference is particularly important: if achieving only high recall while lacking sufficient precise patient-level conflict verification, the system more easily generates numerous false positives; CuraView's advantage manifests in maintaining high recall while leveraging structured patient evidence chains to significantly elevate Precision and final F1.

Furthermore, based on 250-case Qwen 3 plus experimental results, we examined the relationship between medical record character count and patient-level F1. Statistical results show no significant linear or monotonic correlation between them (Pearson r = 0.083, p = 0.1917; Spearman ρ = 0.002, p = 0.9804). Therefore, within the text length range covered by this experiment, we have not observed evidence of detection performance significantly declining with increasing medical record length, indicating overall stable performance of this method on medical records of varying lengths.

### Model Size Exploration: 8B vs 14B

Beyond the formal 50-patient main experiment, we also conducted small-scale exploratory trials on Qwen 3 8b and Qwen 3 14b following the same pipeline. Since both share the same training framework, task definition, data construction process, and structured output constraints, the comparison here focuses on end-to-end engineering usability rather than bare model capability differences under unconstrained generation.

The focus of this exploration is no longer on classification scores on a small number of successful samples, but on structured output stability truly required by end-to-end workflows. Under identical LangChain structured output and step-by-step JSON prompting, Qwen 3 8b (base) JSON format accuracy typically remains only around 40-50%, with field name correctness around 60%; this aligns with our practical observation that 8b frequently produces JSON parsing failures, missing fields, incorrect field names, or extra text when strict fixed JSON structure is required, preventing results from entering subsequent automated verification pipelines. Even after trying multiple hyperparameter groups on the 8b side, the most stable performing group did not fundamentally address this problem.

In contrast, 14B demonstrates higher structured output stability under the same LangChain pipeline. The empirical values provided in the repository inference guide are: 14B JSON format accuracy around 70-80%, field name correctness around 85%; furthermore, under small-sample debug settings employing LangChain structured output, step-by-step JSON prompting, and parsing validation, its JSON parsing success rate can reach 100%. Therefore, 14B not only notably outperforms 8B in the same pipeline comparison, but also more easily achieves stable usable engineering performance in the existing detection chain.

Thus, we treat this portion of results only as model size exploration, not incorporating it into formal primary results. After comprehensive hyperparameter experimentation, structured output performance, engineering usability, and hardware costs, we ultimately select 14B as the primary local model for this work: although 8B has lower resource consumption, it still struggles to reliably meet fixed JSON output requirements under the same LangChain structured output framework; 14B more easily achieves stable usability.

## 5.6 Ablation Studies

### Fine-tuning Impact

Table 8 presents model evolution and fine-tuning impact.

<a id="tab:ablation-finetuning"></a>

| Configuration | F1 (E3+E4) | F1 (E4) | Relative Change (Relative to Base Model) |
| --- | --- | --- | --- |
| Base Model | 0.777 | 0.554 | - |
| + Curated Fine-tuning | 0.823* | 0.831* | +5.9%* |
| + Original Data Fine-tuning | 0.753 | 0.803 | -3.1% |
| API Model | 0.658 | 0.791 | -15.3% |

*Table 8. Model Evolution and Fine-tuning Impact*

**Analysis:**

-   When measured by the core safety metric E4 of this research, curated fine-tuning significantly elevates F1 from 0.554 to 0.831, a relative improvement of **50.0%**; in contrast, on the supplementary E3+E4 metric covering all hallucinations, comprehensive F1 achieves a **5.9%** relative improvement.

-   E4-level detection significant improvement: **F1 0.554 → 0.831** (relative improvement +50.0%)

-   Original data fine-tuning reduced precision (68.1%), indicating importance of data quality

-   API model (Qwen 3 plus) shows unbalanced metrics: high recall (83.3%) but low precision (54.4%)

### Type-wise Fine-tuning Gain Analysis

To avoid underestimating high-baseline types with limited remaining improvement space in comparison, we conduct type-wise analysis on 50 test patients (patient_201-250), employing ceiling-corrected gain rate $\frac{F1_{\text{tuned}} - F1_{\text{base}}}{1 - F1_{\text{base}}} \times 100\%$ as the primary gain metric. This metric measures what proportion of "remaining improvable space" fine-tuning consumed. Training sample counts in the table indicate coverage scale of each type in the final training set.

<a id="tab:typewise-relative-gain"></a>

| Hallucination Type | Training Samples (Final Training Set Coverage Scale) | Base F1 | Tuned F1 | Absolute Gain | Ceiling-Corrected Gain Rate |
| --- | --- | --- | --- | --- | --- |
| Exam Result Error | 1692 | 0.081 | 0.482 | +0.401 | +43.6% |
| Medication Error | 939 | 0.381 | 0.594 | +0.213 | +34.4% |
| Numerical Error | 374 | 0.514 | 0.600 | +0.086 | +17.6% |
| Diagnosis Error | 334 | 0.095 | 0.278 | +0.183 | +20.2% |
| Negation Error | 305 | 0.109 | 0.154 | +0.045 | +5.0% |
| Temporal Error | 210 | 0.632 | 0.625 | -0.007 | -1.8% |
| Invented Fact | 188 | 0.058 | 0.111 | +0.053 | +5.6% |

*Table 9. Type-wise Fine-tuning Gain Analysis on 50 Test Patients (patient_201-250). Gain metric employs ceiling-corrected improvement rate; training sample count indicates coverage scale of each type in the final training set.*

Table 9 shows that when controlling for ceiling effects, types with larger training coverage scale generally achieve higher ceiling-corrected gains. Exam result error has the largest training coverage scale (1692) and also achieves the highest ceiling-corrected gain rate (43.6%); medication error with the second-highest sample count (939) achieves a gain rate of 34.4%. This result indicates that current fine-tuning data is effective in the type dimension, with more same-type training samples typically translating to stronger type discrimination ability. Meanwhile, temporal error and negation error types achieve gain rates of only -1.8% and 5.0%, indicating clear performance variation across types remains.

<a id="fig:typewise-relative-gain"></a>

![Figure 6. Type-wise results based on 50 test patients (patient_201-250). Horizontal axis represents coverage scale of each hallucination type in the final training set; vertical axis represents the percentage of remaining F1 space consumed by fine-tuning.](figures/figure_04a.png)

*Figure 6. Type-wise results based on 50 test patients (patient_201-250). Horizontal axis represents coverage scale of each hallucination type in the final training set; vertical axis represents the percentage of remaining F1 space consumed by fine-tuning.*

Figure 6 further supports this conclusion from an overall trend perspective: types with more training samples typically exhibit higher ceiling-corrected gains, indicating that this work's type-level fine-tuning is effective overall. While this relationship is not strictly linear and different types remain influenced by task difficulty and base model initial capability, this result provides clear direction for subsequent improvements. Future work could employ type-wise combined fine-tuning strategies, maintaining multi-type joint training while selectively supplementing dedicated samples and conducting additional fine-tuning for currently lower-gain or weaker-performing categories, thereby more specifically reducing performance gaps across different hallucination types.

### Domain Customization Impact

Table 10 presents key impacts of domain-customized prompts.

<a id="tab:ablation-domain"></a>

| Metric | Before | After | Improvement |
| --- | --- | --- | --- |
| Total Entities | 240 | 58* | ↓75.8% |
| LAB_TEST Entities | 35 | 6* | ↓82.9% |
| PATIENT Fragmentation | 3 | 1* | ↓66.7% |
| Entity Accuracy | 42% | 91%* | ↑116.7% |
| Graph Connectivity | 7 components | 1 component* | Fully Connected |
| F1 Score | 0.553 | 0.791* | ↑43.0% |

*Table 10. Domain Customization Impact*

## 5.7 Real LLM Output Hallucination Detection: Meditron-7B Case Study

To verify the applicability of CuraView in real-world scenarios, we applied the detection agent to patient discharge summaries generated from Meditron-7B. We selected this model because, on one hand, the MEDITRON series represents the open-source medical LLM pathway of continued pretraining on medical corpora [57], and on the other, the Discharge Me shared task has seen MEDISCHARGE, a discharge summary system based on Meditron-7B, demonstrating that this model family can be directly employed for Brief Hospital Course and Discharge Instructions generation [21]. Accordingly, we used Meditron-7B to generate discharge summaries for 25 MIMIC-IV patients, then applied CuraView's detection agent to perform hallucination detection on these generated texts.

### Detection Result Statistics

In 25 detection reports, the system analyzed 154 sentences and detected 45 hallucinations, with overall hallucination rate of 29.22%. This elevated hallucination rate indicates that even LLMs specifically fine-tuned for medical domains still face serious challenges with factual accuracy when generating clinical documents.

Figure 7 presents the distribution of detected hallucination types. Notably, "invented fact" dominates absolutely, accounting for 84.4% (38/45 hallucinations). This indicates that Meditron-7B tends to add information completely absent in the EHR during generation, rather than simply modifying existing facts. Other types include exam result error (6.7%), numerical error (4.4%), medication error (2.2%), and negation error (2.2%). Diagnosis error and temporal error did not appear in this batch.

This distribution has direct practical significance: in subsequent joint generation-detection training, we can prioritize targeted reinforcement on invented facts and small amounts of high-risk factual errors; and in clinical review processes with physician participation, "invented fact," exam result error, and medication error can be prioritized for manual review, improving human review efficiency.

<a id="fig:meditron-hallucination-distribution"></a>

![Figure 7. Distribution of hallucination types detected in discharge summaries generated by Meditron-7B (based on 25 patients, 154 sentences, 45 hallucinations). "Invented fact" dominates absolutely (84.4%), indicating LLMs tend to add non-existent information rather than modify existing facts.](figures/figure_05.png)

*Figure 7. Distribution of hallucination types detected in discharge summaries generated by Meditron-7B (based on 25 patients, 154 sentences, 45 hallucinations). "Invented fact" dominates absolutely (84.4%), indicating LLMs tend to add non-existent information rather than modify existing facts.*

### Key Findings

This case study reveals three important findings:

First, **heterogeneity of hallucination type distribution**. Unlike training data created by our hallucination generation agent (uniformly covering seven types), real LLM output exhibits strong type bias-"invented fact" far exceeds other types in proportion. This heterogeneity validates the necessity of our diversified hallucination generation framework, as relying solely on real LLM errors cannot obtain comprehensive type coverage. Simultaneously, this real error distribution also suggests that subsequent joint training should not merely pursue average coverage, but assign higher weight to high-frequency and clinically easily-overlooked types.

Second, **generalization capability of the detection agent**. Although the detection model was primarily trained on our generated hallucination data, it can effectively detect real Meditron-7B output, validating the robustness of the GraphRAG-enhanced verification approach. The system can distinguish EHR-supported statements from unsupported "invented facts," demonstrating the generality of the knowledge graph-based verification mechanism.

Finally, **risk assessment for clinical deployment**. The 29.22% hallucination rate far exceeds clinically acceptable thresholds (typically requiring <5%), highlighting the importance of rigorous hallucination detection before medical LLM deployment. CuraView can rapidly detect large volumes of patient reports in batch, providing a practical quality control tool for clinical applications.

## 5.8 Case Studies

### Case 1: Perfect Detection (Patient 201)

In this case, the original text was "Patient diagnosed with pneumonia prescribed azithromycin 500mg," modified to "Patient diagnosed with *tuberculosis* prescribed *clarithromycin 500mg*." The system correctly detected two hallucinations: the sentence "Patient diagnosed with tuberculosis" was marked as E4-level hallucination with conflicting evidence as "Diagnosis: J18.9 - Pneumonia"; the sentence "prescribed clarithromycin 500mg" was also marked as E4-level hallucination with conflicting evidence as "Medication: Azithromycin 500mg." The system correctly identified diagnosis error and medication error by matching against structured EHR records, with high confidence scores (0.95+) reflecting clear evidence conflicts. This case demonstrates CuraView's advantage in detecting safety-critical E4-level hallucinations with explicit EHR contradictions.

### Case 2: Partial Detection (Patient 205)

In this case, the original text was "Patient reports chest pain and shortness of breath. No cardiac disease history," modified to "Patient reports *severe* chest pain and shortness of breath. *Has history of myocardial infarction*." The sentence "Patient reports severe chest pain..." was not detected, a false negative, because the subjective modifier "severe" is difficult to verify. The sentence "Has history of myocardial infarction" was correctly detected as E4-level hallucination with conflicting evidence as "Cardiac history: No records." The system successfully detected the negation error (E4) but missed the subjective intensifying modifier. This result highlights a limitation: subjective modifiers ("severe," "mild," "moderate") are difficult to verify without quantitative clinical records; improvement requires better subjective terminology modeling.

### Case 3: False Positive (Patient 208, Precision Issue)

In this case, the original text was "Patient received intravenous fluid replacement for dehydration," rewritten (without hallucination) as "Patient received intravenous infusion for dehydration." The system marked the sentence "Patient received intravenous infusion..." as E3-level hallucination, a false positive, reasoning "No explicit record of intravenous fluid replacement in procedure records," when the actual reason was that the treatment was implied by discharge instructions but not separately recorded in structured fields. The false positive arose because intravenous fluid replacement is "implicit" rather than "explicit" recorded treatment. The system conservatively marked it as E3 (no supporting evidence) rather than E4 (conflicting evidence), reflecting appropriate uncertainty modeling. This case reveals a trade-off: strict verification enhances safety but may increase false positives for implicitly recorded treatments.

Based on in-depth insights and clinical significance analysis of the above experimental results, see Section 6.

# 6 Discussion

## 6.1 Key Insights and Clinical Significance

Our comprehensive evaluation of CuraView reveals several key insights in medical hallucination detection:

### Domain-specific Fine-tuning is Critical for Medical LLMs

The significant improvement from the base model (F1=0.554 on E4) to the fine-tuned model (F1=0.831 on E4) demonstrates that domain-specific fine-tuning is crucial for clinical deployment. For safety-critical E4-level hallucinations, this relative improvement of +50.0% is particularly significant. However, data quality is equally important: fine-tuning with curated data achieved a 9.3% relative improvement in E3+E4 F1 compared to original data fine-tuning, highlighting the importance of high-quality training data curation.

**Clinical Significance:** Medical institutions should invest in carefully curated medical training data rather than relying solely on general pre-trained models. Compared to the substantial performance gains in detecting safety-critical errors, the cost of data quality curation is justified.

### GraphRAG Provides Critical Context

Our ablation study demonstrates that domain-customized GraphRAG prompts can elevate F1 from 0.553 to 0.791, a relative improvement of 43.0%. The reduction in entity over-extraction (240 → 58 entities per patient) and improved graph connectivity (7 → 1 connected components) directly translate to better detection performance.

**Clinical Significance:** Effective medical AI requires structured, patient-specific knowledge representation. For clinical verification tasks requiring multi-hop reasoning over complex medical relationships, generic document retrieval is insufficient.

### Robustness to Medical Record Length

Record length varies substantially in real clinical deployment, so it is practically important to ask whether the method deteriorates as context grows. We tested the relationship between medical record length and patient-level F1 in an extended experiment on 250 Qwen 3 plus cases and found neither significant linear nor monotonic correlation (Pearson r = 0.083, p = 0.1917; Spearman ρ = 0.002, p = 0.9804). This suggests that, at least within the length range studied here, CuraView does not exhibit a clear degradation trend as records grow longer, strengthening the argument for deployability in real long-context verification settings.

### Precision-Recall Trade-off in Safety-Critical Scenarios

The API model (Qwen 3 plus) achieves high recall (83.3%) but lower precision (54.4%), resulting in substantial false positives. In contrast, when measured by safety-critical E4 results, our fine-tuned model achieves a better balance with recall of 90.9% and precision of 76.5%, corresponding to F1 of 0.831. In clinical deployment, false positives (marking correct statements as hallucinations) erode physician trust, while false negatives (missing dangerous errors) directly threaten patient safety.

**Clinical Significance:** The optimal operating point depends on deployment scenarios. For high-risk decisions (such as medication dosage, diagnosis), high recall should be prioritized even at the cost of precision; whereas in document review scenarios, balanced metrics can avoid alert fatigue.

## 6.2 Practical Deployment Considerations

### Cost-Performance Trade-off

There is a clear cost-performance trade-off in deployment approach selection. API models have higher costs (approximately $0.0392 per patient) but require no infrastructure investment, suitable for small-scale usage; local models have lower marginal costs but require GPU infrastructure. Although the CuraView framework design is in principle adaptable to other models, the complete local detection solution and primary fine-tuning achievements ultimately developed in this work were built upon Qwen 3 14b; related research also demonstrates that the Qwen family exhibits strong competitiveness in related open-source hallucination detection and evaluation tasks, consistent with our observations [49, 50, 51, 52]. Combined with the model size exploration results from Section 5, the 14b model exhibits higher end-to-end engineering usability under unified structured output constraints, thus becoming our practical compromise solution among resource costs and system stability. Implementation details regarding VRAM and quantization configuration are provided in Section 5.

### Structured Output Strategy Discussion

In structured output tasks, the distinction between prompt engineering and constraint-based generation has direct deployment implications. Progressive prompting and templated prompts can improve extraction quality, but are insufficient alone to guarantee output structure legality; in contrast, schema-based generation, validation, and automatic retry mechanisms more reliably support downstream verification and batch processing workflows [44, 45, 46, 47]. The unified structured output pipeline presented in Section 4 implements this approach for patient-level clinical document verification; the results show that model differences ultimately manifest as differences in end-to-end structured output usability rather than merely as differences in open-ended natural language understanding capability.

### Integration with Clinical Workflows

CuraView can be integrated into clinical workflows in three ways. Real-time detection mode integrates the system as an AI copilot into EHR systems (such as Epic, Cerner), providing immediate feedback as physicians document. Batch verification mode can be paired with discharge summary generation systems like Meditron-7B, such as MEDISCHARGE in the Discharge Me task [21], automatically performing hallucination detection on generated discharge summaries after nocturnal generation and flagging errors for morning review, achieving end-to-end automation from document generation to quality control. Combined with type biases exposed in the case study, clinical review can prioritize more common and higher-risk categories such as "invented facts," incorrect test results, and medication errors. Educational support mode treats detected hallucinations as teaching cases for medical students and residents, enhancing clinical documentation quality awareness.

The limitations and future improvement directions of this research are detailed in Section 8.

# 7 Conclusions

## 7.1 Summary of Contributions

This paper presents CuraView, an end-to-end multi-agent framework for sentence-level verification of clinical documents. The system organizes patient-level EHR evidence into a GraphRAG knowledge graph and combines evidence grading, structured-output validation, and a generation-detection loop to deliver interpretable and auditable medical hallucination detection. Experimental results show that the framework not only reduces safety-critical E4 errors effectively, but also produces reusable annotation and distillation resources that can serve as infrastructure for future medical LLM quality-control research.

## 7.2 Impact and Clinical Significance

CuraView addresses critical gaps in medical AI safety through the following aspects:

-   **Safety Protection Mechanism:** Detects 90.9% of safety-critical E4-level hallucinations, preventing potentially harmful medical errors

-   **Interpretable Verification:** Provides explanations based on evidence grading with citations to specific EHR records, enabling physicians to establish trust and perform verification

-   **Production-ready Deployment System:** Supports both API and local deployment with structured validation, facilitating integration into real clinical scenarios

-   **Open-Source Toolkit:** The released framework supports reproducible research and accelerates development in medical hallucination detection

## 7.3 Broader Significance

Beyond direct clinical applications, CuraView demonstrates broader principles for trustworthy medical AI. First, domain knowledge integration is critical; although general LLMs are powerful, domain-specific knowledge integration remains necessary in safety-critical applications, and our GraphRAG approach demonstrates that structured medical knowledge can significantly enhance LLM reliability. Second, interpretability is a necessary condition; in clinical environments, black-box AI decision-making is unacceptable, and explanation with evidence grades citing specific EHR records enables physicians to verify AI recommendations and establish trust and accountability mechanisms. Third, multi-agent collaboration shows that complex medical tasks benefit from specialized agents with complementary capabilities, and our adversarial generation-detection paradigm can extend to other medical AI applications. Finally, continuous evaluation is indispensable; medical AI systems must be continuously monitored and evaluated, and our framework provides infrastructure for performance tracking as clinical practice evolves.

## 7.4 Concluding Remarks

Medical AI safety is non-negotiable. This research demonstrates that integrating domain knowledge graphs with LLM reasoning can achieve high detection performance while providing interpretable evidence chains, offering a viable approach for safe deployment of medical LLMs.

Despite remaining limitations in data diversity, knowledge coverage, temporal reasoning, and real-world deployment, CuraView demonstrates the feasibility of turning patient-level evidence verification into an interpretable and operational system, while specific technical extensions are discussed in the limitations-and-future-work section.

As medical AI rapidly advances, **hallucination detection will become an essential component of clinical deployment**. We hope CuraView serves as a benchmark for the research community, advancing medical AI safety technology and ultimately serving patient health and well-being.

**"We trust AI, but we verify the evidence."** - CuraView Design Philosophy

# 8 Limitations

Although CuraView achieves significant results in medical hallucination detection, this research has the following limitations, which also point to future research directions.

## 8.1 Dataset and Generalization Limitations

**Single Data Source:** This research evaluates only on the MIMIC-IV dataset (a single medical center in the United States). Different medical institutions differ in clinical practice, documentation standards, and terminology usage, which may impact system generalization to other environments. Future validation on multi-center, multi-national datasets (such as eICU, UK Biobank, Chinese hospital data) is needed.

**Emergency Department Scenario Limitations:** The Discharge-Me used in this research is a discharge summary benchmark constructed from MIMIC-IV, with upstream tasks covering Brief Hospital Course and Discharge Instructions section generation [48, 6]. However, in the current experimental setup of this paper, formal hallucination generation and detection have focused only on brief_hospital_course, with discharge_instructions not yet included in primary evaluation. Therefore, other clinical document types such as inpatient records, outpatient notes, and surgical reports are not covered; even within the same benchmark, review capabilities for post-discharge instruction statements remain to be further enhanced through introducing external medical knowledge graphs, clinical guidelines, and pharmaceutical knowledge resources. This expansion direction has relevant literature support: recent medical GraphRAG work demonstrates that connecting user documents to trusted medical sources and incorporating graph retrieval can enhance evidence and credibility [30]; healthcare RAG systems reviews further indicate that external knowledge sources are important mechanisms for mitigating medical hallucinations and enhancing transparency [31]; and reviews on SNOMED CT and large language model integration also show that terminology and ontology knowledge can improve downstream medical task performance through retrieval or external knowledge injection [35]. Hallucination patterns may differ across document types and sections, requiring targeted adaptation.

**English Corpus Limitations:** The current system is trained and evaluated only on English clinical text. Differences in medical terminology expression across languages, handling of multilingual clinical documents, and cross-lingual knowledge graph construction remain issues to be addressed in future work.

## 8.2 Methodological Limitations

**Knowledge Graph Coverage:** GraphRAG indexing relies on information explicitly recorded in EHRs. For implicit medical knowledge (such as drug interactions, clinical guidelines, disease progression patterns) and external medical knowledge bases (such as UMLS, SNOMED-CT), the current system has not yet integrated. This limits detection capability for complex statements requiring inferential verification. Error analysis shows that synonym and abbreviation recognition issues are important sources of missed E4 hallucinations; for example, "adult-onset diabetes" and "type 2 diabetes" may be misclassified as different concepts. Integrating standardized medical terminology systems like UMLS could significantly improve this issue.

**Temporal Reasoning Capability:** Although GraphRAG can extract temporal information, the current system has limited capability in complex temporal reasoning. For example, verifying "patient developed complications on post-op day 3" requires understanding temporal sequence and causal relationships, exceeding the capability of current graph query mechanisms. Error analysis also indicates that temporal reasoning issues such as conflicts between medication discontinuation time and record timestamps are important causes of missed detections. Constructing temporal knowledge graphs with timestamped edges is an important future improvement direction.

**Missing Causal Reasoning:** The current system cannot distinguish "correlation" from "causality." For example, "eGFR improvement → medication discontinuation" represents clinical reasoning rather than direct evidence, but the system may mark it as hallucination. We observe in low-confidence and boundary cases that insufficient causal chain explanation repeatedly affects system judgment, indicating this is a key bottleneck affecting system performance. Introducing causal graphs, counterfactual reasoning mechanisms, and clinical guidelines are viable paths to address this limitation.

**LLM Dependency:** The hallucination detection agent relies on LLM reasoning capability. Even using GPT-4 or fine-tuned models, the LLM itself may produce reasoning errors or "second-order hallucinations" (introducing new errors during detection). We mitigate this through structured output validation and retry mechanisms, but cannot completely eliminate it.

## 8.3 Evaluation Limitations

**Limited Test Scale:** Main experiments conduct deep evaluation on 50 patients. While this is sufficient to establish performance benchmarks, larger-scale clinical trials (hundreds to thousands of patients) are necessary to validate system stability and consistency in production environments.

**Manual Annotation Cost:** Evidence grade annotation (E1-E4) ideally requires clinical expert review. In this work, we currently adopt a generation-stage structured-records-as-ground-truth strategy and observed approximately X% agreement with manual review on an independently sampled subset, providing preliminary support for this pipeline; however, boundary cases may still be affected by automated rules. Future work should incorporate manual double-blind review by clinicians to further validate the robustness of this labeling strategy on complex cases.

**Lack of Real-World Validation:** The system has not been deployed and tested in actual clinical workflows. The gap between laboratory settings and clinical practice (such as interface integration, response time requirements, physician acceptance) may impact real-world application effectiveness.

## 8.4 Computational Resource Limitations

**Hardware Requirements:** From theoretical estimation, Qwen 3 14b with FP16/BF16 model weights alone is approximately 28 GB, and actual inference VRAM would further increase due to KV cache, activation values, and other runtime overhead [53, 54, 55, 56]. Therefore, current local deployment still relies on 8-bit quantization and RTX 4090 (24GB) level GPUs for relatively stable operation. Future work could further explore INT4 quantization, model distillation, and other techniques to further reduce computational costs.

**API Costs:** For institutions choosing API deployment mode, the cost per patient detection is approximately $0.0392. While individual transaction costs are not high, in large-scale deployment scenarios (such as processing thousands of patients daily), cumulative costs cannot be ignored. Hybrid deployment strategies (batch processing using local models, real-time queries using APIs) can balance cost and flexibility.

**Processing Speed:** GraphRAG indexing and query construction and querying faces performance bottlenecks on large patient populations (tens of thousands of patients). The current system requires approximately 30 minutes to complete indexing on the full 250-patient experimental subset. While meeting experimental requirements, scaling to the complete MIMIC-IV dataset (46,998 patients) requires optimizing graph storage structures and query algorithms to improve efficiency.

## 8.5 Safety and Ethical Limitations

**Privacy Protection:** Although MIMIC-IV data is de-identified, knowledge graphs may indirectly expose patient information through entity associations. In real deployment, differential privacy and federated learning techniques must be implemented. Additionally, the system has not yet completed comprehensive HIPAA (United States) and GDPR (European Union) compliance verification, which is a necessary prerequisite for clinical deployment.

**Clinical Responsibility Definition:** As an auxiliary decision-support tool, system detection results should not replace physician clinical judgment. How to clarify responsibility boundaries between AI systems and clinical physicians and establish regulatory frameworks for medical AI are issues requiring policy-level solutions. Physicians may over-rely on the system and overlook missed cases, or may suffer alert fatigue from excessive false positives.

**False Negative Risk:** Hallucinations not detected by the system (false negatives) may lead to erroneous medical decisions. The best model achieves 90.9% E4 recall, meaning approximately 9.1% of safety-critical errors may still be missed. In clinical applications, multi-layer safety mechanisms must be established, including: mandatory manual review of low-confidence cases, explicit system limitation statements, continuous performance monitoring, and periodic re-evaluation.

## 8.6 Future Improvement Directions

To address these limitations, we plan the following improvement directions:

**Multi-center Validation:** Collaborate with multiple medical institutions to validate system generalization across different clinical scenarios, document types, and patient populations.

**External Knowledge Integration:** Integrate medical knowledge bases such as UMLS, SNOMED-CT, and medical guidelines into GraphRAG to enhance reasoning capability.

**Temporal and Causal Reasoning:** Extend knowledge graphs to support timestamped edges and causal relationships, enabling complex temporal reasoning.

**Ensemble Learning:** Combine predictions from multiple detection models through voting or stacking to enhance robustness.

**Active Learning:** Prioritize annotation of cases the system is uncertain about, iteratively improving detection performance.

**Deployment Optimization:** Model quantization, knowledge graph compression, incremental index updates to reduce computational costs and latency.

**Clinical Integration Pilot:** Collaborate with medical institutions to deploy pilots in real clinical workflows, collect physician feedback, and iteratively optimize.

Despite these limitations, CuraView still represents significant progress in medical hallucination detection, providing a viable technical pathway for safe deployment of medical LLMs.

# 9 Acknowledgments

This research has benefited from support and assistance from multiple sources, for which we express our sincere gratitude.

We thank the MIMIC-IV dataset development team and Beth Israel Deaconess Medical Center for providing high-quality de-identified clinical data resources to the research community. We thank the Microsoft GraphRAG team for open-sourcing a powerful knowledge graph construction framework, which provided the foundation for the core technology of this research.

We especially thank the reviewers for their valuable comments and constructive suggestions, which greatly improved the quality of the paper.

This research received computational resource support from Kyungpook National University.

**Corresponding Author:** YE SEVERIN (`6severin9@gmail.com`)

# Appendix

This appendix provides detailed experimental configurations, prompt templates, dataset construction descriptions, and reproducibility information to support verification and reproduction of the results presented in this paper.

## Appendix A: Experimental Setup

### A.1 Hardware and Software

All experiments were completed in a single-machine environment. Local inference primarily utilized a single NVIDIA RTX 4090 (24GB VRAM), while LoRA fine-tuning used a single NVIDIA H200. The server is equipped with an Intel Xeon Platinum 8358 (32 cores) and 256GB of memory, storage utilizing a 2TB NVMe SSD.

Software environment is as follows:

- Python 3.10.12
- PyTorch 2.1.0
- Transformers 4.36.0
- LangChain 1.0.0
- GraphRAG 0.2.1
- LanceDB 0.3.2

### A.2 Model Hyperparameters

**Qwen 3 14b LoRA Fine-tuning:**

- Learning rate: 2e-5
- Batch size: 8 (gradient accumulation steps = 4)
- Training epochs: 3
- Warmup steps: 100
- Maximum sequence length: 2048
- LoRA rank: 16
- LoRA alpha: 32

**Inference Parameters:**

- Temperature: 0.3 (detection), 0.7 (generation)
- top-p: 0.9
- Maximum output tokens: 512
- Stop sequences: `["\n\n\n"]`

## Appendix B: Prompt Templates

### B.1 Entity Extraction Prompt (Medical Customization)

We employ the following "protocol-based" instruction template to extract entities and relationships from patient EHR data for constructing patient-specific knowledge graphs.

**Instruction**

You are a medical knowledge graph extraction system. Please extract medical entities and relationships from the input EHR records and output as JSON.

**Constraints**

1. **Patient Entity Uniqueness**
     - Create and only create one `Patient` entity for the entire record.
     - Do not create `Patient_1`, `Patient_2`, or multiple patient entities.
     - All diagnoses, medications, and tests must be linked to this single `Patient`.

2. **Laboratory Test Normalization**
     - Consolidate individual indicators into test panels, for example:
         - CBC: WBC, RBC, HGB, HCT, PLT
         - Liver function: ALT, AST, ALK PHOS, BILIRUBIN
         - Kidney function: CREAT, UREA N, BUN
     - Do not create separate `LAB_TEST` entities for each indicator.
     - Create `LAB_RESULT` entities for specific values and link them to corresponding `LAB_TEST` entities through relationships.

3. **Language Consistency**
     - Entity names are unified in Chinese.
     - English is retained in the description field.
     - Example: `name="高脂血症"`, `description="HYPERLIPIDEMIA"`.

**Entity Types**

- PATIENT, DIAGNOSIS, MEDICATION, LAB_TEST, LAB_RESULT
- VITAL_SIGN, SYMPTOM, PROCEDURE, DEPARTMENT

**Relation Types**

- HAS_DIAGNOSIS, PRESCRIBED, SHOWS, UNDERWENT
- HAS_VITAL_SIGN, TESTED_BY, RESULT_OF, TREATED_IN

**Output Format**

Output JSON containing two arrays: `entities` and `relationships`:

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

**Why this design**

This template reduces entity over-fragmentation through "patient entity uniqueness" and "laboratory panel normalization" constraints, improving consistency in cross-table evidence alignment and providing more stable structured support for subsequent GraphRAG retrieval and fact verification.

### B.2 Hallucination Detection Prompt

We employ the following template to verify individual statements in discharge summaries: given a sentence and EHR evidence context retrieved from the knowledge graph, determine whether the sentence is hallucinated and output a structured explanation.

**Inputs**

- `sentence`: The sentence to be verified
- `evidence_context`: Retrieved EHR evidence context

**Task**

1. Determine whether the sentence is supported by evidence.
2. Identify any contradictory information.
3. Assign evidence grades:
     - E1: Supported by structured EHR fields
     - E2: Supported by unstructured text
     - E3: Evidence not mentioned, but should be flagged as problematic based on context
     - E4: Contradicts existing factual evidence

**Output Format**

Output JSON:

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

**Consistency Rule**

If `hallucination_detected = true`, then `evidence_grade` must be `E3` or `E4`.

## Appendix C: Error Analysis

Based on qualitative review of typical misclassification cases, the primary error patterns are as follows.

**False Negatives (Missed E4 Hallucinations)**

- Medical synonyms or abbreviations failed to correctly align with standard representations in the EHR.
- Statements requiring integration of clinical course across multiple time points were not consistently identified as contradictions.
- Generated sentences rely on implicit clinical meaning rather than explicit documentation in the EHR.
- Graph retrieval failed to return key evidence sufficient to support discrimination.

**False Positives (Correct Statements Flagged)**

- Generated text made conservative extrapolation from existing hints in the medical record, not explicitly recorded verbatim in the source.
- Semantically equivalent expressions were not fully aligned at the character string level.
- Temporal ranges or event sequencing expressions contained ambiguities.
- Entity or relationship errors from the graph extraction phase propagated to the final determination.

## Appendix D: Dataset Details

### D.1 Source Tables

We constructed experimental data from multi-table fields of Discharge-Me / MIMIC-IV. The "table-level record scale" shown below reflects the scale of the complete original table view, used to illustrate the data source; this scale is not equivalent to the experimental directory scale after splitting into train, valid, test_phase_1, test_phase_2, nor should it be directly interpreted as the actual scale of the 250-patient experimental subset in this paper.

**Diagnosis Table (diagnosis.csv)**

- Scale: 143,285 diagnosis records (original table view)
- Key fields: `subject_id`, `stay_id`, `icd_code`, `icd_version`, `icd_title`
- Example: `10000032`, `J18.9`, `ICD-10`, "Pneumonia with unspecified pathogen"

**ED Stays and Triage Tables (edstays.csv / triage.csv)**

- Purpose: Provide emergency department visit, triage, and vital sign information
- Key fields (identifiers and timestamps): `subject_id`, `stay_id`, `intime`, `outtime`
- Key fields (vital signs): `temperature`, `heartrate`, `resprate`, `o2sat`, `sbp`, `dbp`, `pain`, `acuity`

**Discharge Target Table (discharge_target.csv)**

- Purpose: Provide `brief_hospital_course` and `discharge_instructions` and other target section text
- Key fields: `subject_id`, `note_id`, `brief_hospital_course`, `discharge_instructions`
- Description: One of the core text sources for generation and verification tasks

**Radiology Table (radiology.csv)**

- Purpose: Provide supplementary radiology text evidence
- Key fields: `subject_id`, `stay_id`, `text`, `charttime`
- Description: Provides supplementary evidence for imaging-related fact verification

### D.2 Data Preprocessing

We employ the following preprocessing pipeline to organize multi-source table fields into a format compatible with GraphRAG:

1. **Multi-table join**: Integrate diagnosis, discharge, discharge_target, edstays, radiology, and triage from six sources on `subject_id` and `stay_id`.
2. **Deduplication**: Remove duplicate stay records (348 cases).
3. **Missing value handling**:
     - Delete records with missing discharge summaries (1,203 cases).
     - Standardize missing vital sign fields in triage.
4. **Text cleaning**:
     - Remove PHI markers (e.g., `[* * ... * *]`).
     - Normalize whitespace characters.
     - Correct common spelling errors.
5. **Format conversion**: CSV → JSONL for compatibility with GraphRAG.

## Appendix E: Reproducibility Checklist

- Code Availability: Project code is planned for release at https://github.com/[username]/CuraView
- Data Access: MIMIC-IV (requires PhysioNet credentials for access)
- Model Checkpoints: HuggingFace Hub `[username]/curaview-qwen3-14b`
- Training Configuration: See Appendix A.2
- Random Seed: All experiments fixed at 42
- Hardware: LoRA fine-tuning used a single NVIDIA H200; local inference used a single RTX 4090 (24GB)
- Training Time: Approximately 48 hours (LoRA fine-tuning)
- Dependencies: Repository `requirements.txt`

# References

[1] Singhal, Karan, Shekoofeh Azizi, Tao Tu, S Sara Mahdavi, Jason Wei, Hyung Won Chung, Nathan Scales, et al. 2023. "Large Language Models Encode Clinical Knowledge." *Nature* 620 (7972): 172--80. <https://doi.org/10.1038/s41586-023-06291-2>.

[2] Singhal, Karan, Tao Tu, Juraj Gottweis, Rory Sayres, Ellery Wulczyn, Le Hou, Kevin Clark, et al. 2023. "Towards Expert-Level Medical Question Answering with Large Language Models." *arXiv Preprint arXiv:2305.09617*. <https://arxiv.org/abs/2305.09617>.

[3] Nori, Harsha, Nicholas King, Scott Mayer McKinney, Dean Carignan, and Eric Horvitz. 2023. "Capabilities of GPT-4 on Medical Challenge Problems." *arXiv Preprint arXiv:2303.13375*. <https://arxiv.org/abs/2303.13375>.

[4] Lee, Peter, Sebastien Bubeck, and Joseph Petro. 2023a. "Benefits, Limits, and Risks of GPT-4 as an AI Chatbot for Medicine." *New England Journal of Medicine* 388 (13): 1233--39. <https://doi.org/10.1056/NEJMsr2214184>.

[5] Thirunavukarasu, Arun James, Darren Shu Jeng Ting, Kabilan Elangovan, Laura Gutierrez, Ting Fang Tan, and Daniel Shu Wei Ting. 2023. "Large Language Models in Medicine." *Nature Medicine* 29 (8): 1930--40. <https://doi.org/10.1038/s41591-023-02448-8>.

[6] Xu, Justin, Zhihong Chen, Andrew Johnston, Louis Blankemeier, Maya Varma, Jason Hom, William J. Collins, Ankit Modi, Robert Lloyd, Benjamin Hopkins, Curtis Langlotz, and Jean-Benoit Delbrouck. 2024. "Overview of the First Shared Task on Clinical Text Generation: RRG24 and \"Discharge Me!\"" In *Proceedings of the 23rd Workshop on Biomedical Natural Language Processing*, 85--98. Bangkok, Thailand: Association for Computational Linguistics. <https://doi.org/10.18653/v1/2024.bionlp-1.7>.

[7] MarketsandMarkets. 2025. "Artificial Intelligence (AI) in Healthcare Market - Global Forecast to 2030." MarketsandMarkets Research Private Ltd. <https://www.marketsandmarkets.com/Market-Reports/artificial-intelligence-healthcare-market-54679303.html>.

[8] Sinsky, Christine, Lacey Colligan, Ling Li, Mirela Prgomet, Sam Reynolds, Lindsey Goeders, Johanna Westbrook, Michael Tutty, and George Blike. 2016. "Allocation of Physician Time in Ambulatory Practice: A Time and Motion Study in 4 Specialties." *Annals of Internal Medicine* 165 (11): 753--60. <https://doi.org/10.7326/M16-0961>.

[9] Zhao, Jungang, Hanxiang Liu, Yaolong Chen, and Fujian Song. 2025. "Application of Artificial Intelligence Tools and Clinical Documentation Burden: A Systematic Review and Meta-analysis." *BMC Medical Informatics and Decision Making* 26: 29. <https://pmc.ncbi.nlm.nih.gov/articles/PMC12836966/>.

[10] Alkaissi, Hussam, and Samy I McFarlane. 2023. "Artificial Hallucinations in ChatGPT: Implications in Scientific Writing." *Cureus* 15 (2): e35179. <https://doi.org/10.7759/cureus.35179>.

[11] Rajpurkar, Pranav, Emma Chen, Oishi Banerjee, and Eric J Topol. 2022. "AI in Health and Medicine." *Nature Medicine* 28 (1): 31--38. <https://doi.org/10.1038/s41591-021-01614-0>.

[12] Pal, Ankit, Logesh Kumar Umapathi, and Malaikannan Sankarasubbu. 2023. "Med-HALT: Medical Domain Hallucination Test for Large Language Models." In *Proceedings of the 27th Conference on Computational Natural Language Learning (CoNLL)*, 314--334. Singapore: Association for Computational Linguistics. <https://aclanthology.org/2023.conll-1.21/>.

[13] Rotmensch, Maya, Yoni Halpern, Abdulhakim Tlimat, Steven Horng, and David Sontag. 2017. "Learning a Health Knowledge Graph from Electronic Medical Records." *Scientific Reports* 7 (1): 5994. <https://doi.org/10.1038/s41598-017-05778-z>.

[14] Finlayson, Samuel G, Paea LePendu, and Nigam H Shah. 2014. "Building the Graph of Medicine from Millions of Clinical Narratives." *Scientific Data* 1: 140032. <https://doi.org/10.1038/sdata.2014.32>.

[15] Tonekaboni, Sana, Shalmali Joshi, Melissa D McCradden, and Anna Goldenberg. 2019. "What Clinicians Want: Contextualizing Explainable Machine Learning for Clinical End Use." In *Proceedings of the 4th Machine Learning for Healthcare Conference*, 359--380. PMLR 106. <https://proceedings.mlr.press/v106/tonekaboni19a.html>.

[16] Asgari, Elham, Nina Montaña-Brown, Magda Dubois, Saleh Khalil, Jasmine Balloch, Joshua Au Yeung, and Dominic Pimenta. 2025. "A Framework to Assess Clinical Safety and Hallucination Rates of LLMs for Medical Text Summarisation." *NPJ Digital Medicine* 8: 274. <https://doi.org/10.1038/s41746-025-01670-7>.

[17] Williams, Christopher Y. K., Charumathi Raghu Subramanian, Syed Salman Ali, et al. 2025. "Physician- and Large Language Model-Generated Hospital Discharge Summaries." *JAMA Internal Medicine* 185 (7): 818--825. <https://jamanetwork.com/journals/jamainternalmedicine/fullarticle/2833228>.

[18] Toma, Augustin, Patrick R Lawler, Jimmy Ba, Rahul G Krishnan, Barry B Rubin, and Bo Wang. 2023. "Clinical Camel: An Open Expert-Level Medical Language Model with Dialogue-Based Knowledge Encoding." *arXiv Preprint arXiv:2305.12031*. <https://arxiv.org/abs/2305.12031>.

[19] Wu, Chaoyi, Xiaoman Zhang, Xin Zhang, Ya Wang, and Weidi Xie. 2023. "PMC-LLaMA: Towards Building Open-Source Language Models for Medicine." *arXiv Preprint arXiv:2304.14454*. <https://arxiv.org/abs/2304.14454>.

[20] Ji, Ziwei, Nayeon Lee, Rita Frieske, Tiezheng Yu, Dan Su, Yan Xu, Etsuko Ishii, Ye Jin Bang, Andrea Madotto, and Pascale Fung. 2023. "Survey of Hallucination in Natural Language Generation." *ACM Computing Surveys* 55 (12): 1--38. <https://doi.org/10.1145/3571730>.

[21] Wu, Haotian, Paul Boulenger, Antonin Faure, Berta Céspedes, Farouk Boukil, Nastasia Morel, Zeming Chen, and Antoine Bosselut. 2024. "EPFL-MAKE at \"Discharge Me!\": An LLM System for Automatically Generating Discharge Summaries of Clinical Electronic Health Record." In *Proceedings of the 23rd Workshop on Biomedical Natural Language Processing*, 696--711. Bangkok, Thailand: Association for Computational Linguistics. <https://doi.org/10.18653/v1/2024.bionlp-1.61>.

[22] Lyu, Mengxian, Cheng Peng, Daniel Paredes, Ziyi Chen, Aokun Chen, Jiang Bian, and Yonghui Wu. 2024. "UF-HOBI at \"Discharge Me!\": A Hybrid Solution for Discharge Summary Generation Through Prompt-based Tuning of GatorTronGPT Models." *arXiv Preprint arXiv:2407.15359*. <https://arxiv.org/abs/2407.15359>.

[23] Artsi, Yaara, Eyal Klang, Jeremy D. Collins, Benjamin S. Glicksberg, Girish N. Nadkarni, Panagiotis Korfiatis, and Vera Sorin. 2025. "Large Language Models in Radiology Reporting: A Systematic Review of Performance, Limitations, and Clinical Implications." *Intelligence-Based Medicine* 12: 100287. <https://doi.org/10.1016/j.ibmed.2025.100287>.

[24] Zhang, Serena, Sraavya Sambara, Oishi Banerjee, Julian Acosta, L. John Fahrner, and Pranav Rajpurkar. 2024. "RadFlag: A Black-Box Hallucination Detection Method for Medical Vision Language Models." *arXiv Preprint arXiv:2411.00299*. <https://arxiv.org/abs/2411.00299>.

[25] Lewis, Patrick, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, et al. 2020. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." *Advances in Neural Information Processing Systems* 33: 9459--74. <https://arxiv.org/abs/2005.11401>.

[26] Gao, Luyu, Zhuyun Dai, Panupong Pasupat, Anthony Chen, Arun Tejasvi Chaganty, Yicheng Fan, Vincent Y. Zhao, Ni Lao, Hongrae Lee, Da-Cheng Juan, and Kelvin Guu. 2023. "RARR: Researching and Revising What Language Models Say, Using Language Models." In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, 16477--16508. <https://doi.org/10.18653/v1/2023.acl-long.910>.

[27] Xiong, Guangzhi, Qiao Jin, Zhiyong Lu, and Aidong Zhang. 2024. "Benchmarking Retrieval-Augmented Generation for Medicine." *arXiv Preprint arXiv:2402.13178*. <https://arxiv.org/abs/2402.13178>.

[28] Wang, Chengrui, Qingqing Long, Meng Xiao, Xunxin Cai, Chengjun Wu, Zhen Meng, Xuezhi Wang, and Yuanchun Zhou. 2024. "BioRAG: A RAG-LLM Framework for Biological Question Reasoning." *arXiv Preprint arXiv:2408.01107*. <https://arxiv.org/abs/2408.01107>.

[29] Edge, Darren, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, and Jonathan Larson. 2024. "From Local to Global: A Graph RAG Approach to Query-Focused Summarization." *arXiv Preprint arXiv:2404.16130*. <https://arxiv.org/abs/2404.16130>.

[30] Wu, Junde, Jiayuan Zhu, Yunli Qi, Jingkun Chen, Min Xu, Filippo Menolascina, Yueming Jin, and Vicente Grau. 2025. "Medical Graph RAG: Evidence-based Medical Large Language Model via Graph Retrieval-Augmented Generation." In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, 28443--28467. <https://doi.org/10.18653/v1/2025.acl-long.1381>.

[31] Amugongo, Lameck Mbangula, Pietro Mascheroni, Steven Brooks, Stefan Doering, and Jan Seidel. 2025. "Retrieval Augmented Generation for Large Language Models in Healthcare: A Systematic Review." *PLOS Digital Health* 4 (6): e0000877. <https://doi.org/10.1371/journal.pdig.0000877>.

[32] Bodenreider, Olivier. 2004. "The Unified Medical Language System (UMLS): Integrating Biomedical Terminology." *Nucleic Acids Research* 32 (suppl_1): D267--70. <https://doi.org/10.1093/nar/gkh061>.

[33] Donnelly, Kevin. 2006. "SNOMED-CT: The Advanced Terminology and Coding System for eHealth." *Studies in Health Technology and Informatics* 121: 279--90. <https://pubmed.ncbi.nlm.nih.gov/17095826/>.

[34] World Health Organization. 2016. "International Statistical Classification of Diseases and Related Health Problems 10th Revision." *World Health Organization*. <https://icd.who.int/browse10/2016/en>.

[35] Chang, Eunsuk, and Sumi Sung. 2024. "Use of SNOMED CT in Large Language Models: Scoping Review." *JMIR Medical Informatics* 12: e62924. <https://doi.org/10.2196/62924>.

[36] Chase, Harrison. 2023. "LangChain: Building Applications with LLMs Through Composability." <https://github.com/langchain-ai/langchain>.

[37] Significant Gravitas. 2023. "AutoGPT: An Experimental Open-Source Attempt to Make GPT-4 Fully Autonomous." <https://github.com/Significant-Gravitas/AutoGPT>.

[38] Yao, Shunyu, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao. 2023. "ReAct: Synergizing Reasoning and Acting in Language Models." *arXiv Preprint arXiv:2210.03629*. <https://arxiv.org/abs/2210.03629>.

[39] Liu, Weiwen, Xu Huang, Xingshan Zeng, Xinlong Hao, Shuai Yu, Dexun Li, Shuai Wang, Weinan Gan, Zhengying Liu, Yuanqing Yu, Zezhong Wang, Yuxian Wang, Wu Ning, Yutai Hou, Bin Wang, Chuhan Wu, Xinzhi Wang, Yong Liu, Yasheng Wang, Duyu Tang, Dandan Tu, Lifeng Shang, Xin Jiang, Ruiming Tang, Defu Lian, Qun Liu, and Enhong Chen. 2025. "ToolACE: Winning the Points of LLM Function Calling." *arXiv Preprint arXiv:2409.00920*. <https://arxiv.org/abs/2409.00920>.

[40] Prabhakar, Akshara, Zuxin Liu, Weiran Yao, Jianguo Zhang, Ming Zhu, Shiyu Wang, Zhiwei Liu, Tulika Awalgaonkar, Haolin Chen, Thai Hoang, Juan Carlos Niebles, Shelby Heinecke, Huan Wang, Silvio Savarese, and Caiming Xiong. 2025. "APIGen-MT: Agentic Pipeline for Multi-Turn Data Generation via Simulated Agent-Human Interplay." *arXiv Preprint arXiv:2504.03601*. <https://arxiv.org/abs/2504.03601>.

[41] Zhang, Shaokun, Yi Dong, Jieyu Zhang, Jan Kautz, Bryan Catanzaro, Andrew Tao, Qingyun Wu, Zhiding Yu, and Guilin Liu. 2025. "Nemotron-Research-Tool-N1: Exploring Tool-Using Language Models with Reinforced Reasoning." *arXiv Preprint arXiv:2505.00024*. <https://arxiv.org/abs/2505.00024>.

[42] Tang, Xiangru, Anni Zou, Zhuosheng Zhang, Ziming Li, Yilun Zhao, Xingyao Zhang, Arman Cohan, and Mark Gerstein. 2023. "MedAgents: Large Language Models as Collaborators for Zero-shot Medical Reasoning." *arXiv Preprint arXiv:2311.10537*. <https://arxiv.org/abs/2311.10537>.

[43] Frohmann, Markus, Igor Sterner, Ivan Vulić, Benjamin Minixhofer, and Markus Schedl. 2024. "Segment Any Text: A Universal Approach for Robust, Efficient and Adaptable Sentence Segmentation." In *Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing*, 11908--41. Miami, Florida, USA: Association for Computational Linguistics. <https://aclanthology.org/2024.emnlp-main.665>.

[44] LangChain. 2024. "Structured Output." LangChain Documentation. <https://docs.langchain.com/oss/python/langchain/structured-output>.

[45] Liu, Yu, Duantengchuan Li, Kaili Wang, Zhuoran Xiong, Fobo Shi, Jian Wang, Bing Li, and Bo Hang. 2024. "Are LLMs Good at Structured Outputs? A Benchmark for Evaluating Structured Output Capabilities in LLMs." *Information Processing & Management* 61 (5): 103809. <https://doi.org/10.1016/j.ipm.2024.103809>.

[46] Lu, Yaxi, Haolun Li, Xin Cong, Zhong Zhang, Yesai Wu, Yankai Lin, Zhiyuan Liu, Fangming Liu, and Maosong Sun. 2025. "Learning to Generate Structured Output with Schema Reinforcement Learning." In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, 4905--4918. <https://doi.org/10.18653/v1/2025.acl-long.243>.

[47] Geng, Saibo, Martin Josifoski, Maxime Peyrard, and Robert West. 2023. "Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning." In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*, 10932--10952. <https://doi.org/10.18653/v1/2023.emnlp-main.674>.

[48] Stanford AIMI. 2024. "Discharge Me!" Stanford Center for Artificial Intelligence in Medicine and Imaging. <https://stanford-aimi.github.io/discharge-me/>.

[49] Jiang, Zhouyu, Mengshu Sun, Zhiqiang Zhang, and Lei Liang. 2025. "Bi'an: A Bilingual Benchmark and Model for Hallucination Detection in Retrieval-Augmented Generation." *arXiv Preprint arXiv:2502.19209*. <https://arxiv.org/abs/2502.19209>.

[50] Qi, Siya, Rui Cao, Yulan He, and Zheng Yuan. 2025. "Evaluating LLMs' Assessment of Mixed-Context Hallucination Through the Lens of Summarization." In *Findings of the Association for Computational Linguistics: ACL 2025*, 16480--16503. Vienna, Austria: Association for Computational Linguistics. <https://doi.org/10.18653/v1/2025.findings-acl.847>.

[51] Croxford, Emily, et al. 2025. "Evaluating Clinical AI Summaries with Large Language Models as Judges." *NPJ Digital Medicine* 8 (1): 640. <https://doi.org/10.1038/s41746-025-02005-2>.

[52] Ravi, Selvan Sunitha, Bartosz Mielczarek, Anand Kannappan, Douwe Kiela, and Rebecca Qian. 2024. "Lynx: An Open Source Hallucination Evaluation Model." *arXiv Preprint arXiv:2407.08488*. <https://arxiv.org/abs/2407.08488>.

[53] Yang, An, Anfeng Li, Baosong Yang, Beichen Zhang, Binyuan Hui, et al. 2025. "Qwen3 Technical Report." *arXiv Preprint arXiv:2505.09388*. <https://arxiv.org/abs/2505.09388>.

[54] Micikevicius, Paulius, Sharan Narang, Jonah Alben, Gregory Diamos, Erich Elsen, David Garcia, Boris Ginsburg, Michael Houston, Oleksii Kuchaiev, Ganesh Venkatesh, and Hao Wu. 2018. "Mixed Precision Training." *arXiv Preprint arXiv:1710.03740*. <https://arxiv.org/abs/1710.03740>.

[55] Fujii, Kento, Satoshi Tamaki, Yusuke Kuroda, Ryota Shingaki, and Yutaka Kanemasa. 2024. "Accelerating Large Language Model Training with 4D Parallelism and Memory Consumption Estimator." *arXiv Preprint arXiv:2411.06465*. <https://arxiv.org/abs/2411.06465>.

[56] Kim, Junyeob, Junho Kim, Hwanju Kim, and Jangwoo Kim. 2024. "LLMem: Estimating GPU Memory Usage for Fine-Tuning Pre-Trained LLMs." *arXiv Preprint arXiv:2404.10933*. <https://arxiv.org/abs/2404.10933>.

[57] Chen, Zeming, Alejandro Hernández-Cano, Angelika Romanou, Antoine Bonnet, Kyle Matoba, Francesco Salvi, Matteo Pagliardini, et al. 2023. "MEDITRON-70B: Scaling Medical Pretraining for Large Language Models." *arXiv Preprint arXiv:2311.16079*. <https://arxiv.org/abs/2311.16079>.
