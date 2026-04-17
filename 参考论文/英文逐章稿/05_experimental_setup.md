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