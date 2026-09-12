"""Dashboard aggregation."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import InterviewStatus
from app.models.interview import (
    Answer,
    Evaluation,
    ImprovementPlan,
    Interview,
    InterviewQuestion,
)

# A topic needs at least this many graded answers before it is reported as a
# strength or a weakness - one answer is noise, not a trend.
MIN_ANSWERS_PER_TOPIC = 1
WEAK_TOPIC_THRESHOLD = 6.5


def build_dashboard(db: Session, user_id: str) -> dict:
    interviews = list(
        db.execute(
            select(Interview)
            .where(Interview.user_id == user_id)
            .order_by(Interview.created_at.desc())
        ).scalars()
    )
    completed = [i for i in interviews if i.status == InterviewStatus.COMPLETED.value]

    # One row per graded answer, joined to its question for the topic label.
    rows = db.execute(
        select(
            InterviewQuestion.topic,
            Evaluation.score,
            Evaluation.correctness,
            Evaluation.relevance,
            Evaluation.clarity,
            Evaluation.completeness,
            Evaluation.communication,
        )
        .select_from(Evaluation)
        .join(Answer, Answer.id == Evaluation.answer_id)
        .join(InterviewQuestion, InterviewQuestion.id == Answer.question_id)
        .join(Interview, Interview.id == Evaluation.interview_id)
        .where(Interview.user_id == user_id)
    ).all()

    total_answers = len(rows)
    average_score = (
        round(sum(r.score for r in rows) / total_answers, 2) if total_answers else None
    )

    rubric_averages = None
    if total_answers:
        rubric_averages = {
            key: round(sum(getattr(r, key) for r in rows) / total_answers, 2)
            for key in (
                "correctness",
                "relevance",
                "clarity",
                "completeness",
                "communication",
            )
        }

    by_topic: dict[str, list[int]] = {}
    for row in rows:
        by_topic.setdefault(row.topic or "general", []).append(row.score)

    topic_performance = [
        {
            "topic": topic,
            "average_score": round(sum(scores) / len(scores), 2),
            "answer_count": len(scores),
        }
        for topic, scores in by_topic.items()
        if len(scores) >= MIN_ANSWERS_PER_TOPIC
    ]
    topic_performance.sort(key=lambda t: t["average_score"])

    weak_topics = [t for t in topic_performance if t["average_score"] < WEAK_TOPIC_THRESHOLD][:6]
    strongest_topics = list(reversed(topic_performance))[:6]

    progress = [
        {
            "interview_id": interview.id,
            "completed_at": interview.updated_at,
            "score": interview.overall_score,
        }
        for interview in sorted(completed, key=lambda i: i.updated_at)
        if interview.overall_score is not None
    ]

    latest_plan = db.execute(
        select(ImprovementPlan)
        .where(ImprovementPlan.user_id == user_id)
        .order_by(ImprovementPlan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    scored = [i.overall_score for i in interviews if i.overall_score is not None]

    return {
        "total_interviews": len(interviews),
        "completed_interviews": len(completed),
        "total_answers": total_answers,
        "average_score": average_score,
        "best_score": max(scored) if scored else None,
        "rubric_averages": rubric_averages,
        "strongest_topics": strongest_topics,
        "weak_topics": weak_topics,
        "progress": progress,
        "recent_interviews": interviews[:5],
        "latest_plan": latest_plan,
    }


def admin_overview(db: Session) -> dict:
    """Platform-wide counts for the administrator view."""
    from app.models.user import User

    total_users = db.execute(select(func.count()).select_from(User)).scalar_one()
    total_interviews = db.execute(
        select(func.count()).select_from(Interview)
    ).scalar_one()
    completed = db.execute(
        select(func.count())
        .select_from(Interview)
        .where(Interview.status == InterviewStatus.COMPLETED.value)
    ).scalar_one()
    average = db.execute(
        select(func.avg(Interview.overall_score)).where(
            Interview.overall_score.isnot(None)
        )
    ).scalar_one()

    return {
        "total_users": total_users,
        "total_interviews": total_interviews,
        "completed_interviews": completed,
        "average_score": round(float(average), 2) if average is not None else None,
    }
