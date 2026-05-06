## Abstract

E-commerce VOC (Voice of Customer) analysis requires understanding both the subjective user experiences expressed in reviews and the objective evidence presented on product pages. This paper proposes Decathlon VOC Analyzer, an evidence-driven multimodal VOC analysis system that explicitly aligns product images, product text, and user reviews. The system standardizes product information into evidence packages, preserves raw reviews with ratings, and constructs aspect-level VOC objects through rating-aware sampling and low-information review filtering. It then plans each aspect into questions for text support, visual confirmation, and cross-modal disambiguation, retrieves and reranks candidate evidence along text and image routes, and finally generates structured reports with claim-level evidence attribution and explicit evidence gaps. The current implementation preserves key intermediate artifacts to support reproducibility, error localization, and subsequent replay analysis, and 166 automated tests validate the stability of the core workflow.

## Keywords

multimodal VOC analysis; evidence-constrained generation; image-text retrieval; product review mining; claim attribution
