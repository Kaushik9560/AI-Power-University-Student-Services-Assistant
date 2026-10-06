"""FastAPI application. Run with: uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import settings
from app.bootstrap import ensure_local_data
from app.rag.store import get_store
from app.services.llm import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm up once so the first /ask during the demo is fast.
    store = get_store()
    ensure_local_data(store)
    llm = get_llm()
    log.info("Ready: %d chunks, collection=%s, db=%s, llm=%s/%s, embeddings=%s",
             store.count(), settings.CHROMA_COLLECTION, settings.SQLITE_PATH,
             llm.name, llm.model, settings.EMBEDDING_PROVIDER)
    yield


app = FastAPI(title="University Student Services Assistant",
              description="Grounded answers from official university documents and student records.",
              version="1.0.0", lifespan=lifespan)
app.include_router(router)
