from pathlib import Path
import html

from decathlon_voc_analyzer.prompts import get_prompt_variant


class HtmlExportService:
    def _is_cn_variant(self) -> bool:
        return get_prompt_variant() == "CN"

    def _document_lang(self) -> str:
        return "zh-CN" if self._is_cn_variant() else "en"

    def _labels(self) -> dict[str, str]:
        if self._is_cn_variant():
            return {
                "page_title_suffix": "VOC 报告",
                "strengths": "优势",
                "gallery": "证据图集",
                "weaknesses": "问题点",
                "controversies": "争议点",
                "evidence_gaps": "证据缺口",
                "suggestions": "改进建议",
                "retrieval_judge": "检索质检",
                "runtime_profile": "运行配置",
                "process_drawer": "过程抽屉",
                "no_items": "暂无条目。",
                "no_suggestions": "暂无建议。",
                "no_evidence_refs": "暂无证据引用。",
                "no_retrieval_metrics": "暂无检索指标。",
                "no_runtime_profile": "暂无运行配置。",
                "no_trace": "暂无过程记录。",
                "no_images": "暂无图片证据。",
                "owner": "归因",
                "confidence": "置信度",
                "type": "类型",
                "evidence": "证据",
                "support": "支撑",
                "coverage": "覆盖度",
                "drift": "漂移",
                "conflict": "冲突风险",
                "quality": "质量",
                "reason": "原因",
                "action": "动作",
                "text": "文本",
                "image": "图像",
                "text_embedding": "文本向量",
                "image_embedding": "图像向量",
                "text_reranker": "文本精排",
                "multimodal_reranker": "多模态精排",
                "native_multimodal_enabled": "原生多模态启用",
            }
        return {
            "page_title_suffix": "VOC Report",
            "strengths": "Strengths",
            "gallery": "Evidence Gallery",
            "weaknesses": "Weaknesses",
            "controversies": "Controversies",
            "evidence_gaps": "Evidence Gaps",
            "suggestions": "Suggestions",
            "retrieval_judge": "Retrieval Judge",
            "runtime_profile": "Runtime Profile",
            "process_drawer": "Process Drawer",
            "no_items": "No items.",
            "no_suggestions": "No suggestions.",
            "no_evidence_refs": "No cited evidence.",
            "no_retrieval_metrics": "No retrieval metrics.",
            "no_runtime_profile": "No runtime profile.",
            "no_trace": "No trace.",
            "no_images": "No images available.",
            "owner": "owner",
            "confidence": "confidence",
            "type": "type",
            "evidence": "evidence",
            "support": "support",
            "coverage": "coverage",
            "drift": "drift",
            "conflict": "conflict",
            "quality": "quality",
            "reason": "reason",
            "action": "action",
            "text": "text",
            "image": "image",
            "text_embedding": "text_embedding",
            "image_embedding": "image_embedding",
            "text_reranker": "text_reranker",
            "multimodal_reranker": "multimodal_reranker",
            "native_multimodal_enabled": "native_multimodal_enabled",
        }

    def render(self, analysis_payload: dict, normalized_payload: dict | None = None) -> str:
        report = analysis_payload.get("report", {})
        trace = analysis_payload.get("trace", [])
        retrieval_quality = analysis_payload.get("retrieval_quality", [])
        retrieval_runtime = analysis_payload.get("retrieval_runtime", {})
        normalized_payload = normalized_payload or {}
        product_name = normalized_payload.get("product_name") or report.get("product_id", "Unknown Product")
        category_text = normalized_payload.get("category_text") or report.get("category_slug") or ""
        model_description = normalized_payload.get("model_description") or ""
        hero_answer = report.get("answer", "")
        images = normalized_payload.get("images", [])[:5]
        labels = self._labels()
        evidence_nodes = {
            str(node.get("evidence_node_id")): node
            for node in report.get("evidence_nodes", [])
            if isinstance(node, dict) and node.get("evidence_node_id")
        }
        strength_attributions = self._claim_attributions_for_source(report, "strength")
        weakness_attributions = self._claim_attributions_for_source(report, "weakness")
        controversy_attributions = self._claim_attributions_for_source(report, "controversy")
        suggestion_attributions = self._claim_attributions_for_source(report, "suggestion")
        evidence_gap_attributions = self._claim_attributions_for_source(report, "evidence_gap")

        return f"""<!DOCTYPE html>
    <html lang=\"{self._document_lang()}\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(str(product_name))} {labels['page_title_suffix']}</title>
  {self._render_styles()}
</head>
<body>
  <main class=\"page\">
    <section class=\"hero\">
      <div class=\"eyebrow\">Decathlon VOC Analyzer</div>
      <h1>{html.escape(str(product_name))}</h1>
      <p class=\"sub\">{html.escape(str(category_text))}</p>
      <p class=\"sub\">{html.escape(str(hero_answer))}</p>
      <p class=\"sub\">{html.escape(str(model_description))}</p>
    </section>
    <section class=\"grid\">
      <article class=\"card span-8\"><h2 class=\"section-title\">{labels['strengths']}</h2>{self._render_insight_list(report.get('strengths', []), strength_attributions, evidence_nodes, labels)}</article>
      <article class=\"card span-4\"><h2 class=\"section-title\">{labels['gallery']}</h2>{self._render_gallery(images, normalized_payload.get('source_dir'), labels)}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">{labels['weaknesses']}</h2>{self._render_insight_list(report.get('weaknesses', []), weakness_attributions, evidence_nodes, labels)}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">{labels['controversies']}</h2>{self._render_insight_list(report.get('controversies', []), controversy_attributions, evidence_nodes, labels)}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">{labels['evidence_gaps']}</h2>{self._render_evidence_gap_list(report.get('evidence_gaps', []), evidence_gap_attributions, evidence_nodes, labels)}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">{labels['suggestions']}</h2>{self._render_suggestion_list(report.get('suggestions', []), suggestion_attributions, evidence_nodes, labels)}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">{labels['retrieval_judge']}</h2>{self._render_retrieval_quality(retrieval_quality, labels)}</article>
      <article class=\"card span-12\"><h2 class=\"section-title\">{labels['runtime_profile']}</h2>{self._render_retrieval_runtime(retrieval_runtime, labels)}</article>
      <article class=\"card span-12\"><h2 class=\"section-title\">{labels['process_drawer']}</h2>{self._render_trace(trace, labels)}</article>
    </section>
  </main>
  {self._render_enhancement_script()}
</body>
</html>"""

    def _render_styles(self) -> str:
        return """<style>
    :root {
      --bg: #f5f5f7;
      --panel: rgba(255,255,255,0.78);
      --ink: #1d1d1f;
      --muted: #6e6e73;
      --line: rgba(60,60,67,0.12);
      --blue: #0071e3;
      --shadow: 0 18px 48px rgba(0,0,0,0.08);
      --soft-shadow: 0 8px 22px rgba(0,0,0,0.055);
      --radius: 24px;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { margin: 0; color: var(--ink); background: radial-gradient(circle at top left, rgba(0,113,227,0.11), transparent 30%), radial-gradient(circle at top right, rgba(255,159,10,0.11), transparent 31%), linear-gradient(180deg, #fbfbfd 0%, var(--bg) 100%); font: 14px/1.5 -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', 'Segoe UI', sans-serif; }
    .page { max-width: 1380px; margin: 0 auto; padding: 28px; }
    .hero { position: relative; overflow: hidden; border: 1px solid var(--line); border-radius: 32px; padding: 32px; background: linear-gradient(180deg, rgba(255,255,255,0.88), rgba(255,255,255,0.70)); backdrop-filter: blur(18px) saturate(140%); box-shadow: var(--shadow); }
    .hero::after { content: ""; position: absolute; inset: auto -70px -110px auto; width: 320px; height: 320px; border-radius: 999px; background: radial-gradient(circle, rgba(0,113,227,0.13), transparent 68%); pointer-events: none; }
    .eyebrow { color: var(--muted); text-transform: uppercase; letter-spacing: .05em; font-size: 12px; font-weight: 700; }
    h1 { max-width: 920px; margin: 8px 0 12px; font-size: clamp(34px, 4.8vw, 64px); line-height: .98; letter-spacing: -.055em; }
    .sub { position: relative; max-width: 920px; margin: 10px 0 0; color: var(--muted); font-size: 15px; }
    .hero .sub:nth-of-type(1) { color: var(--blue); font-weight: 650; }
    .hero .sub:nth-of-type(2) { max-width: 980px; color: #2c2c2e; font-size: 18px; line-height: 1.55; letter-spacing: -.01em; }
    .hero .sub:nth-of-type(3) { max-width: 980px; max-height: 142px; overflow: auto; margin-top: 18px; padding: 16px 18px; border: 1px solid var(--line); border-radius: 20px; background: rgba(255,255,255,0.68); box-shadow: inset 0 1px 0 rgba(255,255,255,0.72); }
    .grid { display: grid; gap: 18px; grid-template-columns: repeat(12, minmax(0, 1fr)); margin-top: 18px; align-items: start; }
    .card { min-width: 0; padding: 20px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--panel); backdrop-filter: blur(14px) saturate(135%); box-shadow: var(--shadow); }
    .span-12 { grid-column: span 12; }
    .span-8 { grid-column: span 8; }
    .span-6 { grid-column: span 6; }
    .span-4 { grid-column: span 4; }
    .span-4.card { position: sticky; top: 18px; }
    .section-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 0 16px; font-size: 21px; letter-spacing: -.025em; }
    .section-title::after { content: attr(data-count); color: var(--muted); font-size: 12px; font-weight: 650; letter-spacing: .02em; text-transform: uppercase; }
    .item { margin-top: 12px; padding: 16px; border: 1px solid rgba(60,60,67,0.10); border-radius: 18px; background: rgba(255,255,255,0.76); box-shadow: var(--soft-shadow); }
    .item:first-of-type { margin-top: 0; }
    .item h3 { margin: 0 0 8px; font-size: 17px; line-height: 1.25; letter-spacing: -.015em; }
    .item p { margin: 0 0 10px; color: #2c2c2e; line-height: 1.58; }
    .meta { color: var(--muted); font-size: 12px; line-height: 1.45; }
    .evidence-strip { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
    .evidence-chip { display: inline-flex; max-width: 100%; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; background: rgba(0,113,227,.08); color: #1d1d1f; font-size: 12px; border: 1px solid rgba(0,113,227,.14); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .evidence-chip[data-kind="review"] { background: rgba(36,138,61,.10); border-color: rgba(36,138,61,.18); }
    .evidence-chip[data-kind="text"] { background: rgba(125,87,193,.10); border-color: rgba(125,87,193,.18); }
    .evidence-chip[data-kind="image"] { background: rgba(178,107,0,.10); border-color: rgba(178,107,0,.18); }
    .gallery { display: grid; gap: 12px; grid-template-columns: 1fr; }
    .gallery a { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 12px; align-items: center; min-height: 118px; padding: 10px; border: 1px solid var(--line); border-radius: 18px; text-decoration: none; color: var(--ink); background: rgba(255,255,255,0.84); box-shadow: var(--soft-shadow); transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease; }
    .gallery a:hover { transform: translateY(-2px); border-color: rgba(0,113,227,.25); box-shadow: 0 14px 28px rgba(0,0,0,.08); }
    .gallery img { width: 96px; height: 96px; object-fit: cover; border-radius: 14px; background: #f2f2f4; }
    .gallery strong { display: block; font-size: 15px; }
    details { margin-top: 10px; border: 1px solid rgba(60,60,67,0.10); border-radius: 16px; padding: 12px 14px; background: rgba(255,255,255,0.72); }
    details:first-of-type { margin-top: 0; }
    details[open] { background: rgba(255,255,255,0.90); }
    summary { cursor: pointer; font-weight: 650; color: var(--ink); }
    summary::marker { color: var(--blue); }
    @media (max-width: 1100px) { .span-8, .span-6, .span-4 { grid-column: span 12; } .span-4.card { position: static; } .gallery { grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); } }
    @media (max-width: 640px) { .page { padding: 16px; } .hero { padding: 22px; border-radius: 24px; } .card { padding: 16px; } .gallery a { grid-template-columns: 84px minmax(0, 1fr); } .gallery img { width: 84px; height: 84px; } }
  </style>"""

    def _render_enhancement_script(self) -> str:
        return """<script>
    document.querySelectorAll('.section-title').forEach((title) => {
      const card = title.closest('.card');
      const count = card ? card.querySelectorAll(':scope > .item, :scope > details').length : 0;
      if (count) title.dataset.count = `${count} items`;
    });

    document.querySelectorAll('.evidence-chip').forEach((chip) => {
      const text = chip.textContent.trim();
      const kind = text.split(':', 1)[0];
      if (['review', 'text', 'image', '图像', '文本'].includes(kind)) chip.dataset.kind = kind === '图像' ? 'image' : kind === '文本' ? 'text' : kind;
      chip.title = text;
    });
  </script>"""

    def _claim_attributions_for_source(self, report: dict, claim_source: str) -> list[dict]:
        return [
            attribution
            for attribution in report.get("claim_attributions", [])
            if isinstance(attribution, dict) and attribution.get("claim_source") == claim_source
        ]

    def _render_insight_list(
        self,
        items: list[dict],
        attributions: list[dict],
        evidence_nodes: dict[str, dict],
        labels: dict[str, str],
    ) -> str:
        if not items:
            return f"<p class=\"meta\">{labels['no_items']}</p>"
        return self._render_evidence_bound_items(
            items=items,
            attributions=attributions,
            title_key="label",
            body_builder=lambda item: str(item.get("summary") or ""),
            meta_builder=self._insight_meta_builder(labels),
            labels=labels,
            evidence_nodes=evidence_nodes,
        )

    def _insight_meta_builder(self, labels: dict[str, str]):
        def build(item: dict) -> str:
            owner = str(item.get("owner") or "")
            confidence_breakdown = item.get("confidence_breakdown") or {}
            confidence = confidence_breakdown.get("final_confidence", item.get("confidence", 0.0))
            return f"{labels['owner']}={html.escape(owner)} | {labels['confidence']}={float(confidence):.2f}"

        return build

    def _render_evidence_gap_list(
        self,
        items: list[dict],
        attributions: list[dict],
        evidence_nodes: dict[str, dict],
        labels: dict[str, str],
    ) -> str:
        if not items:
            return f"<p class=\"meta\">{labels['no_items']}</p>"
        return self._render_evidence_bound_items(
            items=items,
            attributions=attributions,
            title_key="label",
            body_builder=lambda item: str(item.get("summary") or ""),
            meta_builder=lambda item: f"{labels['owner']}={html.escape(str(item.get('owner') or ''))}",
            labels=labels,
            evidence_nodes=evidence_nodes,
        )

    def _render_suggestion_list(
        self,
        items: list[dict],
        attributions: list[dict],
        evidence_nodes: dict[str, dict],
        labels: dict[str, str],
    ) -> str:
        if not items:
            return f"<p class=\"meta\">{labels['no_suggestions']}</p>"
        return self._render_evidence_bound_items(
            items=items,
            attributions=attributions,
            title_key="suggestion",
            body_builder=lambda item: "; ".join(str(reason) for reason in (item.get("reason") or [])),
            meta_builder=lambda item: (
                f"{labels['type']}={html.escape(str(item.get('suggestion_type') or ''))}"
                f" | {labels['owner']}={html.escape(str(item.get('owner') or ''))}"
            ),
            labels=labels,
            evidence_nodes=evidence_nodes,
        )

    def _render_evidence_bound_items(
        self,
        items: list[dict],
        attributions: list[dict],
        title_key: str,
        body_builder,
        meta_builder,
        labels: dict[str, str],
        evidence_nodes: dict[str, dict],
    ) -> str:
        html_parts: list[str] = []
        paired_count = 0
        for item, attribution in zip(items, attributions, strict=False):
            html_parts.append(
                f"<div class='item'><h3>{html.escape(str(item.get(title_key) or ''))}</h3><p>{html.escape(body_builder(item))}</p><div class='meta'>{meta_builder(item)}</div>{self._render_evidence_refs(attribution, evidence_nodes, labels)}</div>"
            )
            paired_count += 1
        for item in items[paired_count:]:
            html_parts.append(
                f"<div class='item'><h3>{html.escape(str(item.get(title_key) or ''))}</h3><p>{html.escape(body_builder(item))}</p><div class='meta'>{meta_builder(item)}</div><div class='meta'>{labels['evidence']}={labels['no_evidence_refs']}</div></div>"
            )
        return "".join(html_parts)

    def _render_evidence_refs(self, attribution: dict | None, evidence_nodes: dict[str, dict], labels: dict[str, str]) -> str:
        if not isinstance(attribution, dict):
            return f"<div class='meta'>{labels['evidence']}={labels['no_evidence_refs']}</div>"
        support_ids = attribution.get("support_ids") or []
        refs = [
            self._evidence_ref_label(evidence_nodes.get(str(support_id)), labels)
            for support_id in support_ids
            if isinstance(support_id, str)
        ]
        refs = [ref for ref in refs if ref]
        if not refs:
            return f"<div class='meta'>{labels['evidence']}={labels['no_evidence_refs']}</div>"
        chips = "".join(f"<span class='evidence-chip'>{html.escape(ref)}</span>" for ref in refs)
        return f"<div class='evidence-strip' aria-label='{html.escape(labels['support'])}'>{chips}</div>"

    def _evidence_ref_label(self, node: dict | None, labels: dict[str, str]) -> str | None:
        if not isinstance(node, dict):
            return None
        source_type = str(node.get("source_type") or "")
        if source_type == "review":
            return f"review:{node.get('source_id')}"
        if source_type == "product_text":
            section = node.get("source_section") or "text"
            return f"{labels['text']}:{section}"
        if source_type == "product_image":
            region_label = node.get("region_label") or node.get("region_id")
            image_path = node.get("image_path") or node.get("source_id")
            if region_label:
                return f"{labels['image']}:{region_label} · {image_path}"
            return f"{labels['image']}:{image_path}"
        fallback = node.get("source_id") or node.get("evidence_node_id")
        return str(fallback) if fallback else None

    def _render_retrieval_quality(self, items: list[dict], labels: dict[str, str]) -> str:
        if not items:
            return f"<p class=\"meta\">{labels['no_retrieval_metrics']}</p>"
        return "".join(
            (
                f"<div class='item'><h3>{html.escape(str(item.get('source_aspect') or ''))}</h3>"
                f"<p>{labels['coverage']}={float(item.get('evidence_coverage', 0.0)):.2f}, {labels['drift']}={float(item.get('score_drift', 0.0)):.2f}, {labels['conflict']}={float(item.get('conflict_risk', 0.0)):.2f}</p>"
                f"<div class='meta'>{labels['text']}={bool(item.get('text_coverage'))} | {labels['image']}={bool(item.get('image_coverage'))}</div>"
                f"{self._render_retrieval_evaluator_meta(item, labels)}"
                f"</div>"
            )
            for item in items
        )

    def _render_retrieval_evaluator_meta(self, item: dict, labels: dict[str, str]) -> str:
        quality = item.get("retrieval_quality_label")
        reason = item.get("failure_reason")
        action = item.get("corrective_action")
        explanation = item.get("evaluator_explanation")

        if not any([quality, reason, action, explanation]):
            return ""

        summary_parts = []
        if quality:
            summary_parts.append(f"{labels['quality']}={html.escape(str(quality))}")
        if reason:
            summary_parts.append(f"{labels['reason']}={html.escape(str(reason))}")
        if action:
            summary_parts.append(f"{labels['action']}={html.escape(str(action))}")

        summary_html = f"<div class='meta'>{' | '.join(summary_parts)}</div>" if summary_parts else ""
        explanation_html = f"<div class='meta'>{html.escape(str(explanation))}</div>" if explanation else ""
        return f"{summary_html}{explanation_html}"

    def _render_retrieval_runtime(self, item: dict, labels: dict[str, str]) -> str:
        if not item:
            return f"<p class=\"meta\">{labels['no_runtime_profile']}</p>"
        return (
            f"<div class='item'><h3>{html.escape(str(item.get('summary') or ''))}</h3>"
            f"<div class='meta'>{labels['text_embedding']}={html.escape(str(item.get('text_embedding_backend') or ''))}:{html.escape(str(item.get('text_embedding_model') or ''))}</div>"
            f"<div class='meta'>{labels['image_embedding']}={html.escape(str(item.get('image_embedding_backend') or ''))}:{html.escape(str(item.get('image_embedding_model') or 'none'))}</div>"
            f"<div class='meta'>{labels['text_reranker']}={html.escape(str(item.get('reranker_backend') or ''))}:{html.escape(str(item.get('reranker_model') or ''))}</div>"
            f"<div class='meta'>{labels['multimodal_reranker']}={html.escape(str(item.get('multimodal_reranker_backend') or ''))}:{html.escape(str(item.get('multimodal_reranker_model') or 'none'))}</div>"
            f"<div class='meta'>{labels['native_multimodal_enabled']}={bool(item.get('native_multimodal_enabled'))}</div></div>"
        )

    def _render_trace(self, items: list[dict], labels: dict[str, str]) -> str:
        if not items:
            return f"<p class=\"meta\">{labels['no_trace']}</p>"
        return "".join(
            f"<details><summary>{html.escape(str(item.get('trace_type') or ''))} · {html.escape(str(item.get('aspect') or ''))}</summary><p>{html.escape(str(item.get('summary') or ''))}</p><div class='meta'>{labels['owner']}={html.escape(str(item.get('owner') or ''))}</div></details>"
            for item in items
        )

    def _render_gallery(self, images: list[dict], source_dir: str | None, labels: dict[str, str]) -> str:
        if not images:
            return f"<p class=\"meta\">{labels['no_images']}</p>"
        cards: list[str] = []
        root = Path(source_dir) if source_dir else None
        for item in images:
            image_path = str(item.get("image_path") or "")
            href = str((root / image_path).resolve()) if root is not None and image_path else image_path
            image_alt = image_path or str(item.get("variant") or "image")
            cards.append(
                f"<a href='{html.escape(href)}'><img src='{html.escape(href)}' alt='{html.escape(image_alt)}' loading='lazy' /><span><strong>{html.escape(str(item.get('variant') or 'image'))}</strong><div class='meta'>{html.escape(image_path)}</div></span></a>"
            )
        return f"<div class='gallery'>{''.join(cards)}</div>"
