"""Dashboard and administrator endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentAdmin, CurrentUser, DbSession
from app.models.interview import ToolLog
from app.schemas.auth import UserOut
from app.schemas.interview import DashboardResponse
from app.services import dashboard as service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def read_dashboard(user: CurrentUser, db: DbSession) -> DashboardResponse:
    return DashboardResponse.model_validate(service.build_dashboard(db, user.id))


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/overview")
def admin_overview(_: CurrentAdmin, db: DbSession) -> dict[str, Any]:
    return service.admin_overview(db)


@admin_router.get("/users", response_model=list[UserOut])
def admin_list_users(_: CurrentAdmin, db: DbSession) -> list[UserOut]:
    from app.models.user import User

    users = db.execute(select(User).order_by(User.created_at.desc())).scalars()
    return [UserOut.model_validate(u) for u in users]


@admin_router.get("/tool-logs")
def admin_tool_logs(
    _: CurrentAdmin,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """The AI tool audit trail - every tool call the workflow has made."""
    logs = db.execute(
        select(ToolLog).order_by(ToolLog.created_at.desc()).limit(limit)
    ).scalars()
    return [
        {
            "id": log.id,
            "created_at": log.created_at,
            "user_id": log.user_id,
            "interview_id": log.interview_id,
            "tool_name": log.tool_name,
            "arguments": log.arguments,
            "result_summary": log.result_summary,
            "duration_ms": log.duration_ms,
            "ok": log.ok,
            "error": log.error,
        }
        for log in logs
    ]
