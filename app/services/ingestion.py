import hashlib
import io
import re
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.config import get_settings

NAMESPACE = uuid.UUID("f8f94c68-6d74-4bcb-8ce6-dc2a9f0a79b7")


@dataclass
class ParsedDocument:
    source_key: str
    filename: str
    title: str
    wiki_path: str
    path_segments: list[str]
    source_url: str | None
    content_hash: str
    sections: list[tuple[str, str]]


def _clean(value: str) -> str:
    value = value.replace("\u00a0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def normalize_wiki_path(path: str) -> str:
    path = path.strip().replace("\\", "/")
    path = re.sub(r"/+", "/", path)
    return path.strip("/")


def path_segments(path: str) -> list[str]:
    return [_clean(part.replace("_", " ")) for part in normalize_wiki_path(path).split("/") if part.strip()]


def path_context(path: str) -> str:
    return " > ".join(path_segments(path))


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if re.match(r"^#\s+", line):
            return _clean(re.sub(r"^#\s+", "", line))
        if re.match(r"^==\s*\\*\\*.*", line):
            candidate = re.sub(r"^==|==.*$", "", line).strip("* ")
            if candidate:
                return _clean(candidate)
    return fallback


def _split_by_sections(body: str) -> list[tuple[str, str]]:
    lines = body.splitlines()
    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        text = "\n".join(current).strip()
        if text:
            section = " > ".join(heading_stack)
            sections.append((section, text))
        current = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if match:
            flush()
            level = len(match.group(1))
            heading = _clean(match.group(2))
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading)
            current.append(line)
        else:
            current.append(line)

    flush()
    return sections or [("", body.strip())]


def _split_long_text(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= size:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(paragraph) <= size:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + size, len(paragraph))
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(paragraph):
                current = ""
                break
            start = max(0, end - overlap)

    if current:
        chunks.append(current)

    return chunks


def parse_markdown(filename: str, raw_text: str) -> ParsedDocument:
    match = re.search(r"^Путь:\s*(.+)$", raw_text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"В документе {filename!r} отсутствует обязательное поле 'Путь:'")

    wiki_path = normalize_wiki_path(match.group(1))
    segments = path_segments(wiki_path)
    fallback_title = segments[-1] if segments else PurePosixPath(filename).stem
    title = _extract_title(raw_text, fallback_title)

    # `Путь:` is metadata, not article content.
    body = re.sub(r"^Путь:\s*.+$", "", raw_text, count=1, flags=re.MULTILINE).strip()
    sections = _split_by_sections(body)
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    source_key = wiki_path

    return ParsedDocument(
        source_key=source_key,
        filename=filename,
        title=title,
        wiki_path=wiki_path,
        path_segments=segments,
        source_url=None,
        content_hash=content_hash,
        sections=sections,
    )


def parse_zip(data: bytes) -> list[ParsedDocument]:
    documents: list[ParsedDocument] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".md"):
                continue
            raw = archive.read(info).decode("utf-8", errors="replace")
            # Some Windows zip exports contain unicode path names encoded as #UXXXX.
            filename = re.sub(
                r"#U([0-9A-Fa-f]{4})",
                lambda m: chr(int(m.group(1), 16)),
                info.filename,
            )
            documents.append(parse_markdown(filename, raw))

    if not documents:
        raise ValueError("В архиве нет Markdown-документов")
    return documents


def build_chunks(document: ParsedDocument) -> list[dict]:
    settings = get_settings()
    path_ctx = path_context(document.wiki_path)
    result: list[dict] = []
    chunk_index = 0

    for section, text in document.sections:
        for part in _split_long_text(text, settings.chunk_size_chars, settings.chunk_overlap_chars):
            embedding_text = (
                f"Путь: {path_ctx}\n"
                f"Название: {document.title}\n"
                f"Раздел: {section}\n"
                f"Содержание:\n{part}"
            )
            result.append(
                {
                    "chunk_index": chunk_index,
                    "section": section,
                    "content": part,
                    "embedding_text": embedding_text,
                    "document_id": str(uuid.uuid5(NAMESPACE, document.source_key)),
                }
            )
            chunk_index += 1

    return result
