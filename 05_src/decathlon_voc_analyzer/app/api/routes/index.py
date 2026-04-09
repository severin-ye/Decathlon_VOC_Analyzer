from fastapi import APIRouter

from decathlon_voc_analyzer.schemas.index import IndexBuildRequest, IndexBuildResponse, IndexOverview
from decathlon_voc_analyzer.stage3_retrieval.index_service import IndexService


router = APIRouter(prefix="/index", tags=["index"])
service = IndexService()


@router.get("/overview", response_model=IndexOverview)
def get_index_overview() -> IndexOverview:
    return service.get_overview()


@router.post("/build", response_model=IndexBuildResponse)
def build_index(request: IndexBuildRequest) -> IndexBuildResponse:
    return service.build_index(request)