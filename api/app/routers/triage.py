"""Synchronous FastAPI route handler for Pydantic v2 Support Ticket Triage."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.triage import TriageTicketRequest, TriageTicketResponse
from app.services.triage_service import TicketTriageService

router = APIRouter(prefix="/api/v1", tags=["triage"])


@router.post("/triage", response_model=TriageTicketResponse)
def triage_ticket(payload: TriageTicketRequest, request: Request) -> TriageTicketResponse:
    """Classify and persist an inbound Thai-English support ticket (sync threadpool)."""
    triage_service: TicketTriageService = request.app.state.triage_service
    return triage_service.triage(payload)
