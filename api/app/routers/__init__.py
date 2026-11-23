"""FastAPI API routers for Enterprise RAG Ops Copilot."""

from app.routers.documents import router as documents_router
from app.routers.eval import router as eval_router
from app.routers.rag import router as rag_router
from app.routers.triage import router as triage_router

__all__ = ["documents_router", "eval_router", "rag_router", "triage_router"]
