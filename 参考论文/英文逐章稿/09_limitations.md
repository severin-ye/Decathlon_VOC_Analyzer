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