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
        progress.activate_module("overview", detail="统计类目、商品与评论总量")
        progress.activate_step("overview", "scan", detail="扫描数据集目录")
        result = dataset_service.build_overview()
        progress.complete_step("overview", "scan")
        progress.activate_step("overview", "summarize", detail="汇总概览信息")
        progress.complete_step("overview", "summarize")
        progress.complete_module("overview")
        return {"overview": result}

    def normalize_node(state: SingleProductWorkflowState) -> dict[str, DatasetNormalizationResult | None]:
        progress = get_workflow_progress()
        progress.activate_module("normalize", detail=f"标准化 {state['product_id']} 所在商品包")
        if state.get("skip_normalize"):
            progress.skip_module("normalize", detail="已跳过标准化阶段")
            return {"normalization": None}
        progress.activate_step("normalize", "select", detail="选择目标商品目录")
        result = dataset_service.normalize_dataset(
            DatasetNormalizeRequest(
                categories=[state["category"]],
                product_ids=[state["product_id"]],
                persist_artifacts=True,
            )
        )
        progress.complete_step("normalize", "select")
        progress.complete_module("normalize")
        return {"normalization": result}

    def index_node(state: SingleProductWorkflowState) -> dict[str, IndexBuildResponse | None]:
        progress = get_workflow_progress()
        progress.activate_module("index", detail=f"为 {state['product_id']} 构建证据索引")
        if state.get("skip_index"):
            progress.skip_module("index", detail="已跳过索引阶段")
            return {"index_result": None}
        progress.activate_step("index", "load_packages", detail="加载商品包并整理证据")
        result = index_service.build_index(
            IndexBuildRequest(
                categories=[state["category"]],
                product_ids=[state["product_id"]],
                persist_artifact=True,
            )
        )
        progress.complete_step("index", "load_packages")
        progress.complete_module("index")
        return {"index_result": result}

    def analyze_node(state: SingleProductWorkflowState) -> dict[str, ProductAnalysisResponse]:
        progress = get_workflow_progress()
        progress.activate_module("analyze", detail=f"生成 {state['product_id']} 的分析报告")
        progress.activate_step("analyze", "extract", detail="抽取评论与方面")
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