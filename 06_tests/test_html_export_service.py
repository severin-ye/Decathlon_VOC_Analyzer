from decathlon_voc_analyzer.stage4_generation.html_export_service import HtmlExportService


def test_html_export_service_uses_english_lang_for_main_variant(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")

    html = HtmlExportService().render(
        analysis_payload={"report": {"product_id": "backpack_010", "answer": "Good for travel."}},
        normalized_payload={"product_name": "Travel Backpack", "images": []},
    )

    assert '<html lang="en">' in html
    assert "VOC Report" in html
    assert ">Strengths<" in html
    assert "No images available." in html


def test_html_export_service_uses_chinese_lang_for_cn_variant(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "zh-cn")

    html = HtmlExportService().render(
        analysis_payload={"report": {"product_id": "backpack_010", "answer": "适合通勤。"}},
        normalized_payload={"product_name": "通勤背包", "images": []},
    )

    assert '<html lang="zh-CN">' in html
    assert "VOC 报告" in html
    assert ">优势<" in html
    assert "暂无图片证据。" in html


def test_html_export_service_renders_evidence_gap_and_region_level_support(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")

    html = HtmlExportService().render(
        analysis_payload={
            "report": {
                "product_id": "sunglasses_010",
                "answer": "Lens tinting is supported by text and image evidence.",
                "evidence_gaps": [
                    {
                        "label": "Tint substantiation gap",
                        "summary": "The page still lacks explicit tint hue naming.",
                        "owner": "content_presentation",
                    }
                ],
                "suggestions": [
                    {
                        "suggestion": "Add a front-facing tinted lens image.",
                        "reason": ["Current tint claim needs direct visual support."],
                        "suggestion_type": "perception",
                        "owner": "content_presentation",
                    }
                ],
                "evidence_nodes": [
                    {
                        "evidence_node_id": "review_1_chunk_00",
                        "source_type": "review",
                        "source_id": "review_1",
                        "modality": "text",
                    },
                    {
                        "evidence_node_id": "img_region_1_visual",
                        "source_type": "product_image",
                        "source_id": "image_1",
                        "modality": "visual",
                        "region_id": "img_region_1",
                        "region_label": "upper_focus",
                        "image_path": "images/img2.png",
                    },
                ],
                "claim_attributions": [
                    {
                        "claim_id": "evidence_gap:tint_gap:0",
                        "claim_source": "evidence_gap",
                        "support_ids": ["review_1_chunk_00"],
                    },
                    {
                        "claim_id": "suggestion:tint_suggestion:0",
                        "claim_source": "suggestion",
                        "support_ids": ["review_1_chunk_00", "img_region_1_visual"],
                    },
                ],
            }
        },
        normalized_payload={"product_name": "Sports Sunglasses", "images": []},
    )

    assert ">Evidence Gaps<" in html
    assert "Tint substantiation gap" in html
    assert "Add a front-facing tinted lens image." in html
    assert "review:review_1" in html
    assert "image:upper_focus · images/img2.png" in html


def test_html_export_service_renders_insight_support_refs(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")

    html = HtmlExportService().render(
        analysis_payload={
            "report": {
                "product_id": "sunglasses_010",
                "answer": "Summary.",
                "strengths": [
                    {
                        "label": "positive lens tinting perception",
                        "summary": "Tinting is supported by text and image evidence.",
                        "owner": "product_issue",
                        "confidence": 0.89,
                    }
                ],
                "weaknesses": [
                    {
                        "label": "Rubber insert durability failure",
                        "summary": "A user reports long-term failure.",
                        "owner": "product_issue",
                        "confidence": 0.78,
                    }
                ],
                "evidence_nodes": [
                    {
                        "evidence_node_id": "review_1_chunk_00",
                        "source_type": "review",
                        "source_id": "review_1",
                        "modality": "text",
                    },
                    {
                        "evidence_node_id": "text_1_chunk_00",
                        "source_type": "product_text",
                        "source_id": "text_1",
                        "modality": "text",
                        "source_section": "model_description",
                    },
                    {
                        "evidence_node_id": "img_region_1_visual",
                        "source_type": "product_image",
                        "source_id": "image_1",
                        "modality": "visual",
                        "region_label": "upper_focus",
                        "image_path": "images/img2.png",
                    },
                ],
                "claim_attributions": [
                    {
                        "claim_id": "strength:lens_tinting_issue:0",
                        "claim_source": "strength",
                        "support_ids": ["review_1_chunk_00", "text_1_chunk_00", "img_region_1_visual"],
                    },
                    {
                        "claim_id": "weakness:rubber_insert_durability_issue:0",
                        "claim_source": "weakness",
                        "support_ids": ["review_1_chunk_00"],
                    },
                ],
            }
        },
        normalized_payload={"product_name": "Sports Sunglasses", "images": []},
    )

    assert "Tinting is supported by text and image evidence." in html
    assert "text:model_description" in html
    assert "image:upper_focus · images/img2.png" in html
    assert "A user reports long-term failure." in html
    assert "review:review_1" in html


def test_html_export_service_renders_retrieval_evaluator_fields(monkeypatch) -> None:
    monkeypatch.setenv("PROMPT_VARIANT", "en")

    html = HtmlExportService().render(
        analysis_payload={
            "report": {
                "product_id": "sunglasses_010",
                "answer": "Summary.",
            },
            "retrieval_quality": [
                {
                    "source_aspect": "lens tinting",
                    "evidence_coverage": 0.5,
                    "score_drift": 0.41,
                    "conflict_risk": 0.0,
                    "text_coverage": True,
                    "image_coverage": False,
                    "retrieval_quality_label": "mixed",
                    "failure_reason": "modality_miss",
                    "corrective_action": "add_multimodal_route",
                    "evaluator_explanation": "Expected route coverage is incomplete; add or recover the missing route(s): image.",
                }
            ],
        },
        normalized_payload={"product_name": "Sports Sunglasses", "images": []},
    )

    assert "quality=mixed" in html
    assert "reason=modality_miss" in html
    assert "action=add_multimodal_route" in html
    assert "Expected route coverage is incomplete" in html