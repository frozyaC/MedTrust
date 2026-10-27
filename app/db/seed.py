import hashlib
import logging
from pathlib import Path

from app.core.config import get_settings
from app.db.repository import KnowledgeRepository
from app.services.ingestion import parse_zip

logger = logging.getLogger(__name__)


def seed_knowledge_index() -> None:
    settings = get_settings()
    archive = Path(settings.knowledge_index_archive)
    if not archive.is_file():
        logger.warning("Knowledge archive not found: %s", archive.resolve())
        return

    data = archive.read_bytes()
    archive_hash = hashlib.sha256(data).hexdigest()
    repo = KnowledgeRepository()
    document_count = repo.document_count()
    stored_hash = repo.get_index_archive_hash()
    if document_count > 0 and stored_hash == archive_hash:
        logger.info("Knowledge index is up to date (%s documents)", document_count)
        return

    logger.info("Indexing knowledge archive %s", archive)
    stats = repo.reindex(parse_zip(data))
    repo.save_index_archive_hash(archive_hash)
    logger.info(
        "Knowledge index ready: %s documents, %s chunks",
        stats["documents"],
        stats["chunks"],
    )
