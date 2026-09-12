"""The adaptive interview workflow, orchestrated with LangGraph.

The graph is deliberately *controlled*: every edge is either unconditional or
decided by a pure Python function over the state. The model chooses the content
of questions and the grading of answers; it never chooses the control flow, and
it never touches the database except through `app.ai.tools.ToolRunner`.

    start_interview_graph:
        load_context -> plan_questions -> ask_first_question -> END

    answer_turn_graph:
        load_context -> record_answer -> evaluate -> update_state
                     -> (decide) -> generate_follow_up ---> END
                                 -> next_planned_question -> END
                                 -> finalize --------------> END
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import InterviewContext
from app.ai.schemas import AnswerEvaluation, GeneratedQuestion
from app.ai.tools import ToolRunner
from app.models.enums import (
    AnswerQuality,
    Difficulty,
    InterviewStatus,
    QuestionCategory,
)
from app.models.interview import Evaluation, Interview, InterviewQuestion

logger = logging.getLogger(__name__)

# A follow-up never triggers another follow-up, and at most this fraction of the
# planned interview length may be spent on them.
FOLLOW_UP_BUDGET_RATIO = 0.5


class TurnState(TypedDict, total=False):
    """State passed between graph nodes for a single interview turn.

    `_runner` must be declared here: LangGraph derives its state channels from
    these annotations and silently drops any key that is not one of them.
    """

    # the request-scoped tool surface (carries the db session and acting user)
    _runner: Any

    # inputs
    interview_id: str
    user_id: str
    question_id: str
    answer_text: str
    time_taken_seconds: int | None

    # populated by nodes
    ctx: InterviewContext
    answer_id: str
    evaluation: AnswerEvaluation
    next_question_id: str | None
    finished: bool
    progress: dict[str, Any]
    events: list[str]


def _runner(state: TurnState) -> ToolRunner:
    return state["_runner"]


def _emit(state: TurnState, message: str) -> list[str]:
    return [*state.get("events", []), message]


# --------------------------------------------------------------------------- #
# Shared nodes
# --------------------------------------------------------------------------- #


def node_load_context(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    db = runner.db
    interview = db.get(Interview, state["interview_id"])
    if interview is None:
        raise ValueError("Interview not found")
    ctx = runner.build_context(job_id=interview.job_description_id)
    return {"ctx": ctx, "events": _emit(state, "Loaded candidate profile and job context")}


# --------------------------------------------------------------------------- #
# Start-interview graph
# --------------------------------------------------------------------------- #


def node_plan_questions(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    db = runner.db
    interview = db.get(Interview, state["interview_id"])
    assert interview is not None

    question_set = runner.generate_interview_question_set(
        ctx=state["ctx"],
        count=interview.planned_question_count,
        difficulty=Difficulty(interview.current_difficulty),
        seed=interview.id,
    )

    plan = [q.model_dump(mode="json") for q in question_set.questions]
    snapshot = dict(interview.context_snapshot or {})
    snapshot.update(
        {
            "candidate_block": state["ctx"].candidate_block,
            "job_block": state["ctx"].job_block,
            "job_title": state["ctx"].job_title,
            "plan": plan,
            "planned_total": len(plan),
            "follow_ups_used": 0,
        }
    )
    # JSON columns are not mutation-tracked, so reassign rather than mutate.
    interview.context_snapshot = snapshot
    interview.planned_question_count = len(plan)
    db.flush()

    return {
        "events": _emit(state, f"Generated {len(plan)} grounded questions"),
    }


def node_ask_first_question(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    question = _pop_planned_question(runner.db, state["interview_id"])
    if question is None:
        raise ValueError("Question planning produced no questions")
    row = runner.save_question(
        interview_id=state["interview_id"], question=question, position=1
    )
    return {
        "next_question_id": row.id,
        "finished": False,
        "events": _emit(state, "Asked the opening question"),
    }


# --------------------------------------------------------------------------- #
# Answer-turn graph
# --------------------------------------------------------------------------- #


def node_record_answer(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    answer = runner.save_answer(
        interview_id=state["interview_id"],
        question_id=state["question_id"],
        answer_text=state["answer_text"],
        time_taken_seconds=state.get("time_taken_seconds"),
    )
    return {"answer_id": answer.id, "events": _emit(state, "Recorded the answer")}


def node_evaluate(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    db = runner.db
    question = db.get(InterviewQuestion, state["question_id"])
    assert question is not None

    evaluation = runner.evaluate_answer(
        question_text=question.question_text,
        category=question.category,
        difficulty=question.difficulty,
        expected_points=list(question.expected_points or []),
        answer_text=state["answer_text"],
        job_title=state["ctx"].job_title,
    )
    runner.save_evaluation(
        interview_id=state["interview_id"],
        answer_id=state["answer_id"],
        evaluation=evaluation,
    )
    return {
        "evaluation": evaluation,
        "events": _emit(state, f"Scored the answer {evaluation.score}/10"),
    }


def node_update_state(state: TurnState) -> dict[str, Any]:
    """Adjust difficulty from the answer quality and recompute progress."""
    runner = _runner(state)
    db = runner.db
    interview = db.get(Interview, state["interview_id"])
    assert interview is not None

    quality = state["evaluation"].quality
    delta = {
        AnswerQuality.STRONG: 1,
        AnswerQuality.ADEQUATE: 0,
        AnswerQuality.WEAK: -1,
        AnswerQuality.INCOMPLETE: -1,
    }[quality]
    current = Difficulty(interview.current_difficulty)
    interview.current_difficulty = Difficulty.from_rank(current.rank + delta).value
    db.flush()

    snapshot = dict(interview.context_snapshot or {})
    remaining = len(snapshot.get("plan", []))
    asked = db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.interview_id == interview.id
        )
    ).scalars().all()
    answered = sum(1 for q in asked if q.answer is not None)

    return {
        "progress": {
            "answered": answered,
            "planned_total": snapshot.get("planned_total", interview.planned_question_count),
            "remaining_in_plan": remaining,
            "current_difficulty": interview.current_difficulty,
        },
        "events": _emit(
            state, f"Difficulty is now {interview.current_difficulty}"
        ),
    }


def decide_next_step(
    state: TurnState,
) -> Literal["generate_follow_up", "next_planned_question", "finalize"]:
    """Pure routing decision - the model never makes this call."""
    runner = _runner(state)
    db = runner.db
    interview = db.get(Interview, state["interview_id"])
    assert interview is not None

    snapshot = dict(interview.context_snapshot or {})
    plan_remaining = len(snapshot.get("plan", []))
    follow_ups_used = int(snapshot.get("follow_ups_used", 0))
    planned_total = int(snapshot.get("planned_total", interview.planned_question_count))
    budget = int(planned_total * FOLLOW_UP_BUDGET_RATIO)

    current_question = db.get(InterviewQuestion, state["question_id"])
    is_follow_up = current_question is not None and current_question.follow_up_to_id

    quality = state["evaluation"].quality
    # A follow-up is worth asking when the previous answer left something
    # specific to chase, and we have not already chained one.
    wants_follow_up = quality in (
        AnswerQuality.STRONG,
        AnswerQuality.WEAK,
        AnswerQuality.INCOMPLETE,
    )

    if wants_follow_up and not is_follow_up and follow_ups_used < budget:
        return "generate_follow_up"
    if plan_remaining > 0:
        return "next_planned_question"
    return "finalize"


def node_generate_follow_up(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    db = runner.db
    interview = db.get(Interview, state["interview_id"])
    previous = db.get(InterviewQuestion, state["question_id"])
    assert interview is not None and previous is not None

    covered = [
        q.topic
        for q in db.execute(
            select(InterviewQuestion).where(
                InterviewQuestion.interview_id == interview.id
            )
        ).scalars().all()
    ]

    question = runner.generate_follow_up(
        ctx=state["ctx"],
        previous_question=previous.question_text,
        previous_answer=state["answer_text"],
        evaluation=state["evaluation"],
        target_difficulty=Difficulty(interview.current_difficulty),
        covered_topics=covered,
        previous_topic=previous.topic,
        previous_category=QuestionCategory(previous.category),
        seed=f"{interview.id}:{previous.id}",
    )

    row = runner.save_question(
        interview_id=interview.id,
        question=question,
        position=_next_position(db, interview.id),
        follow_up_to_id=previous.id,
    )

    snapshot = dict(interview.context_snapshot or {})
    snapshot["follow_ups_used"] = int(snapshot.get("follow_ups_used", 0)) + 1
    interview.context_snapshot = snapshot
    db.flush()

    return {
        "next_question_id": row.id,
        "finished": False,
        "events": _emit(
            state, f"Adapted: asking a {state['evaluation'].quality.value} follow-up"
        ),
    }


def node_next_planned_question(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    db = runner.db
    question = _pop_planned_question(db, state["interview_id"])
    if question is None:
        return node_finalize(state)

    # Keep the planned question in step with the adapted difficulty.
    interview = db.get(Interview, state["interview_id"])
    assert interview is not None
    question = question.model_copy(
        update={"difficulty": Difficulty(interview.current_difficulty)}
    )

    row = runner.save_question(
        interview_id=state["interview_id"],
        question=question,
        position=_next_position(db, state["interview_id"]),
    )
    return {
        "next_question_id": row.id,
        "finished": False,
        "events": _emit(state, "Moved to the next planned question"),
    }


def node_finalize(state: TurnState) -> dict[str, Any]:
    runner = _runner(state)
    db = runner.db
    interview = db.get(Interview, state["interview_id"])
    assert interview is not None

    scores = db.execute(
        select(Evaluation.score).where(Evaluation.interview_id == interview.id)
    ).scalars().all()
    interview.overall_score = round(sum(scores) / len(scores), 2) if scores else None
    interview.status = InterviewStatus.COMPLETED.value
    db.flush()

    return {
        "next_question_id": None,
        "finished": True,
        "events": _emit(state, "Interview complete"),
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _next_position(db: Session, interview_id: str) -> int:
    positions = db.execute(
        select(InterviewQuestion.position).where(
            InterviewQuestion.interview_id == interview_id
        )
    ).scalars().all()
    return (max(positions) + 1) if positions else 1


def _pop_planned_question(db: Session, interview_id: str) -> GeneratedQuestion | None:
    """Take the next question off the stored plan, persisting the shortened plan."""
    interview = db.get(Interview, interview_id)
    assert interview is not None
    snapshot = dict(interview.context_snapshot or {})
    plan = list(snapshot.get("plan", []))
    if not plan:
        return None
    head, rest = plan[0], plan[1:]
    snapshot["plan"] = rest
    interview.context_snapshot = snapshot
    db.flush()
    return GeneratedQuestion.model_validate(head)


# --------------------------------------------------------------------------- #
# Graph construction
# --------------------------------------------------------------------------- #


def _build_start_graph():
    graph = StateGraph(TurnState)
    graph.add_node("load_context", node_load_context)
    graph.add_node("plan_questions", node_plan_questions)
    graph.add_node("ask_first_question", node_ask_first_question)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "plan_questions")
    graph.add_edge("plan_questions", "ask_first_question")
    graph.add_edge("ask_first_question", END)
    return graph.compile()


def _build_turn_graph():
    graph = StateGraph(TurnState)
    graph.add_node("load_context", node_load_context)
    graph.add_node("record_answer", node_record_answer)
    graph.add_node("evaluate", node_evaluate)
    graph.add_node("update_state", node_update_state)
    graph.add_node("generate_follow_up", node_generate_follow_up)
    graph.add_node("next_planned_question", node_next_planned_question)
    graph.add_node("finalize", node_finalize)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "record_answer")
    graph.add_edge("record_answer", "evaluate")
    graph.add_edge("evaluate", "update_state")
    graph.add_conditional_edges(
        "update_state",
        decide_next_step,
        {
            "generate_follow_up": "generate_follow_up",
            "next_planned_question": "next_planned_question",
            "finalize": "finalize",
        },
    )
    graph.add_edge("generate_follow_up", END)
    graph.add_edge("next_planned_question", END)
    graph.add_edge("finalize", END)
    return graph.compile()


START_GRAPH = _build_start_graph()
TURN_GRAPH = _build_turn_graph()


def run_start_interview(runner: ToolRunner, interview_id: str) -> TurnState:
    state: dict[str, Any] = {
        "interview_id": interview_id,
        "user_id": runner.user_id,
        "events": [],
        "_runner": runner,
    }
    return START_GRAPH.invoke(state)  # type: ignore[return-value]


def _turn_state(
    runner: ToolRunner,
    interview_id: str,
    question_id: str,
    answer_text: str,
    time_taken_seconds: int | None,
) -> dict[str, Any]:
    return {
        "interview_id": interview_id,
        "user_id": runner.user_id,
        "question_id": question_id,
        "answer_text": answer_text,
        "time_taken_seconds": time_taken_seconds,
        "events": [],
        "_runner": runner,
    }


def run_answer_turn(
    runner: ToolRunner,
    interview_id: str,
    question_id: str,
    answer_text: str,
    time_taken_seconds: int | None = None,
) -> TurnState:
    state = _turn_state(
        runner, interview_id, question_id, answer_text, time_taken_seconds
    )
    return TURN_GRAPH.invoke(state)  # type: ignore[return-value]


def stream_answer_turn(
    runner: ToolRunner,
    interview_id: str,
    question_id: str,
    answer_text: str,
    time_taken_seconds: int | None = None,
) -> Iterator[tuple[str, dict[str, Any], TurnState]]:
    """Run a turn, yielding `(node_name, update, accumulated_state)` per node.

    Backs the SSE endpoint so the client can show the workflow progressing
    instead of staring at one long request.
    """
    state = _turn_state(
        runner, interview_id, question_id, answer_text, time_taken_seconds
    )
    accumulated: dict[str, Any] = dict(state)
    for chunk in TURN_GRAPH.stream(state, stream_mode="updates"):
        for node_name, update in chunk.items():
            if isinstance(update, dict):
                accumulated.update(update)
            yield node_name, update or {}, accumulated  # type: ignore[misc]
