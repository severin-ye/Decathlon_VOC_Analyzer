from pathlib import Path

from decathlon_voc_analyzer.schemas.analysis import (
    AttributionCheckpointPayload,
    AttributionCheckpointSignature,
    ExperimentRunManifest,
    ReportCheckpointPayload,
    ReportCheckpointSignature,
)
from decathlon_voc_analyzer.schemas.review import ReviewAspect
from decathlon_voc_analyzer.schemas.retrieval_cache import (
    RetrievalStageCheckpointPayload,
    RetrievalStageCheckpointSignature,
)
from decathlon_voc_analyzer.schemas.analysis import RetrievalQuestion
from decathlon_voc_analyzer.stage4_generation.analysis_service import ProductAnalysisService


def _build_aspect() -> ReviewAspect:
    return ReviewAspect(
        aspect_id="a1",
        review_id="r1",
        product_id="p1",
        aspect="test_aspect",
        sentiment="positive",
        opinion="test opinion",
        evidence_span="test evidence",
        usage_scene="test",
        confidence=0.9,
        extraction_mode="llm",
    )


class TestRetrievalStageCheckpoint:
    def test_schema_valid(self) -> None:
        sig = RetrievalStageCheckpointSignature(
            question_id="q1",
            question_digest="abc",
            top_k_per_route=2,
            use_llm=True,
            ablation_no_image=False,
            ablation_no_reranking=False,
            index_digest="",
            embedding_backend="api",
            reranker_backend="api",
            prompt_variant="main",
        )
        payload = RetrievalStageCheckpointPayload(
            product_id="p1",
            stage="final",
            created_at="2026-01-01T00:00:00+00:00",
            signature=sig,
        )
        assert payload.stage == "final"
        assert payload.product_id == "p1"


class TestReportCheckpoint:
    def test_schema_valid(self) -> None:
        sig = ReportCheckpointSignature(
            aggregates_digest="",
            retrievals_digest="",
            prompt_variant="",
            prompt_digest="",
            llm_model="",
            use_llm=True,
            control_method="none",
        )
        payload = ReportCheckpointPayload(
            product_id="p1",
            stage="raw_llm",
            created_at="2026-01-01T00:00:00+00:00",
            signature=sig,
            raw_report={"strengths": []},
        )
        assert payload.raw_report is not None
        assert payload.stage == "raw_llm"


class TestAttributionCheckpoint:
    def test_schema_valid(self) -> None:
        sig = AttributionCheckpointSignature(
            report_digest="",
            aspects_digest="",
            retrievals_digest="",
            attribution_version="1.0",
        )
        payload = AttributionCheckpointPayload(
            product_id="p1",
            created_at="2026-01-01T00:00:00+00:00",
            signature=sig,
        )
        assert len(payload.evidence_nodes) == 0
        assert len(payload.claim_attributions) == 0


class TestExperimentRunManifest:
    def test_schema_valid(self) -> None:
        manifest = ExperimentRunManifest(
            run_id="backpack__p1__full_system",
            product_id="p1",
            category_slug="backpack",
            condition_name="full_system",
            status="pending",
            stages={"retrieval": "succeeded", "report": "pending"},
        )
        assert manifest.status == "pending"
        assert manifest.stages["retrieval"] == "succeeded"


class TestAnalysisServiceCheckpointHelpers:
    def test_per_question_checkpoint_path(self) -> None:
        service = ProductAnalysisService()
        q = RetrievalQuestion(
            question_id="a1_q_01",
            source_review_id="review_0001",
            source_aspect="test",
            source_aspect_id="a1",
            question="test?",
            rationale="test",
            confidence=0.5,
        )
        path = service._build_retrieval_checkpoint_path(q, "final", "_test_suffix")
        assert "_test_suffix" in path.name
        assert "retrieval_checkpoints" in str(path)

    def test_report_checkpoint_path(self, tmp_path) -> None:
        service = ProductAnalysisService()
        service.settings.reports_output_dir = tmp_path
        path = service._build_report_checkpoint_path("p1", "backpack", "_test_cp")
        assert path.exists() is False
        assert "_test_cp" in path.name
        assert "report_checkpoint" in path.name

    def test_attribution_checkpoint_path(self, tmp_path) -> None:
        service = ProductAnalysisService()
        service.settings.reports_output_dir = tmp_path
        path = service._build_attribution_checkpoint_path("p1", "backpack", "_no_attr")
        assert "_no_attr" in path.name
        assert "attribution_checkpoint" in path.name

    def test_save_and_load_report_checkpoint(self, tmp_path) -> None:
        service = ProductAnalysisService()
        service.settings.reports_output_dir = tmp_path
        raw = {"strengths": [], "weaknesses": []}
        path = service._save_report_checkpoint("p1", "backpack", "raw_llm", raw, "_test")

        assert path.endswith(".json")
        assert Path(path).exists()

        loaded = service._load_report_checkpoint("p1", "backpack", "_test")
        assert loaded is not None
        assert loaded.get("strengths") == []
        assert loaded.get("weaknesses") == []

    def test_save_and_load_attribution_checkpoint(self, tmp_path) -> None:
        service = ProductAnalysisService()
        service.settings.reports_output_dir = tmp_path
        nodes = [{"node_id": "n1"}]
        attrs = [{"claim_id": "c1"}]
        service._save_attribution_checkpoint("p1", "backpack", nodes, attrs, "_test")

        result = service._load_attribution_checkpoint("p1", "backpack", "_test")
        assert result is not None
        nodes_loaded, attrs_loaded = result
        assert nodes_loaded == nodes
        assert attrs_loaded == attrs

    def test_report_checkpoint_missing_returns_none(self, tmp_path) -> None:
        service = ProductAnalysisService()
        service.settings.reports_output_dir = tmp_path
        result = service._load_report_checkpoint("nonexistent", "backpack", "_test")
        assert result is None

    def test_attribution_checkpoint_missing_returns_none(self, tmp_path) -> None:
        service = ProductAnalysisService()
        service.settings.reports_output_dir = tmp_path
        result = service._load_attribution_checkpoint("nonexistent", "backpack", "_test")
        assert result is None
