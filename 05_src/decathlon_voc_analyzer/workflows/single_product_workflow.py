from functools import lru_cache
from typing import NotRequired, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from decathlon_voc_analyzer.schemas.analysis import ProductAnalysisRequest, ProductAnalysisResponse
from decathlon_voc_analyzer.schemas.dataset import DatasetNormalizeRequest, DatasetNormalizationResult, DatasetOverview
from decathlon_voc_analyzer.schemas.index import IndexBuildRequest, IndexBuildResponse
from decathlon_voc_analyzer.runtime_progress import get_workflow_progress
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
    reuse_extraction_artifact: bool
    reuse_analysis_checkpoint: bool
    overview: NotRequired[DatasetOverview]
    normalization: NotRequired[DatasetNormalizationResult | None]
    index_result: NotRequired[IndexBuildResponse | None]
    analysis: NotRequired[ProductAnalysisResponse]


def build_single_product_workflow():
    dataset_service = DatasetService()
    index_service = IndexService()
    analysis_service = ProductAnalysisService()

    def overview_node(state: SingleProductWorkflowState) -> dict[str, DatasetOverview]:
        progress = get_workflow_progress()
        progress.activate_module("overview", detail="Counting categories, products and reviews")
        progress.activate_step("overview", "scan", detail="Scanning dataset directory")
        result = dataset_service.build_overview()
        progress.complete_step("overview", "scan")
        progress.activate_step("overview", "summarize", detail="Summarizing overview")
        progress.complete_step("overview", "summarize")
        progress.complete_module("overview")
        return {"overview": result}

    def normalize_node(state: SingleProductWorkflowState) -> dict[str, DatasetNormalizationResult | None]:
        progress = get_workflow_progress()
        progress.activate_module("normalize", detail=f"Normalizing product package for {state['product_id']}")
        if state.get("skip_normalize"):
            progress.skip_module("normalize", detail="Normalization stage skipped")
            return {"normalization": None}
        progress.activate_step("normalize", "select", detail="Selecting target product directory")
        result = dataset_service.normalize_dataset(
            DatasetNormalizeRequest(
                categories=[state["category"]],
                product_ids=[state["product_id"]],
                persist_artifacts=True,
                use_llm=state["use_llm"],
            )
        )
        progress.complete_step("normalize", "select")
        progress.complete_module("normalize")
        return {"normalization": result}

    def index_node(state: SingleProductWorkflowState) -> dict[str, IndexBuildResponse | None]:
        progress = get_workflow_progress()
        progress.activate_module("index", detail=f"Building evidence index for {state['product_id']}")
        if state.get("skip_index"):
            progress.skip_module("index", detail="Index stage skipped")
            return {"index_result": None}
        progress.activate_step("index", "load_packages", detail="Loading product packages and organizing evidence")
        result = index_service.build_index(
            IndexBuildRequest(
                categories=[state["category"]],
                product_ids=[state["product_id"]],
                persist_artifact=True,
                use_llm=state["use_llm"],
            )
        )
        progress.complete_step("index", "load_packages")
        progress.complete_module("index")
        return {"index_result": result}

    def analyze_node(state: SingleProductWorkflowState) -> dict[str, ProductAnalysisResponse]:
        progress = get_workflow_progress()
        progress.activate_module("analyze", detail=f"Generating analysis report for {state['product_id']}")
        progress.activate_step("analyze", "extract", detail="Extracting reviews and aspects")
        result = analysis_service.analyze(
            ProductAnalysisRequest(
                product_id=state["product_id"],
                category_slug=state["category"],
                max_reviews=state.get("max_reviews"),
                use_llm=state["use_llm"],
                persist_artifact=True,
                use_replay=True,
                reuse_extraction_artifact=state.get("reuse_extraction_artifact", False),
                reuse_analysis_checkpoint=state.get("reuse_analysis_checkpoint", False),
                top_k_per_route=state["top_k_per_route"],
                questions_per_aspect=state["questions_per_aspect"],
            )
        )
        progress.complete_step("analyze", "extract")
        progress.complete_module("analyze")
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