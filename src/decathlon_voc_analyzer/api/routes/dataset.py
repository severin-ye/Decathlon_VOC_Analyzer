from fastapi import APIRouter

from decathlon_voc_analyzer.models.dataset import (
    DatasetNormalizeRequest,
    DatasetOverview,
    DatasetNormalizationResult,
)
from decathlon_voc_analyzer.services.dataset_service import DatasetService


router = APIRouter(prefix="/dataset", tags=["dataset"])
service = DatasetService()


@router.get("/overview", response_model=DatasetOverview)
def get_dataset_overview() -> DatasetOverview:
    return service.build_overview()


@router.post("/normalize", response_model=DatasetNormalizationResult)
def normalize_dataset(request: DatasetNormalizeRequest) -> DatasetNormalizationResult:
    return service.normalize_dataset(request)