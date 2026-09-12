"""Interview endpoints, including the SSE variant of the answer turn."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app.ai.llm import LLMError
from app.ai.tools import ToolError, ToolRunner
from app.ai.workflow import stream_answer_turn
from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Message
from app.schemas.interview import (
    AnswerSubmit,
    CompleteInterviewResponse,
    ImprovementPlanOut,
    InterviewCreate,
    InterviewDetail,
    InterviewOut,
    QuestionOut,
    StartInterviewResponse,
    TurnResponse,
)
from app.services import interviews as service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", response_model=StartInterviewResponse, status_code=status.HTTP_201_CREATED)
def start_interview(
    payload: InterviewCreate, user: CurrentUser, db: DbSession
) -> StartInterviewResponse:
    interview, question, events = service.start_interview(db, user, payload)
    return StartInterviewResponse(
        interview=InterviewOut.model_validate(interview),
        first_question=QuestionOut.model_validate(question),
        workflow_events=events,
    )


@router.get("", response_model=list[InterviewOut])
def list_interviews(user: CurrentUser, db: DbSession) -> list[InterviewOut]:
    return [
        InterviewOut.model_validate(i) for i in service.list_interviews(db, user.id)
    ]


@router.get("/{interview_id}", response_model=InterviewDetail)
def read_interview(
    interview_id: str, user: CurrentUser, db: DbSession
) -> InterviewDetail:
    interview = service.get_owned_interview(db, user.id, interview_id)
    return InterviewDetail.model_validate(service.build_detail(interview))


@router.get("/{interview_id}/question", response_model=QuestionOut | None)
def read_current_question(
    interview_id: str, user: CurrentUser, db: DbSession
) -> QuestionOut | None:
    interview = service.get_owned_interview(db, user.id, interview_id)
    question = service.current_question(interview)
    return QuestionOut.model_validate(question) if question else None


@router.post("/{interview_id}/answer", response_model=TurnResponse)
def submit_answer(
    interview_id: str, payload: AnswerSubmit, user: CurrentUser, db: DbSession
) -> TurnResponse:
    result = service.submit_answer(db, user, interview_id, payload)
    return TurnResponse.model_validate(result)


@router.post("/{interview_id}/answer/stream")
def submit_answer_streaming(
    interview_id: str, payload: AnswerSubmit, user: CurrentUser, db: DbSession
) -> StreamingResponse:
    """Server-sent events version of the answer turn.

    Emits one `step` event per workflow node so the UI can show progress
    (recording, evaluating, adapting), then a final `result` event carrying the
    same payload as the plain REST endpoint.
    """
    # Validate ownership and state before opening the stream, so genuine errors
    # are still ordinary HTTP status codes rather than an error inside a 200.
    interview = service.get_owned_interview(db, user.id, interview_id)
    service.assert_answerable(interview, payload.question_id, db)

    def event_stream() -> Iterator[str]:
        runner = ToolRunner(db, user.id, interview_id=interview_id)
        try:
            for node_name, _update, state in stream_answer_turn(
                runner,
                interview_id=interview_id,
                question_id=payload.question_id,
                answer_text=payload.answer_text,
                time_taken_seconds=payload.time_taken_seconds,
            ):
                events = state.get("events") or []
                yield _sse(
                    "step",
                    {
                        "node": node_name,
                        "message": events[-1] if events else node_name,
                    },
                )
            db.commit()
            result = service.turn_result(db, interview_id, state)
            yield _sse("result", json.loads(TurnResponse.model_validate(result).model_dump_json()))
        except (LLMError, ToolError) as exc:
            db.rollback()
            logger.exception("Streaming turn failed")
            yield _sse("error", {"detail": str(exc)})
        finally:
            yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/{interview_id}/complete", response_model=CompleteInterviewResponse)
def complete_interview(
    interview_id: str, user: CurrentUser, db: DbSession
) -> CompleteInterviewResponse:
    interview, plan = service.complete_interview(db, user, interview_id)
    return CompleteInterviewResponse(
        interview=InterviewOut.model_validate(interview),
        improvement_plan=ImprovementPlanOut.model_validate(plan),
    )


@router.post("/{interview_id}/abandon", response_model=InterviewOut)
def abandon_interview(
    interview_id: str, user: CurrentUser, db: DbSession
) -> InterviewOut:
    return InterviewOut.model_validate(
        service.abandon_interview(db, user, interview_id)
    )


@router.get("/{interview_id}/plan", response_model=ImprovementPlanOut)
def read_plan(
    interview_id: str, user: CurrentUser, db: DbSession
) -> ImprovementPlanOut:
    plan = service.get_plan(db, user, interview_id)
    return ImprovementPlanOut.model_validate(plan)


@router.delete("/{interview_id}", response_model=Message)
def delete_interview(interview_id: str, user: CurrentUser, db: DbSession) -> Message:
    service.delete_interview(db, user, interview_id)
    return Message(detail="Interview deleted")
