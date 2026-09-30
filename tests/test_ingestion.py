from app.services.ingestion import parse_markdown, path_context, path_segments


def test_path_is_parsed_as_hierarchy():
    doc = parse_markdown(
        "demo.md",
        "Путь: Регистратура/Словарь/Лаборатория/Анализы_крови/ОАК\n\n# Общий анализ крови\n\nТекст",
    )
    assert doc.wiki_path == "Регистратура/Словарь/Лаборатория/Анализы_крови/ОАК"
    assert path_segments(doc.wiki_path) == [
        "Регистратура",
        "Словарь",
        "Лаборатория",
        "Анализы крови",
        "ОАК",
    ]
    assert path_context(doc.wiki_path).endswith("Лаборатория > Анализы крови > ОАК")


def test_missing_path_fails():
    import pytest
    with pytest.raises(ValueError):
        parse_markdown("bad.md", "# Нет пути\n\nТекст")
