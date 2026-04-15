from functools import lru_cache
from typing import NotRequired, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from decathlon_voc_analyzer.schemas.analysis import ProductAnalysisRequest, ProductAnalysisResponse
from decathlon_voc_analyzer.schemas.dataset import DatasetNormalizeRequest, DatasetNormalizationResult, DatasetOverview
from decathlon_voc_analyzer.schemas.index import IndexBuildRequest, IndexBuildResponse
from decathlon_voc_analyzer.stage1_dataset.dataset_service import DatasetService
from decathlon_voc_analyzer.stage3_retrieval.index_service import IndexService
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


class SingleProductWorkflowState(TypedDict):
    category: str
    product_id: str
    max_reviews: int | None
    top_k_per_route: int
    questions_per_aspect: int
    use_llm: bool
    skip_normalize: bool
    skip_index: bool
    overview: NotRequired[DatasetOverview]
    normalization: NotRequired[DatasetNormalizationResult | None]
    index_result: NotRequired[IndexBuildResponse | None]
    analysis: NotRequired[ProductAnalysisResponse]


def build_single_product_workflow():
    dataset_service = DatasetService()
    index_service = IndexService()
    analysis_service = ProductAnalysisService()

    def overview_node(state: SingleProductWorkflowState) -> dict[str, DatasetOverview]:
        return {"overview": dataset_service.build_overview()}

    def normalize_node(state: SingleProductWorkflowState) -> dict[str, DatasetNormalizationResult | None]:
        if state.get("skip_normalize"):
            return {"normalization": None}
        result = dataset_service.normalize_dataset(
            DatasetNormalizeRequest(
                categories=[state["category"]],
                product_ids=[state["product_id"]],
                persist_artifacts=True,
            )
        )
        return {"normalization": result}

    def index_node(state: SingleProductWorkflowState) -> dict[str, IndexBuildResponse | None]:
        if state.get("skip_index"):
            return {"index_result": None}
        result = index_service.build_index(
            IndexBuildRequest(
                categories=[state["category"]],
                product_ids=[state["product_id"]],
                persist_artifact=True,
            )
        )
        return {"index_result": result}

    def analyze_node(state: SingleProductWorkflowState) -> dict[str, ProductAnalysisResponse]:
        result = analysis_service.analyze(
            ProductAnalysisRequest(
                product_id=state["product_id"],
                category_slug=state["category"],
                max_reviews=state.get("max_reviews"),
                use_llm=state["use_llm"],
                persist_artifact=True,
                use_replay=True,
                top_k_per_route=state["top_k_per_route"],
                questions_per_aspect=state["questions_per_aspect"],
            )
        )
        return {"analysis": result}

    builder = StateGraph(SingleProductWorkflowState)
    builder.add_node("overview", overview_node)
    builder.add_node("normalize", normalize_node)
    builder.add_node("index", index_node)
    builder.add_node("analyze", analyze_node)
    builder.add_edge(START, "overview")
    builder.add_edge("overview", "normalize")
    builder.add_edge("normalize", "index")
    builder.add_edge("index", "analyze")
    builder.add_edge("analyze", END)
    return builder.compile(checkpointer=InMemorySaver())


@lru_cache(maxsize=1)
def get_single_product_workflow():
    return build_single_product_workflow()