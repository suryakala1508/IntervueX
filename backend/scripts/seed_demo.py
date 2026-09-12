"""Seed a demo account so the UI has something to show on a fresh database.

    python -m scripts.seed_demo           # deterministic, instant, no API calls
    python -m scripts.seed_demo --live    # real model for both questions and answers

Creates a candidate (demo@intervuex.app / demo1234), an administrator
(admin@intervuex.app / admin1234), a filled-in profile, a target job, and one
finished interview with an improvement plan. Re-running it is a no-op.

Two modes, because the awkward part of seeding is not the questions - it is the
*answers*. A seeded interview needs a candidate to answer as well as an
interviewer to ask.

Default mode runs the whole thing on the offline provider. Its questions are
drawn from fixed templates, so the canned answers below were written to fit
them, and the scores come out coherent. Instant and free.

--live mode uses whichever real provider is configured and has it write the
candidate's answers too, at a scripted mix of qualities. The transcript reads
like a real interview and the adaptive difficulty visibly moves, at the cost of
roughly 20k tokens and a minute or two against a rate-limited free tier.

What you must not do is mix the two: a real model invents its own questions, so
the canned answers no longer match them and every score collapses to near zero.
"""

from __future__ import annotations

import argparse
import logging
import sys

from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.ai.llm import LLMError, get_llm_provider, reset_llm_provider
from app.ai.tools import ToolRunner
from app.core.config import settings
from app.core.security import hash_password
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.enums import InterviewStatus, UserRole
from app.models.interview import Interview, InterviewQuestion
from app.models.user import CandidateProfile, User
from app.schemas.profile import JobDescriptionCreate
from app.services.interviews import complete_interview
from app.services.profile import create_job_description
from app.ai.workflow import run_answer_turn, run_start_interview

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("seed")

CANDIDATE_EMAIL = "demo@intervuex.app"
ADMIN_EMAIL = "admin@intervuex.app"

JOB_TEXT = """Backend Engineer (Python) - Northwind Labs

We are looking for a backend engineer to design and operate the services behind
our order platform. You will build REST APIs in Python with FastAPI, model data
in PostgreSQL, and keep p99 latency predictable as traffic grows.

Requirements:
- Strong Python, including async I/O and testing discipline
- Relational data modelling and query tuning in PostgreSQL
- REST API design, authentication, and versioning
- Docker, CI, and comfort owning a service in production
- Bonus: retrieval-augmented generation, vector databases, LangGraph
"""

ANSWERS = [
    (
        "I would keep the write path inside one PostgreSQL transaction so a partial "
        "order can never be persisted, and make the endpoint idempotent with a client "
        "supplied key so a retried request does not double-charge. For read latency I "
        "add a composite index on (customer_id, created_at) because that matches the "
        "listing query, and I verify it with EXPLAIN ANALYZE on production-sized data "
        "rather than assuming the planner will use it."
    ),
    (
        "On OrderFlow the slowest endpoint turned out to be an N+1 query: the list view "
        "loaded each order's line items separately. I found it by turning on SQLAlchemy "
        "query logging and counting statements per request, then fixed it with "
        "selectinload. Latency went from about 900ms to 70ms. The lasting lesson was to "
        "assert on query counts in tests so the regression cannot come back quietly."
    ),
    (
        "I disagreed with a teammate who wanted to cache the pricing response for an "
        "hour. Rather than argue from opinion I pulled the numbers: prices changed "
        "several times a day, so an hour of staleness would have shown customers wrong "
        "totals. We agreed on a 60 second TTL plus explicit invalidation on write, which "
        "kept most of the benefit without the correctness risk."
    ),
    (
        "For authentication I would issue a short-lived JWT access token and a longer "
        "refresh token, hash passwords with bcrypt, and keep the token secret out of the "
        "repository. Access tokens stay short so a leaked one expires quickly, and the "
        "refresh endpoint is the single place to add revocation later without changing "
        "the API surface."
    ),
]


class SimulatedAnswer(BaseModel):
    """A candidate's spoken answer, written by the model for --live seeding."""

    answer_text: str = Field(
        description="The candidate's answer, first person, 60-180 words, no markdown."
    )


# Deliberately varied, so the adaptive loop has something to react to: the
# difficulty should climb after a strong answer and fall back after a weak one.
ANSWER_QUALITIES = ["strong", "weak", "strong", "adequate", "strong", "weak"]

QUALITY_BRIEF = {
    "strong": (
        "Answer well: a specific claim, a concrete example with real numbers or "
        "tools, and an honest trade-off. Sound like an engineer who has done it."
    ),
    "adequate": (
        "Answer reasonably but unevenly: broadly correct, one or two of the key "
        "points missing, light on specifics."
    ),
    "weak": (
        "Answer poorly, the way a nervous or under-prepared candidate would: "
        "vague, largely surface-level, missing the substance of the question. "
        "Do not be absurd - just thin."
    ),
}


def simulate_answer(question, quality: str, candidate_block: str) -> str:
    """Have the configured model write the candidate's answer for one question."""
    provider = get_llm_provider()
    prompt = (
        f"You are role-playing a job candidate in a mock interview.\n\n"
        f"Candidate background:\n{candidate_block}\n\n"
        f"Interview question ({question.category} / {question.difficulty}):\n"
        f"{question.question_text}\n\n"
        f"{QUALITY_BRIEF[quality]}\n\n"
        "Write only what the candidate says out loud."
    )
    result = provider._parse(
        system="You role-play interview candidates realistically for training data.",
        prompt=prompt,
        output_format=SimulatedAnswer,
    )
    return result.answer_text


def get_or_create_user(db, email: str, name: str, password: str, role: UserRole) -> tuple[User, bool]:
    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()
    if user is not None:
        return user, False

    user = User(
        email=email,
        full_name=name,
        password_hash=hash_password(password),
        role=role.value,
    )
    db.add(user)
    db.flush()
    db.add(CandidateProfile(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user, True


def main(live: bool = False) -> int:
    if live:
        provider = get_llm_provider()
        if provider.name == "offline":
            logger.error(
                "--live needs a real provider, but none is configured. Set "
                "GROQ_API_KEY (or ANTHROPIC_API_KEY) in backend/.env, or drop "
                "the flag to seed deterministically."
            )
            return 1
        logger.info("Seeding with %s - questions and answers both generated", provider.name)
    else:
        # Pin the offline provider even when a real one is configured: the canned
        # answers below only line up with the questions it asks. See the module
        # docstring.
        settings.llm_provider = "offline"
        reset_llm_provider()

    init_db()

    with SessionLocal() as db:
        admin, created = get_or_create_user(
            db, ADMIN_EMAIL, "Platform Admin", "admin1234", UserRole.ADMIN
        )
        logger.info("%s admin %s", "Created" if created else "Found", admin.email)

        user, created = get_or_create_user(
            db, CANDIDATE_EMAIL, "Demo Candidate", "demo1234", UserRole.CANDIDATE
        )
        if not created:
            logger.info("Demo candidate already exists - nothing to do")
            return 0

        profile = db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        ).scalar_one()
        profile.headline = "Backend engineer building Python services"
        profile.location = "Bengaluru, India"
        profile.years_of_experience = 3
        profile.skills = [
            "Python", "FastAPI", "PostgreSQL", "SQLAlchemy", "Docker",
            "REST APIs", "pytest", "Redis", "SQL",
        ]
        profile.preferred_role = "Backend Engineer"
        profile.target_company = "Northwind Labs"
        profile.summary = (
            "Backend engineer with three years building and operating Python APIs, "
            "most recently an order platform serving 2k requests per second."
        )
        profile.education = [
            {"degree": "B.Tech Computer Science", "institution": "PES University", "year": "2022"}
        ]
        profile.experience = [
            {
                "title": "Backend Engineer",
                "company": "Acme Retail",
                "period": "2022 - present",
                "description": "Owned the orders and pricing services end to end.",
            }
        ]
        profile.projects = [
            {
                "name": "OrderFlow",
                "description": "Order processing service in FastAPI and PostgreSQL with idempotent writes.",
            },
            {
                "name": "DocSearch",
                "description": "Retrieval over internal docs using embeddings and pgvector.",
            },
        ]
        db.commit()

        job = create_job_description(
            db,
            user.id,
            JobDescriptionCreate(
                title="Backend Engineer (Python)",
                company="Northwind Labs",
                raw_text=JOB_TEXT,
                set_active=True,
            ),
        )
        logger.info("Created job description: %s", job.title)

        interview = Interview(
            user_id=user.id,
            job_description_id=job.id,
            title="Northwind Labs - backend practice",
            planned_question_count=4,
            status=InterviewStatus.IN_PROGRESS.value,
        )
        db.add(interview)
        db.flush()

        runner = ToolRunner(db, user.id, interview_id=interview.id)
        state = run_start_interview(runner, interview.id)
        db.commit()

        candidate_block = ToolRunner(db, user.id).build_context(job_id=job.id).candidate_block
        scripted = ANSWER_QUALITIES if live else ANSWERS

        question_id = state["next_question_id"]
        for turn, scripted_value in enumerate(scripted, start=1):
            if question_id is None:
                break
            question = db.get(InterviewQuestion, question_id)
            logger.info("Q%d: %s", question.position, question.question_text[:78])

            if live:
                try:
                    answer_text = simulate_answer(question, scripted_value, candidate_block)
                except LLMError as exc:
                    logger.error("Could not generate an answer for Q%d: %s", turn, exc)
                    break
                logger.info("   answering (%s): %s", scripted_value, answer_text[:70])
            else:
                answer_text = scripted_value

            state = run_answer_turn(
                ToolRunner(db, user.id, interview_id=interview.id),
                interview_id=interview.id,
                question_id=question_id,
                answer_text=answer_text,
                time_taken_seconds=180,
            )
            db.commit()
            question_id = state.get("next_question_id")
            if state.get("finished"):
                break

        interview_obj, plan = complete_interview(db, user, interview.id)
        logger.info(
            "Completed interview: overall %s/10, %d weak topics",
            interview_obj.overall_score,
            len(plan.weak_topics),
        )

    logger.info("")
    logger.info("Seed complete. Sign in with:")
    logger.info("  candidate  %s / demo1234", CANDIDATE_EMAIL)
    logger.info("  admin      %s / admin1234", ADMIN_EMAIL)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Use the configured model for the questions AND the candidate's "
            "answers. Realistic, but costs roughly 20k tokens."
        ),
    )
    sys.exit(main(live=parser.parse_args().live))
