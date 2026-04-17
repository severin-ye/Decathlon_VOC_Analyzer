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