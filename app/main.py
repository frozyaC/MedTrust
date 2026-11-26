import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.routes import admin_router, public_router, router
from app.core.auth import allowed_origins
from app.core.config import get_settings
from app.db.database import init_db
from app.db.seed import seed_knowledge_index

logger = logging.getLogger(__name__)

app = FastAPI(
    title="MedTrust Path-Aware RAG API",
    version="0.1.0",
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(admin_router)
app.include_router(public_router)
app.include_router(auth_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    try:
        seed_knowledge_index()
    except Exception:
        logger.exception("Failed to seed knowledge index")
