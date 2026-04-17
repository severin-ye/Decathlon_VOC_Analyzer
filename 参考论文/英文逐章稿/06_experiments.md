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