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