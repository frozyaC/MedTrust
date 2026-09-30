from fastapi import FastAPI

from app.api.routes import router
from app.db.database import init_db

app = FastAPI(
    title="MedTrust Path-Aware RAG API",
    version="0.1.0",
)
app.include_router(router)


@app.on_event("startup")
def startup() -> None:
    init_db()
