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