"""FastAPI application. Run with: uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.rag.store import get_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm up once so the first /ask during the demo is fast.
    store = get_store()
    try:
        from app.bootstrap import ensure_local_data
    except ImportError:
        log.info("Student-data bootstrap is pending team integration")
    else:
        ensure_local_data(store)
    settings = get_settings()
    log.info("RAG ready: %d chunks, collection=%s, embeddings=%s",
             store.count(), settings.chroma_collection, settings.embedding_provider)
    yield


app = FastAPI(title="University Student Services Assistant",
              description="Grounded answers from official university documents and student records.",
              version="1.0.0", lifespan=lifespan)
app.include_router(router)
