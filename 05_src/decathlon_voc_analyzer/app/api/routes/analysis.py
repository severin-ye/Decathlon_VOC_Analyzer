from fastapi import APIRouter, HTTPException

from decathlon_voc_analyzer.schemas.analysis import ProductAnalysisRequest, ProductAnalysisResponse
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


router = APIRouter(prefix="/analysis", tags=["analysis"])
service = ProductAnalysisService()


@router.post("/product", response_model=ProductAnalysisResponse)
def analyze_product(request: ProductAnalysisRequest) -> ProductAnalysisResponse:
    try:
        return service.analyze(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc