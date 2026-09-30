from pathlib import Path
import zipfile

from app.services.ingestion import parse_zip


def test_sample_zip_has_path_metadata():
    data = Path("data/sample_sufler.zip").read_bytes()
    docs = parse_zip(data)
    assert len(docs) == 26
    assert any(doc.wiki_path.endswith("Травмпункт") for doc in docs)
    assert any("Скрипты" in doc.path_segments for doc in docs)
