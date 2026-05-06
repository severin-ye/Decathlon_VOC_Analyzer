## Abstract

E-commerce VOC (Voice of Customer) analysis requires understanding both subjective user experiences expressed in reviews and objective evidence on product pages. This paper proposes Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system that explicitly aligns product image-text evidence with user reviews. The proposed system standardizes product information into evidence packages, extracts aspect-level VOC objects from reviews, and plans each aspect into questions for text support, visual confirmation, and cross-modal explanation. It then retrieves and reranks candidate evidence along text and image routes, and finally generates structured reports with claim-level evidence attribution. The current implementation preserves key intermediate artifacts to support reproducibility and error analysis, and 166 automated tests confirm the stability of the core workflow.

## Keywords

multimodal VOC analysis; evidence-constrained generation; image-text retrieval; product review mining; claim attribution
