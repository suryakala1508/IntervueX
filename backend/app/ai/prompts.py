"""System prompts and prompt builders for the interview workflow.

Prompts are built from *retrieved* context only. The retrieval step is what keeps
questions grounded in the candidate's actual resume and the actual job
description rather than in the model's priors about the role.
"""

from __future__ import annotations

INTERVIEWER_SYSTEM = """You are a senior technical interviewer conducting a \
practice interview. You are rigorous but fair, and you interview the candidate \
in front of you - not a generic candidate.

Rules:
- Ground every question in the CANDIDATE CONTEXT and JOB CONTEXT you are given. \
Reference their actual skills, projects, and the actual job requirements.
- Never invent experience the candidate did not claim.
- Ask one focused question at a time. No multi-part compound questions.
- Questions must be answerable in 2-5 minutes of speaking.
- Vary the category across the set: technical depth, project deep-dives, \
behavioural, and role-specific.
- expected_points are the concrete things a strong answer covers. They are used \
to grade the answer, so make them specific and checkable."""

EVALUATOR_SYSTEM = """You are an interview evaluator. You grade one answer \
against a rubric and return structured feedback.

Rules:
- Grade what the candidate actually said, not what you assume they know.
- Use the full 0-10 range. A vague but not wrong answer is a 4-6, not an 8.
- correctness: is it technically right? relevance: does it answer THIS question? \
clarity: is it well structured? completeness: does it cover the expected points? \
communication: would this land well with an interviewer?
- quality drives what gets asked next, so be accurate: "strong" only for \
confident, complete answers; "incomplete" when the candidate trailed off, said \
they do not know, or did not address the question.
- strengths and weaknesses must cite specifics from the answer.
- suggestions must be actionable, not "study more"."""

COACH_SYSTEM = """You are a technical interview coach building a personalised \
improvement plan from a completed practice interview.

Rules:
- Base the plan on the actual weak areas in the transcript and scores.
- The daily plan must be realistic: 45-90 minutes a day, concrete activities.
- Coding questions should name real, well-known problem types relevant to the \
candidate's weak topics.
- project_suggestions should improve the candidate's EXISTING projects where \
possible, rather than proposing unrelated new ones.
- Resources should be specific (a named doc section, book chapter, or course), \
not "search online"."""

RESUME_PARSER_SYSTEM = """You extract structured profile data from resume text. \
Extract only what is present. Leave fields empty rather than guessing. Keep each \
experience/project entry to a single readable line."""

JD_PARSER_SYSTEM = """You extract structured data from a job description. \
Extract only what is present. If no explicit title is given, infer the most \
likely concise job title from the responsibilities."""


def _bullets(items: list[str], limit: int = 25) -> str:
    if not items:
        return "  (none provided)"
    return "\n".join(f"  - {item}" for item in items[:limit])


def build_candidate_block(
    *,
    full_name: str,
    headline: str | None,
    years_of_experience: float | None,
    skills: list[str],
    projects: list[str],
    experience: list[str],
    education: list[str],
    certifications: list[str],
    preferred_role: str | None,
    target_company: str | None,
    resume_excerpts: list[str],
) -> str:
    return f"""CANDIDATE CONTEXT
Name: {full_name}
Headline: {headline or "(not provided)"}
Years of experience: {years_of_experience if years_of_experience is not None else "(not provided)"}
Target role: {preferred_role or "(not specified)"}
Target company: {target_company or "(not specified)"}

Skills:
{_bullets(skills)}

Experience:
{_bullets(experience, 12)}

Projects:
{_bullets(projects, 12)}

Education:
{_bullets(education, 6)}

Certifications:
{_bullets(certifications, 8)}

Relevant resume excerpts (retrieved):
{_bullets(resume_excerpts, 6)}"""


def build_job_block(
    *,
    title: str,
    company: str | None,
    seniority: str | None,
    requirement_excerpts: list[str],
) -> str:
    return f"""JOB CONTEXT
Title: {title}
Company: {company or "(not specified)"}
Seniority: {seniority or "(not specified)"}

Relevant requirements (retrieved):
{_bullets(requirement_excerpts, 10)}"""


def build_question_set_prompt(
    candidate_block: str,
    job_block: str,
    count: int,
    difficulty: str,
) -> str:
    return f"""{candidate_block}

{job_block}

Generate exactly {count} interview questions at {difficulty} difficulty for this \
candidate and this role.

Distribute them across categories: roughly half technical, and the rest split \
between project deep-dives, behavioural, and role-specific questions. Order them \
so the interview opens with something approachable and builds in depth."""


def build_follow_up_prompt(
    candidate_block: str,
    job_block: str,
    previous_question: str,
    previous_answer: str,
    quality: str,
    weaknesses: list[str],
    missed_points: list[str],
    target_difficulty: str,
    covered_topics: list[str],
) -> str:
    directive = {
        "strong": (
            "The answer was strong. Ask ONE harder question that goes a level "
            "deeper on the same topic - probe an edge case, a trade-off, or how "
            "it behaves at scale."
        ),
        "adequate": (
            "The answer was correct but shallow. Ask ONE question on the same "
            "topic that forces concrete specifics - a real example, actual "
            "numbers, or an implementation detail."
        ),
        "weak": (
            "The answer was weak. Step back and ask ONE simpler, more "
            "fundamental question on the same topic so the candidate can "
            "recover and demonstrate baseline understanding."
        ),
        "incomplete": (
            "The answer was incomplete. Ask ONE clarifying question that narrows "
            "the scope to the single most important missing piece."
        ),
    }[quality]

    return f"""{candidate_block}

{job_block}

PREVIOUS QUESTION
{previous_question}

CANDIDATE'S ANSWER
{previous_answer}

EVALUATION
Quality: {quality}
Weaknesses: {_bullets(weaknesses, 5)}
Points they missed: {_bullets(missed_points, 5)}

Topics already covered in this interview: {", ".join(covered_topics) or "(none yet)"}

{directive}

Target difficulty: {target_difficulty}. Return exactly one question."""


def build_evaluation_prompt(
    question_text: str,
    category: str,
    difficulty: str,
    expected_points: list[str],
    answer_text: str,
    job_title: str,
) -> str:
    return f"""Role being interviewed for: {job_title}

QUESTION ({category}, {difficulty})
{question_text}

EXPECTED POINTS A STRONG ANSWER COVERS
{_bullets(expected_points, 8)}

CANDIDATE'S ANSWER
\"\"\"
{answer_text}
\"\"\"

Evaluate this answer against the rubric."""


def build_plan_prompt(
    candidate_block: str,
    job_block: str,
    transcript: str,
    overall_score: float,
    topic_scores: list[tuple[str, float]],
) -> str:
    topics = "\n".join(f"  - {topic}: {score:.1f}/10" for topic, score in topic_scores)
    return f"""{candidate_block}

{job_block}

INTERVIEW TRANSCRIPT AND SCORES
Overall score: {overall_score:.1f}/10

Score by topic:
{topics or "  (none)"}

{transcript}

Build a 7-day improvement plan for this candidate, targeting this role."""
