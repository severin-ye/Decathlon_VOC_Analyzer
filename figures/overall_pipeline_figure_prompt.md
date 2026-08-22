# Overall Pipeline Figure Prompt

Reference style: use the overall project flowchart style from `C:\Users\6seve\Codelib-severin\1_Research\CuraView\论文\figures\01_系统总流程图.pdf`. That reference is the CuraView total project pipeline figure: a wide landscape architecture diagram with numbered layer labels on the left, a large central left-to-right pipeline, a right-side dashed feedback/improvement loop, and a compact bottom legend.

Use this prompt to generate the image:

```text
Create a publication-quality, vector-style architecture diagram for a research paper.

Title: "Decathlon VOC Analyzer: Evidence-Driven Multimodal VOC Analysis Pipeline"

Canvas and style:
- Wide landscape layout, approximately 16:9 or 2:1 aspect ratio, white background.
- Follow the visual grammar of the CuraView overall flowchart: numbered layer panels on the far left, color-coded horizontal layers in the center, a dashed feedback/evaluation loop on the right, and a compact legend along the bottom.
- Use clean academic diagram styling: thin black outlines, rounded rectangles with small radius, crisp arrows, restrained colors, no gradients, no shadows, no 3D effects, no decorative backgrounds.
- Use simple black line icons where helpful: product box, review speech bubble, image frame, document, magnifying glass, vector index, reranker sliders, report page, citation link, chart, feedback loop.
- Make all text readable at paper size. Use short labels inside boxes and avoid long paragraphs.
- Use consistent typography, bold section headers, and enough spacing so arrows and labels never overlap.

Overall layout:
- Left column: four large numbered layer labels, stacked vertically.
- Center: the main system pipeline, flowing from top to bottom and left to right inside each layer.
- Right column: a dashed vertical box named "Evaluation, Feedback, and Experiment Loop" with arrows back to earlier stages.
- Bottom: a legend explaining node colors, evidence routes, and arrow styles.

Layer 1 label on the left:
"1 Product Evidence Acquisition Layer"
Subtitle: "(Raw Product, Reviews, Images)"

Layer 1 central content:
- A large blue-outlined container labeled "Raw Product Folder".
- Inside it, show three input groups:
  1. `product.json`: product name, model description, category, variants.
  2. `reviews.json`: user reviews, star ratings, language hints.
  3. `images/`: product images by variant.
- Show small chips for "product text", "product images", "image regions", and "user reviews".
- Output arrow downward to Layer 2 labeled "normalize to traceable evidence objects".

Layer 2 label on the left:
"2 Evidence Standardization and VOC Demand Modeling Layer"
Subtitle: "(ProductEvidencePackage + ReviewAspect)"

Layer 2 central content:
Use a green-outlined container with two parallel tracks that merge:

Track A: Product evidence standardization
- Box: "ProductEvidencePackage"
- Under it, four small object cards:
  - "TextEvidence: title, description, category"
  - "ImageEvidence: full product images"
  - "ImageRegion: center, upper, lower, left, right focus"
  - "ReviewRecord: stable review IDs"
- Add note: "stable SHA1-based evidence IDs, source fields, language tags".

Track B: VOC demand modeling
- Box sequence:
  "Rating-aware sampling" -> "Low-information review filtering" -> "Aspect extraction" -> "Deduplication"
- Use small labels:
  - "problem_first profile"
  - "LLM or heuristic fallback"
  - "aspect, sentiment, opinion, evidence span, usage scene, confidence"
- Merge Track A and Track B into an output card labeled "Traceable VOC units".

Output arrow downward to Layer 3 labeled "convert VOC aspects into evidence-seeking questions".

Layer 3 label on the left:
"3 Question-Guided Multimodal Retrieval Layer"
Subtitle: "(Text/Image/Mixed Evidence Search)"

Layer 3 central content:
Use an orange-outlined container with a left-to-right retrieval pipeline:
1. "Question Planning"
   - Inputs: ReviewAspect objects.
   - Show five intent chips: `explicit_support`, `visual_confirmation`, `cross_modal_resolution`, `spec_check`, `visual_detail`.
   - Show route chips: `text`, `image`, `mixed`.
2. "Multimodal Indexing"
   - Text route: product title, description, category -> text embeddings.
   - Image route: full images and regions -> CLIP or visual embeddings.
   - Backends: local JSON index and Qdrant.
3. "Candidate Recall"
   - Oversampling per route.
   - Language-balanced candidate pool.
4. "Reranking and Route Coverage"
   - Text reranker.
   - Multimodal reranker when enabled.
   - Select top evidence while preserving text/image coverage.
5. "RetrievalRecord"
   - retrieved evidence, score, route, source IDs, question ID.

Show text evidence cards in blue, image evidence cards in purple, review evidence cards in green. Use solid arrows for data flow and a split arrow for text/image routes that recombine before the RetrievalRecord.

Output arrow downward to Layer 4 labeled "generate report only from retrieved and review evidence".

Layer 4 label on the left:
"4 Evidence-Constrained Analysis and Reporting Layer"
Subtitle: "(Grounded VOC Report + Attribution)"

Layer 4 central content:
Use a purple-outlined container with the following sequence:
1. "Aspect Aggregation"
   - positive, negative, neutral counts
   - confidence averages
   - supporting review spans
2. "Evidence-Constrained Report Generation"
   - Output sections: strengths, weaknesses, controversies, evidence gaps, suggestions.
   - Mark that generation can be LLM-based or heuristic fallback.
3. "Report Refinement"
   - deduplicate insights
   - calibrate evidence level
   - fix unsupported image-support claims
4. "Claim-Level Attribution"
   - map each report claim to review evidence, product text evidence, and product image evidence.
   - support states: supported, partial, unsupported, contradicted.
5. "Artifacts"
   - analysis JSON
   - feedback sidecar
   - replay sidecar
   - HTML report
   - run manifest
   - process trace

At the bottom of the central pipeline, show the final output in a wide blue-outlined bar:
"Output: Grounded VOC Report + Evidence Gaps + Improvement Suggestions + Claim Attribution"
Subtitle: "Every major insight is traceable to review, product text, or product image evidence."

Right-side dashed feedback loop:
Dashed blue container titled "Evaluation, Feedback, and Experiment Loop".
Stack these boxes vertically:
1. "Run Manifest Evaluation"
   - Recall@1/3/5, MRR, NDCG.
2. "Claim Attribution Metrics"
   - claim support rate, grounded rate, citation precision, contradiction rate.
3. "Modality Contribution Analysis"
   - text route, image route, mixed route contribution.
4. "Experiment Matrix"
   - full system, no question planning, no image, no rerank, no attribution, RAG-style baselines.
5. "Feedback and Replay"
   - persistent issues, applied corrections, reusable sidecars.
Draw dashed arrows from this loop back to:
- review sampling and aspect extraction in Layer 2,
- question planning and retrieval/reranking in Layer 3,
- report refinement and attribution in Layer 4.

Bottom legend:
- Green node: review/VOC evidence.
- Blue node: product text evidence.
- Purple node: product image or image-region evidence.
- Orange arrow: retrieval route.
- Black solid arrow: main data flow.
- Black dashed arrow: feedback, replay, or evaluation-driven update.
- Small citation-link icon: claim attribution.

Important accuracy constraints:
- Do not depict the system as a generic chatbot or a single RAG QA chain.
- The central idea is not "answer a user question"; it is "transform product pages and reviews into evidence-grounded VOC analysis".
- Keep the workflow product-centered: one category/product_id runs through normalization, indexing, analysis, reporting, and evaluation.
- Do not invent unrelated modules. Use the exact terms listed above.
- All text in the figure should be English.
```
