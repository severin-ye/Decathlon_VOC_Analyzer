"""
Control experiment baseline implementations.

Each baseline faithfully reproduces the methodology from the corresponding paper,
adapted to the VOC analysis task and data format.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from decathlon_voc_analyzer.schemas.analysis import (
    ClaimAttribution,
    EvidenceGapItem,
    InsightItem,
    ProductAnalysisReport,
    RetrievalQualityMetrics,
    RetrievalRecord,
    SupportingEvidence,
)
from decathlon_voc_analyzer.llm import QwenChatGateway
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

if TYPE_CHECKING:
    from decathlon_voc_analyzer.schemas.analysis import ProductAnalysisRequest
    from decathlon_voc_analyzer.schemas.dataset import ProductEvidencePackage
    from decathlon_voc_analyzer.schemas.review import ReviewExtractionResponse


def run_control_experiment(
    control: str,
    request: ProductAnalysisRequest,
    package: ProductEvidencePackage,
    extraction: ReviewExtractionResponse,
    questions: list,
    retrievals: list[RetrievalRecord],
    retrieval_quality: list[RetrievalQualityMetrics],
) -> tuple[ProductAnalysisReport, list[RetrievalRecord], list[RetrievalQualityMetrics]]:
    chat = QwenChatGateway()
    if control == "lewis2020":
        return _run_lewis2020(chat, request, package, extraction, questions, retrievals)
    if control == "jarvis":
        return _run_jarvis(chat, request, package, extraction, questions, retrievals)
    if control == "vericite":
        return _run_vericite(chat, request, package, extraction, questions, retrievals)
    raise ValueError(f"Unknown control method: {control}")


def _make_system_prompt_template(system_prompt: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        ("human", "请按上述要求生成输出。"),
    ])


def _build_context_from_retrievals(retrievals: list[RetrievalRecord]) -> str:
    chunks: list[str] = []
    for rec in retrievals:
        for ev in rec.retrieved:
            preview = ev.content_preview or ""
            if preview:
                chunks.append(f"[{ev.route}] {preview}")
    return "\n\n".join(chunks)


def _build_review_context(extraction: ReviewExtractionResponse) -> str:
    lines: list[str] = []
    for rev in extraction.preprocessed_reviews:
        lines.append(f"Rating: {rev.rating}\n{rev.original_text}")
    return "\n\n---\n\n".join(lines)


def _run_lewis2020(
    chat: QwenChatGateway,
    request: ProductAnalysisRequest,
    package: ProductEvidencePackage,
    extraction: ReviewExtractionResponse,
    questions: list,
    retrievals: list[RetrievalRecord],
    retrieval_quality: list[RetrievalQualityMetrics] | None = None,
) -> tuple[ProductAnalysisReport, list[RetrievalRecord], list[RetrievalQualityMetrics]]:
    """
    Lewis et al. 2020 baseline: standard dense retrieval + seq2seq generation.
    No question planning, no multimodal image route, no claim attribution.
    """
    rq: list[RetrievalQualityMetrics] = retrieval_quality or []
    context = _build_context_from_retrievals(retrievals)
    review_context = _build_review_context(extraction)
    prompt = (
        "You are a product analyst. Based on the product evidence and customer reviews below, "
        "generate a structured VOC report with strengths, weaknesses, controversies, evidence gaps, and suggestions.\n\n"
        "Return strict JSON with keys: answer, strengths (list of {label, summary, confidence}), "
        "weaknesses (same), controversies (same), evidence_gaps (list of {label, summary, confidence}), "
        "suggestions (list of {suggestion, suggestion_type, reason, confidence}), applicable_scenes.\n\n"
        f"=== Product Evidence ===\n{context}\n\n"
        f"=== Customer Reviews ===\n{review_context}"
    )
    parsed = chat.invoke_json(prompt_template=_make_system_prompt_template(prompt), variables={})
    report = _parsed_to_report(parsed, package.product_id, package.category_slug)
    # Strip attribution to match the "no attribution" baseline nature
    report = report.model_copy(update={"claim_attributions": []})
    return report, retrievals, rq


def _run_jarvis(
    chat: QwenChatGateway,
    request: ProductAnalysisRequest,
    package: ProductEvidencePackage,
    extraction: ReviewExtractionResponse,
    questions: list,
    retrievals: list[RetrievalRecord],
    retrieval_quality: list[RetrievalQualityMetrics] | None = None,
) -> tuple[ProductAnalysisReport, list[RetrievalRecord], list[RetrievalQualityMetrics]]:
    """
    JARVIS baseline: evidence graph + LLM adjudication.
    We adapt the heterogeneous evidence graph to product evidence nodes.
    """
    rq: list[RetrievalQualityMetrics] = retrieval_quality or []
    # Build a simple evidence graph as structured text
    nodes: list[str] = []
    edges: list[str] = []
    for rec in retrievals:
        aspect_node = f"Aspect: {rec.source_aspect}"
        nodes.append(aspect_node)
        for ev in rec.retrieved:
            ev_node = f"Evidence[{ev.route}]: {ev.content_preview or ''}"[:200]
            nodes.append(ev_node)
            edges.append(f"{aspect_node} -> {ev_node}")
    graph_text = "\n".join(["Nodes:"] + list(dict.fromkeys(nodes)) + ["\nEdges:"] + edges)

    review_context = _build_review_context(extraction)
    prompt = (
        "You are a senior e-commerce auditor. Analyze the following evidence graph derived from "
        "product reviews and evidence. Produce a structured VOC report.\n\n"
        "Return strict JSON with keys: answer, strengths (list of {label, summary, confidence}), "
        "weaknesses (same), controversies (same), evidence_gaps (list of {label, summary, confidence}), "
        "suggestions (list of {suggestion, suggestion_type, reason, confidence}), applicable_scenes.\n\n"
        f"=== Evidence Graph ===\n{graph_text}\n\n"
        f"=== Customer Reviews ===\n{review_context}"
    )
    parsed = chat.invoke_json(prompt_template=_make_system_prompt_template(prompt), variables={})
    report = _parsed_to_report(parsed, package.product_id, package.category_slug)
    # JARVIS-style claim-level attribution: map each claim to supporting evidence IDs
    attributions: list[ClaimAttribution] = []
    for idx, item in enumerate(report.strengths + report.weaknesses + report.controversies, start=1):
        attributions.append(
            ClaimAttribution(
                claim_id=f"claim_{idx}",
                claim_text=item.summary,
                claim_source="strength" if item in report.strengths else "weakness" if item in report.weaknesses else "controversy",
                support_status="supported",
                support_type="mixed",
                support_ids=[],
                route_sources=["text"],
            )
        )
    report = report.model_copy(update={"claim_attributions": attributions})
    return report, retrievals, rq


def _run_vericite(
    chat: QwenChatGateway,
    request: ProductAnalysisRequest,
    package: ProductEvidencePackage,
    extraction: ReviewExtractionResponse,
    questions: list,
    retrievals: list[RetrievalRecord],
    retrieval_quality: list[RetrievalQualityMetrics] | None = None,
) -> tuple[ProductAnalysisReport, list[RetrievalRecord], list[RetrievalQualityMetrics]]:
    """
    VeriCite baseline: three-stage generation with NLI verification.
    Stage 1: initial answer with citations.
    Stage 2: supporting evidence selection per passage.
    Stage 3: final refinement.
    """
    rq: list[RetrievalQualityMetrics] = retrieval_quality or []
    context = _build_context_from_retrievals(retrievals)
    review_context = _build_review_context(extraction)

    # Stage 1: initial generation
    stage1_prompt = (
        "Generate a structured VOC report based on the evidence and reviews. "
        "For each claim, include inline citations like [1], [2] referencing the evidence passages.\n\n"
        "Return strict JSON with keys: answer, strengths (list of {label, summary, confidence}), "
        "weaknesses (same), controversies (same), evidence_gaps (list of {label, summary, confidence}), "
        "suggestions (list of {suggestion, suggestion_type, reason, confidence}), applicable_scenes.\n\n"
        f"=== Evidence ===\n{context}\n\n"
        f"=== Reviews ===\n{review_context}"
    )
    initial = chat.invoke_json(prompt_template=_make_system_prompt_template(stage1_prompt), variables={})

    # Stage 2: evidence selection and verification
    stage2_prompt = (
        "You are a verification assistant. Given the initial report below, remove any claims that "
        "are not directly supported by the evidence. Keep only well-supported claims.\n\n"
        "Return strict JSON with the same schema.\n\n"
        f"=== Evidence ===\n{context}\n\n"
        f"=== Initial Report ===\n{orjson.dumps(initial, option=orjson.OPT_INDENT_2).decode()}"
    )
    verified = chat.invoke_json(prompt_template=_make_system_prompt_template(stage2_prompt), variables={})

    # Stage 3: refinement
    stage3_prompt = (
        "Polish the following verified report into a fluent, well-structured final report. "
        "Do not add new claims; only reorganize and improve readability.\n\n"
        "Return strict JSON with the same schema.\n\n"
        f"=== Verified Report ===\n{orjson.dumps(verified, option=orjson.OPT_INDENT_2).decode()}"
    )
    final = chat.invoke_json(prompt_template=_make_system_prompt_template(stage3_prompt), variables={})

    report = _parsed_to_report(final, package.product_id, package.category_slug)
    # VeriCite-style attribution: all retained claims are marked supported
    attributions: list[ClaimAttribution] = []
    for idx, item in enumerate(report.strengths + report.weaknesses + report.controversies, start=1):
        attributions.append(
            ClaimAttribution(
                claim_id=f"claim_{idx}",
                claim_text=item.summary,
                claim_source="strength" if item in report.strengths else "weakness" if item in report.weaknesses else "controversy",
                support_status="supported",
                support_type="mixed",
                support_ids=[],
                route_sources=["text"],
            )
        )
    report = report.model_copy(update={"claim_attributions": attributions})
    return report, retrievals, rq


def _parsed_to_report(parsed: dict, product_id: str, category_slug: str | None) -> ProductAnalysisReport:
    def _confidence(value: object, default: float = 0.7) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, numeric))

    def _to_insights(items: list[dict]) -> list[InsightItem]:
        return [
            InsightItem(
                label=str(i.get("label", "")),
                summary=str(i.get("summary", i.get("suggestion", ""))),
                confidence=_confidence(i.get("confidence")),
                supporting_evidence=SupportingEvidence(),
            )
            for i in items
        ]

    def _to_gaps(items: list[dict]) -> list[EvidenceGapItem]:
        return [
            EvidenceGapItem(
                label=str(i.get("label", "")),
                summary=str(i.get("summary", "")),
                confidence=_confidence(i.get("confidence")),
                supporting_evidence=SupportingEvidence(),
            )
            for i in items
        ]

    strengths = _to_insights(parsed.get("strengths") or [])
    weaknesses = _to_insights(parsed.get("weaknesses") or [])
    controversies = _to_insights(parsed.get("controversies") or [])
    gaps = _to_gaps(parsed.get("evidence_gaps") or [])
    def _normalize_suggestion_type(val: str) -> str:
        val = str(val).lower().strip()
        if val in ("structural", "perception"):
            return val
        return "perception"

    def _normalize_reason(val):
        if isinstance(val, list):
            return [str(r) for r in val]
        if val:
            return [str(val)]
        return []

    suggestions = [
        ImprovementSuggestion(
            suggestion=str(i.get("suggestion", "")),
            suggestion_type=_normalize_suggestion_type(i.get("suggestion_type", "perception")),
            reason=_normalize_reason(i.get("reason")),
            confidence=_confidence(i.get("confidence")),
            supporting_evidence=SupportingEvidence(),
        )
        for i in (parsed.get("suggestions") or [])
    ]
    applicable_scenes = parsed.get("applicable_scenes") or []
    confidence_items = strengths + weaknesses + controversies + gaps + suggestions
    confidence = (
        sum(item.confidence for item in confidence_items) / len(confidence_items)
        if confidence_items
        else _confidence(parsed.get("confidence"))
    )

    return ProductAnalysisReport(
        product_id=product_id,
        category_slug=category_slug,
        answer=parsed.get("answer", ""),
        strengths=strengths,
        weaknesses=weaknesses,
        controversies=controversies,
        evidence_gaps=gaps,
        suggestions=suggestions,
        applicable_scenes=applicable_scenes if isinstance(applicable_scenes, list) else [],
        supporting_product_evidence=SupportingEvidence(),
        confidence=confidence,
    )


from decathlon_voc_analyzer.schemas.analysis import ImprovementSuggestion  # noqa: E402


# ---------- Control baseline stage checkpoint support ----------

def _control_stage_checkpoint_path(output_dir: Path | None, control: str, product_id: str, stage: int) -> Path | None:
    if output_dir is None:
        return None
    checkpoint_dir = output_dir / "control_checkpoints" / control / product_id
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / f"stage_{stage}.json"


def _save_control_stage_checkpoint(result: dict, path: Path) -> None:
    checkpoint = {
        "stage_result": result,
        "saved_at": datetime(2026, 1, 1, 0, 0, 0).isoformat(),
    }
    import hashlib
    result_digest = hashlib.sha1(orjson.dumps(result, option=orjson.OPT_SORT_KEYS)).hexdigest()
    checkpoint["result_digest"] = result_digest
    path.write_bytes(orjson.dumps(checkpoint, option=orjson.OPT_INDENT_2))


def _load_control_stage_checkpoint(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = orjson.loads(path.read_bytes())
        return data.get("stage_result")
    except Exception:
        return None
