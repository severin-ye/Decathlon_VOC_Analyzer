from fastapi import APIRouter, HTTPException

from decathlon_voc_analyzer.models.review import ReviewExtractionRequest, ReviewExtractionResponse
from decathlon_voc_analyzer.services.review_service import ReviewExtractionService


router = APIRouter(prefix="/reviews", tags=["reviews"])
service = ReviewExtractionService()


@router.post("/extract", response_model=ReviewExtractionResponse)
def extract_review_aspects(request: ReviewExtractionRequest) -> ReviewExtractionResponse:
    try:
        return service.extract(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc