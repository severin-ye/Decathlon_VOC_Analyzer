from fastapi import FastAPI

from decathlon_voc_analyzer.api.routes.analysis import router as analysis_router
from decathlon_voc_analyzer.api.routes.dataset import router as dataset_router
from decathlon_voc_analyzer.api.routes.index import router as index_router
from decathlon_voc_analyzer.api.routes.reviews import router as reviews_router
from decathlon_voc_analyzer.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title="Decathlon VOC Analyzer",
    version="0.1.0",
    description="Evidence-driven multimodal VOC analysis backend",
)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
    }


app.include_router(dataset_router, prefix="/api/v1")
app.include_router(index_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")