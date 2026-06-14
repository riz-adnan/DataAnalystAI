from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.services.agent_orchestrator_service import handle_chat_query
from app.services.auth_service import get_current_project, get_required_database


router = APIRouter(prefix="/chat", tags=["chat"])


class ChatQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


@router.post("/query")
async def chat_query(
    payload: ChatQueryRequest,
    request: Request,
    project: dict[str, Any] = Depends(get_current_project),
) -> dict[str, Any]:
    database = get_required_database(request)
    return await handle_chat_query(database, str(project["_id"]), payload.question)
