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