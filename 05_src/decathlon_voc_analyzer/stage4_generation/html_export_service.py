from pathlib import Path
import html


class HtmlExportService:
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

        return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(str(product_name))} VOC Report</title>
  <style>
    :root {{
      --bg: #f4f5f7;
      --card: rgba(255,255,255,0.82);
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: rgba(23,32,42,0.08);
      --accent: #0f766e;
      --warm: #b45309;
      --danger: #b91c1c;
      --shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
      --radius: 24px;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: var(--ink); background: radial-gradient(circle at top left, #ffffff 0, #eef2f7 38%, #e6ebf1 100%); }}
    .page {{ max-width: 1240px; margin: 0 auto; padding: 36px 20px 72px; }}
    .hero {{ background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(240,247,246,0.88)); border: 1px solid var(--line); border-radius: 32px; padding: 36px; box-shadow: var(--shadow); }}
    .eyebrow {{ color: var(--accent); text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 700; }}
    h1 {{ margin: 8px 0 8px; font-size: clamp(32px, 4vw, 54px); line-height: 1.02; }}
    .sub {{ color: var(--muted); font-size: 15px; max-width: 820px; }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: repeat(12, 1fr); margin-top: 22px; }}
    .card {{ background: var(--card); backdrop-filter: blur(14px); border: 1px solid var(--line); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); }}
    .span-12 {{ grid-column: span 12; }} .span-8 {{ grid-column: span 8; }} .span-6 {{ grid-column: span 6; }} .span-4 {{ grid-column: span 4; }}
    .section-title {{ margin: 0 0 14px; font-size: 18px; }}
    .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(15,118,110,.1); color: var(--accent); font-size: 12px; font-weight: 700; margin-right: 8px; margin-bottom: 8px; }}
    .item {{ padding: 14px 0; border-top: 1px solid var(--line); }}
    .item:first-child {{ border-top: 0; padding-top: 0; }}
    .item h3 {{ margin: 0 0 6px; font-size: 16px; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .owner-product_issue {{ color: var(--danger); }}
    .owner-content_presentation {{ color: var(--warm); }}
    .owner-evidence_gap {{ color: #475569; }}
    .gallery {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); }}
    .gallery a {{ display:block; padding:12px; border:1px solid var(--line); border-radius:18px; text-decoration:none; color:var(--ink); background:#fff; }}
    details {{ border-top: 1px solid var(--line); padding: 12px 0; }}
    details:first-child {{ border-top: 0; }}
    summary {{ cursor: pointer; font-weight: 600; }}
    @media (max-width: 900px) {{ .span-8, .span-6, .span-4 {{ grid-column: span 12; }} .hero {{ padding: 24px; }} }}
  </style>
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
      <article class=\"card span-8\"><h2 class=\"section-title\">Strengths</h2>{self._render_insight_list(report.get('strengths', []))}</article>
      <article class=\"card span-4\"><h2 class=\"section-title\">Evidence Gallery</h2>{self._render_gallery(images, normalized_payload.get('source_dir'))}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">Weaknesses</h2>{self._render_insight_list(report.get('weaknesses', []))}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">Controversies</h2>{self._render_insight_list(report.get('controversies', []))}</article>
      <article class=\"card span-6\"><h2 class=\"section-title\">Suggestions</h2>{self._render_suggestion_list(report.get('suggestions', []))}</article>
    <article class=\"card span-6\"><h2 class=\"section-title\">Retrieval Judge</h2>{self._render_retrieval_quality(retrieval_quality)}</article>
    <article class=\"card span-12\"><h2 class=\"section-title\">Runtime Profile</h2>{self._render_retrieval_runtime(retrieval_runtime)}</article>
    <article class=\"card span-12\"><h2 class=\"section-title\">Process Drawer</h2>{self._render_trace(trace)}</article>
    </section>
  </main>
</body>
</html>"""

    def _render_insight_list(self, items: list[dict]) -> str:
        if not items:
            return "<p class=\"meta\">No items.</p>"
        html_parts: list[str] = []
        for item in items:
            owner = str(item.get("owner") or "")
            confidence = item.get("confidence_breakdown", {}).get("final_confidence", item.get("confidence", 0.0))
            html_parts.append(
                f"<div class='item'><h3>{html.escape(str(item.get('label') or ''))}</h3><p>{html.escape(str(item.get('summary') or ''))}</p><div class='meta owner-{html.escape(owner)}'>owner={html.escape(owner)} | confidence={float(confidence):.2f}</div></div>"
            )
        return "".join(html_parts)

    def _render_suggestion_list(self, items: list[dict]) -> str:
        if not items:
            return "<p class=\"meta\">No suggestions.</p>"
        html_parts: list[str] = []
        for item in items:
            owner = str(item.get("owner") or "")
            reasons = item.get("reason") or []
            html_parts.append(
                f"<div class='item'><h3>{html.escape(str(item.get('suggestion') or ''))}</h3><p>{html.escape('; '.join(str(reason) for reason in reasons))}</p><div class='meta owner-{html.escape(owner)}'>type={html.escape(str(item.get('suggestion_type') or ''))} | owner={html.escape(owner)}</div></div>"
            )
        return "".join(html_parts)

    def _render_retrieval_quality(self, items: list[dict]) -> str:
        if not items:
            return "<p class=\"meta\">No retrieval metrics.</p>"
        return "".join(
            f"<div class='item'><h3>{html.escape(str(item.get('source_aspect') or ''))}</h3><p>coverage={float(item.get('evidence_coverage', 0.0)):.2f}, drift={float(item.get('score_drift', 0.0)):.2f}, conflict={float(item.get('conflict_risk', 0.0)):.2f}</p><div class='meta'>text={bool(item.get('text_coverage'))} | image={bool(item.get('image_coverage'))}</div></div>"
            for item in items
        )

    def _render_retrieval_runtime(self, item: dict) -> str:
        if not item:
            return "<p class=\"meta\">No runtime profile.</p>"
        return (
            f"<div class='item'><h3>{html.escape(str(item.get('summary') or ''))}</h3>"
            f"<div class='meta'>text_embedding={html.escape(str(item.get('text_embedding_backend') or ''))}:{html.escape(str(item.get('text_embedding_model') or ''))}</div>"
            f"<div class='meta'>image_embedding={html.escape(str(item.get('image_embedding_backend') or ''))}:{html.escape(str(item.get('image_embedding_model') or 'none'))}</div>"
            f"<div class='meta'>text_reranker={html.escape(str(item.get('reranker_backend') or ''))}:{html.escape(str(item.get('reranker_model') or ''))}</div>"
            f"<div class='meta'>multimodal_reranker={html.escape(str(item.get('multimodal_reranker_backend') or ''))}:{html.escape(str(item.get('multimodal_reranker_model') or 'none'))}</div>"
            f"<div class='meta'>native_multimodal_enabled={bool(item.get('native_multimodal_enabled'))}</div></div>"
        )

    def _render_trace(self, items: list[dict]) -> str:
        if not items:
            return "<p class=\"meta\">No trace.</p>"
        return "".join(
            f"<details><summary>{html.escape(str(item.get('trace_type') or ''))} · {html.escape(str(item.get('aspect') or ''))}</summary><p>{html.escape(str(item.get('summary') or ''))}</p><div class='meta'>owner={html.escape(str(item.get('owner') or ''))}</div></details>"
            for item in items
        )

    def _render_gallery(self, images: list[dict], source_dir: str | None) -> str:
        if not images:
            return "<p class=\"meta\">No images available.</p>"
        cards: list[str] = []
        root = Path(source_dir) if source_dir else None
        for item in images:
            image_path = str(item.get("image_path") or "")
            href = str((root / image_path).resolve()) if root is not None and image_path else image_path
            cards.append(f"<a href='{html.escape(href)}'><strong>{html.escape(str(item.get('variant') or 'image'))}</strong><div class='meta'>{html.escape(image_path)}</div></a>")
        return f"<div class='gallery'>{''.join(cards)}</div>"