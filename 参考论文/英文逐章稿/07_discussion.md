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