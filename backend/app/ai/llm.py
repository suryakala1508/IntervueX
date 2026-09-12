"""LLM providers.

`AnthropicProvider` is the real implementation: every call goes through
`messages.parse(output_format=...)`, so Claude is constrained to the Pydantic
schema and the result arrives already validated.

`OfflineProvider` is a deterministic, rule-based stand-in. It is not an attempt
to imitate a language model - it is a way to keep every code path in the product
(interviews, adaptive follow-ups, evaluation, plans, the dashboard) exercisable
and testable with no API key and no network.
"""

from __future__ import annotations

import json
import logging
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.ai.embeddings import tokenize
from app.ai.offline_knowledge import knowledge_for
from app.ai.prompts import (
    COACH_SYSTEM,
    EVALUATOR_SYSTEM,
    INTERVIEWER_SYSTEM,
    JD_PARSER_SYSTEM,
    RESUME_PARSER_SYSTEM,
    build_evaluation_prompt,
    build_follow_up_prompt,
    build_plan_prompt,
    build_question_set_prompt,
)
from app.ai.schemas import (
    AnswerEvaluation,
    CodingQuestionSuggestion,
    DailyPlanItem,
    GeneratedQuestion,
    GeneratedQuestionSet,
    ImprovementPlanOutput,
    ParsedJobDescription,
    ParsedResumeProfile,
    ResourceSuggestion,
)
from app.core.config import settings
from app.models.enums import AnswerQuality, Difficulty, QuestionCategory

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the provider cannot produce a valid structured result."""


@dataclass
class InterviewContext:
    """Everything the prompt builders and the offline provider need."""

    full_name: str = "the candidate"
    candidate_block: str = ""
    job_block: str = ""
    job_title: str = "Software Engineer"
    skills: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate_questions(
        self, ctx: InterviewContext, count: int, difficulty: Difficulty, seed: str
    ) -> GeneratedQuestionSet: ...

    @abstractmethod
    def generate_follow_up(
        self,
        ctx: InterviewContext,
        previous_question: str,
        previous_answer: str,
        evaluation: AnswerEvaluation,
        target_difficulty: Difficulty,
        covered_topics: list[str],
        previous_topic: str,
        previous_category: QuestionCategory,
        seed: str,
    ) -> GeneratedQuestion: ...

    @abstractmethod
    def evaluate_answer(
        self,
        question_text: str,
        category: str,
        difficulty: str,
        expected_points: list[str],
        answer_text: str,
        job_title: str,
    ) -> AnswerEvaluation: ...

    @abstractmethod
    def create_improvement_plan(
        self,
        ctx: InterviewContext,
        transcript: str,
        overall_score: float,
        topic_scores: list[tuple[str, float]],
    ) -> ImprovementPlanOutput: ...

    @abstractmethod
    def parse_resume(self, text: str) -> ParsedResumeProfile: ...

    @abstractmethod
    def parse_job_description(self, text: str) -> ParsedJobDescription: ...


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None, model: str) -> None:
        import anthropic

        self._anthropic = anthropic
        # A None key lets the SDK fall back to ANTHROPIC_API_KEY / an `ant auth
        # login` profile, which is the documented resolution order.
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model

    def _parse(self, *, system: str, prompt: str, output_format, max_tokens: int | None = None):
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=max_tokens or settings.llm_max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "adaptive"},
                output_config={"effort": settings.llm_effort},
                output_format=output_format,
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "explanation", "") or ""
            raise LLMError(f"Model declined the request. {detail}".strip())

        parsed = response.parsed_output
        if parsed is None:
            raise LLMError("Model returned no parseable structured output")
        return parsed

    def generate_questions(
        self, ctx: InterviewContext, count: int, difficulty: Difficulty, seed: str
    ) -> GeneratedQuestionSet:
        result = self._parse(
            system=INTERVIEWER_SYSTEM,
            prompt=build_question_set_prompt(
                ctx.candidate_block, ctx.job_block, count, difficulty.value
            ),
            output_format=GeneratedQuestionSet,
        )
        if not result.questions:
            raise LLMError("Model returned an empty question set")
        return result

    def generate_follow_up(
        self,
        ctx: InterviewContext,
        previous_question: str,
        previous_answer: str,
        evaluation: AnswerEvaluation,
        target_difficulty: Difficulty,
        covered_topics: list[str],
        previous_topic: str,
        previous_category: QuestionCategory,
        seed: str,
    ) -> GeneratedQuestion:
        return self._parse(
            system=INTERVIEWER_SYSTEM,
            prompt=build_follow_up_prompt(
                ctx.candidate_block,
                ctx.job_block,
                previous_question,
                previous_answer,
                evaluation.quality.value,
                evaluation.weaknesses,
                evaluation.missed_points,
                target_difficulty.value,
                covered_topics,
            ),
            output_format=GeneratedQuestion,
        )

    def evaluate_answer(
        self,
        question_text: str,
        category: str,
        difficulty: str,
        expected_points: list[str],
        answer_text: str,
        job_title: str,
    ) -> AnswerEvaluation:
        return self._parse(
            system=EVALUATOR_SYSTEM,
            prompt=build_evaluation_prompt(
                question_text,
                category,
                difficulty,
                expected_points,
                answer_text,
                job_title,
            ),
            output_format=AnswerEvaluation,
        )

    def create_improvement_plan(
        self,
        ctx: InterviewContext,
        transcript: str,
        overall_score: float,
        topic_scores: list[tuple[str, float]],
    ) -> ImprovementPlanOutput:
        return self._parse(
            system=COACH_SYSTEM,
            prompt=build_plan_prompt(
                ctx.candidate_block,
                ctx.job_block,
                transcript,
                overall_score,
                topic_scores,
            ),
            output_format=ImprovementPlanOutput,
            max_tokens=max(settings.llm_max_tokens, 12000),
        )

    def parse_resume(self, text: str) -> ParsedResumeProfile:
        return self._parse(
            system=RESUME_PARSER_SYSTEM,
            prompt=f"Resume text:\n\"\"\"\n{text[:40000]}\n\"\"\"",
            output_format=ParsedResumeProfile,
        )

    def parse_job_description(self, text: str) -> ParsedJobDescription:
        return self._parse(
            system=JD_PARSER_SYSTEM,
            prompt=f"Job description:\n\"\"\"\n{text[:20000]}\n\"\"\"",
            output_format=ParsedJobDescription,
        )


# --------------------------------------------------------------------------- #
# Groq
# --------------------------------------------------------------------------- #

# Keywords that JSON-schema strict mode rejects or ignores. The bounds they
# express are not lost: the response is validated through the Pydantic model
# afterwards, which enforces them properly.
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "default",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "pattern",
        "format",
        "examples",
    }
)


def _strictify(node: Any) -> Any:
    """Rewrite a Pydantic JSON schema into the strict subset Groq accepts.

    Strict mode requires every object to forbid extra properties and to list
    every property as required - optional fields and defaults are not part of
    the dialect. Bounds and formats are dropped here and re-enforced by the
    Pydantic model when the response is validated.
    """
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node

    result = {
        key: _strictify(value)
        for key, value in node.items()
        if key not in _UNSUPPORTED_SCHEMA_KEYS
    }

    if result.get("type") == "object" or "properties" in result:
        properties = result.get("properties", {})
        result["additionalProperties"] = False
        result["required"] = list(properties)

    return result


class GroqProvider(LLMProvider):
    """Groq's OpenAI-compatible chat completions endpoint.

    Uses strict `json_schema` response formatting so the model is constrained to
    the same Pydantic schemas the Anthropic provider uses, which keeps the rest
    of the application identical whichever provider is configured.
    """

    name = "groq"

    # Groq's free tier rate-limits; a couple of backed-off retries turn a
    # transient 429 into a slower answer rather than a failed interview.
    MAX_ATTEMPTS = 3
    RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

    def __init__(self, api_key: str, model: str) -> None:
        import httpx

        self._httpx = httpx
        self.model = model
        self.client = httpx.Client(
            base_url=settings.groq_base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.groq_timeout_seconds,
        )

    def _effort(self) -> str:
        # gpt-oss exposes low/medium/high only; the higher Anthropic tiers map onto high.
        return {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}[
            settings.llm_effort
        ]

    def _parse(self, *, system: str, prompt: str, output_format, max_tokens: int | None = None):
        schema = _strictify(output_format.model_json_schema())
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": max_tokens or settings.llm_max_tokens,
            "temperature": 0.3,
            "reasoning_effort": self._effort(),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": output_format.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
        }

        last_error = ""
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = self.client.post("/chat/completions", json=payload)
            except self._httpx.RequestError as exc:
                last_error = f"could not reach Groq ({exc.__class__.__name__})"
                self._backoff(attempt)
                continue

            if response.status_code in self.RETRY_STATUSES:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                self._backoff(attempt, response)
                continue

            if response.status_code >= 400:
                raise LLMError(
                    f"Groq request failed (HTTP {response.status_code}): {response.text[:300]}"
                )

            return self._validate(response.json(), output_format)

        raise LLMError(f"Groq request failed after {self.MAX_ATTEMPTS} attempts: {last_error}")

    def _backoff(self, attempt: int, response: Any = None) -> None:
        import time

        # Honour the server's own guidance when it sends one.
        wait = 2.0 * (attempt + 1)
        if response is not None:
            try:
                wait = min(30.0, float(response.headers.get("retry-after", wait)))
            except (TypeError, ValueError):
                pass
        logger.warning("Groq call failed; retrying in %.1fs", wait)
        time.sleep(wait)

    def _validate(self, body: dict, output_format):
        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected response shape from Groq: {exc}") from exc

        if choice.get("finish_reason") == "length":
            raise LLMError(
                "The model hit the token limit before finishing. Raise LLM_MAX_TOKENS."
            )
        if not content or not content.strip():
            raise LLMError("Groq returned an empty response")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Groq returned text that is not JSON: {content[:200]}") from exc

        try:
            return output_format.model_validate(data)
        except ValidationError as exc:
            raise LLMError(f"Groq output did not match {output_format.__name__}: {exc}") from exc

    def generate_questions(
        self, ctx: InterviewContext, count: int, difficulty: Difficulty, seed: str
    ) -> GeneratedQuestionSet:
        result = self._parse(
            system=INTERVIEWER_SYSTEM,
            prompt=build_question_set_prompt(
                ctx.candidate_block, ctx.job_block, count, difficulty.value
            ),
            output_format=GeneratedQuestionSet,
        )
        if not result.questions:
            raise LLMError("Model returned an empty question set")
        return result

    def generate_follow_up(
        self,
        ctx: InterviewContext,
        previous_question: str,
        previous_answer: str,
        evaluation: AnswerEvaluation,
        target_difficulty: Difficulty,
        covered_topics: list[str],
        previous_topic: str,
        previous_category: QuestionCategory,
        seed: str,
    ) -> GeneratedQuestion:
        return self._parse(
            system=INTERVIEWER_SYSTEM,
            prompt=build_follow_up_prompt(
                ctx.candidate_block,
                ctx.job_block,
                previous_question,
                previous_answer,
                evaluation.quality.value,
                evaluation.weaknesses,
                evaluation.missed_points,
                target_difficulty.value,
                covered_topics,
            ),
            output_format=GeneratedQuestion,
        )

    def evaluate_answer(
        self,
        question_text: str,
        category: str,
        difficulty: str,
        expected_points: list[str],
        answer_text: str,
        job_title: str,
    ) -> AnswerEvaluation:
        return self._parse(
            system=EVALUATOR_SYSTEM,
            prompt=build_evaluation_prompt(
                question_text,
                category,
                difficulty,
                expected_points,
                answer_text,
                job_title,
            ),
            output_format=AnswerEvaluation,
        )

    def create_improvement_plan(
        self,
        ctx: InterviewContext,
        transcript: str,
        overall_score: float,
        topic_scores: list[tuple[str, float]],
    ) -> ImprovementPlanOutput:
        return self._parse(
            system=COACH_SYSTEM,
            prompt=build_plan_prompt(
                ctx.candidate_block,
                ctx.job_block,
                transcript,
                overall_score,
                topic_scores,
            ),
            output_format=ImprovementPlanOutput,
            max_tokens=max(settings.llm_max_tokens, 12000),
        )

    def parse_resume(self, text: str) -> ParsedResumeProfile:
        return self._parse(
            system=RESUME_PARSER_SYSTEM,
            prompt=f"Resume text:\n\"\"\"\n{text[:40000]}\n\"\"\"",
            output_format=ParsedResumeProfile,
        )

    def parse_job_description(self, text: str) -> ParsedJobDescription:
        return self._parse(
            system=JD_PARSER_SYSTEM,
            prompt=f"Job description:\n\"\"\"\n{text[:20000]}\n\"\"\"",
            output_format=ParsedJobDescription,
        )


# --------------------------------------------------------------------------- #
# Offline
# --------------------------------------------------------------------------- #

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "this", "that", "as", "at",
    "by", "from", "you", "your", "i", "we", "they", "how", "what", "when", "why",
    "would", "could", "should", "do", "does", "did", "can", "will", "about",
    "there", "their", "them", "then", "than", "so", "if", "not", "have", "has",
}

_STRUCTURE_MARKERS = {
    "first", "second", "third", "then", "next", "finally", "because", "however",
    "although", "trade", "tradeoff", "trade-off", "example", "instance",
    "specifically", "therefore", "whereas", "instead", "additionally",
}

# Framing words that appear in almost every interview question. Counting them
# toward relevance penalises good answers for not parroting the prompt.
_QUESTION_FRAME_WORDS = {
    "walk", "tell", "describe", "explain", "would", "could", "main", "make",
    "through", "design", "implement", "production", "system", "systems",
    "trade", "tradeoff", "trade-off", "tradeoffs", "approach", "team", "teams",
    "time", "work", "worked", "working", "actually", "really", "deliberately",
    "under", "hood", "into", "handle", "given", "look", "like", "most",
    "significant", "piece", "run", "running", "using", "use", "used", "one",
    "way", "ways", "thing", "things", "question", "answer", "candidate",
}

_UNCERTAINTY_MARKERS = (
    "i don't know", "i dont know", "not sure", "no idea", "never used",
    "never worked with", "can't remember", "cant remember", "i'm unsure",
)

_TECHNICAL_TEMPLATES = [
    "Walk me through how you would design and implement {topic} in a production system. What are the main trade-offs?",
    "How does {topic} actually work under the hood, and when would you deliberately choose not to use it?",
    "Describe a bug or performance problem you have run into with {topic}. How did you diagnose it?",
    "Your team's {topic} implementation starts failing under load. How do you investigate?",
]

_PROJECT_TEMPLATES = [
    "Tell me about {topic}. What was the hardest technical decision you made, and what did you reject?",
    "In {topic}, how did you verify it actually worked? Walk me through your testing approach.",
    "If you rebuilt {topic} today, what would you change and why?",
]

_BEHAVIOURAL_TEMPLATES = [
    "Tell me about a time you disagreed with a teammate on a technical approach. How did it resolve?",
    "Describe a deadline you realised you were not going to make. What did you do?",
    "Tell me about the most significant piece of feedback you have received. What changed afterwards?",
    "Describe a time you shipped something that broke. How did you handle it?",
]

_ROLE_TEMPLATES = [
    "This role is {job_title} and emphasises {topic}. Where does your experience match most closely, and where is your biggest gap?",
    "What would your first 90 days as a {job_title} look like, given the emphasis on {topic}?",
    "How do you keep current with {topic}, and what have you learned about it recently?",
]

_BEHAVIOURAL_POINTS = [
    "Uses a concrete situation rather than a hypothetical",
    "States their specific role and actions, not just the team's",
    "Describes the outcome and what they learned",
    "Shows self-awareness about what they would do differently",
]


def _content_tokens(text: str) -> set[str]:
    return {t for t in tokenize(text) if len(t) > 2 and t not in _STOPWORDS}


class OfflineProvider(LLMProvider):
    """Deterministic rule-based provider. Same seed in, same output out."""

    name = "offline"

    # -- question generation ------------------------------------------------ #

    def _topic_pool(self, ctx: InterviewContext) -> list[str]:
        """Topics ranked by overlap between the candidate's skills and the job."""
        requirement_tokens = _content_tokens(" ".join(ctx.requirements))
        scored: list[tuple[int, str]] = []
        for skill in ctx.skills:
            overlap = len(_content_tokens(skill) & requirement_tokens)
            scored.append((overlap, skill))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        topics = [skill for _, skill in scored]

        # Fill out with distinctive terms from the job requirements themselves.
        for requirement in ctx.requirements:
            for token in _content_tokens(requirement):
                if len(token) > 4 and token not in {t.lower() for t in topics}:
                    topics.append(token)
        if not topics:
            topics = ["system design", "algorithms", "testing", "api design"]
        return topics

    def generate_questions(
        self, ctx: InterviewContext, count: int, difficulty: Difficulty, seed: str
    ) -> GeneratedQuestionSet:
        rng = random.Random(seed)
        topics = self._topic_pool(ctx)
        projects = ctx.projects or ["your most recent project"]

        # Roughly: half technical, then project / behavioural / role-specific.
        plan: list[QuestionCategory] = []
        for i in range(count):
            if i % 4 in (0, 2):
                plan.append(QuestionCategory.TECHNICAL)
            elif i % 4 == 1:
                plan.append(QuestionCategory.PROJECT)
            elif i % 8 == 3:
                plan.append(QuestionCategory.BEHAVIORAL)
            else:
                plan.append(QuestionCategory.ROLE_SPECIFIC)

        questions: list[GeneratedQuestion] = []
        for index, category in enumerate(plan):
            # Ramp difficulty gently across the set.
            step = 0 if index < count / 3 else (1 if index < 2 * count / 3 else 1)
            level = Difficulty.from_rank(difficulty.rank + step - 1 + (index % 2))
            questions.append(
                self._make_question(rng, ctx, category, level, topics, projects, index)
            )
        return GeneratedQuestionSet(questions=questions)

    def _make_question(
        self,
        rng: random.Random,
        ctx: InterviewContext,
        category: QuestionCategory,
        difficulty: Difficulty,
        topics: list[str],
        projects: list[str],
        index: int,
    ) -> GeneratedQuestion:
        if category is QuestionCategory.TECHNICAL:
            topic = topics[index % len(topics)]
            text = rng.choice(_TECHNICAL_TEMPLATES).format(topic=topic, job_title=ctx.job_title)
            points = knowledge_for(topic)["points"]
        elif category is QuestionCategory.PROJECT:
            topic = projects[index % len(projects)]
            text = rng.choice(_PROJECT_TEMPLATES).format(topic=topic, job_title=ctx.job_title)
            points = [
                "Explains the problem the project solved and for whom",
                "Names the hardest decision and the alternative that was rejected",
                "Describes how correctness was verified",
                "Reflects on what they would change",
            ]
        elif category is QuestionCategory.BEHAVIORAL:
            topic = "collaboration"
            text = rng.choice(_BEHAVIOURAL_TEMPLATES)
            points = list(_BEHAVIOURAL_POINTS)
        else:
            topic = topics[(index + 1) % len(topics)]
            text = rng.choice(_ROLE_TEMPLATES).format(topic=topic, job_title=ctx.job_title)
            points = [
                f"Connects their own experience to {topic} concretely",
                "Is honest about gaps rather than overclaiming",
                f"Shows they understand what the {ctx.job_title} role involves",
            ]

        return GeneratedQuestion(
            question_text=text,
            category=category,
            difficulty=difficulty,
            topic=str(topic)[:120],
            expected_points=points[:5],
        )

    def generate_follow_up(
        self,
        ctx: InterviewContext,
        previous_question: str,
        previous_answer: str,
        evaluation: AnswerEvaluation,
        target_difficulty: Difficulty,
        covered_topics: list[str],
        previous_topic: str,
        previous_category: QuestionCategory,
        seed: str,
    ) -> GeneratedQuestion:
        rng = random.Random(seed)
        topic = previous_topic or "system design"
        knowledge = knowledge_for(topic)

        if evaluation.quality is AnswerQuality.STRONG:
            text = (
                f"Good. Let's go deeper on {topic}: describe a case where your "
                f"approach would break down, and what you would change to handle it."
            )
            points = knowledge["points"][:3] + [
                "Identifies a concrete failure mode rather than a generic risk",
                "Proposes a specific mitigation and its cost",
            ]
        elif evaluation.quality is AnswerQuality.ADEQUATE:
            text = (
                f"Can you make that concrete? Give me a specific example from your "
                f"own work where you applied {topic}, including the numbers or "
                f"details that mattered."
            )
            points = [
                "Gives a real, specific example rather than restating theory",
                "Includes concrete details: scale, timing, or measurements",
                "Explains the outcome",
            ]
        elif evaluation.quality is AnswerQuality.WEAK:
            text = (
                f"Let's step back to fundamentals. In your own words, what problem "
                f"does {topic} solve, and when would you reach for it?"
            )
            points = [
                f"Correctly states the core purpose of {topic}",
                "Gives at least one appropriate use case",
                "Is honest about the limits of their knowledge",
            ]
        else:
            missing = evaluation.missed_points[0] if evaluation.missed_points else topic
            text = (
                f"Let me narrow that down. Focus on just one thing: {missing}. "
                f"Walk me through your thinking on that alone."
            )
            points = [
                f"Directly addresses: {missing}",
                "Stays focused rather than broadening the answer",
            ]

        return GeneratedQuestion(
            question_text=text,
            category=previous_category,
            difficulty=target_difficulty,
            topic=str(topic)[:120],
            expected_points=points[:5],
        )

    # -- evaluation --------------------------------------------------------- #

    def evaluate_answer(
        self,
        question_text: str,
        category: str,
        difficulty: str,
        expected_points: list[str],
        answer_text: str,
        job_title: str,
    ) -> AnswerEvaluation:
        answer = answer_text.strip()
        lowered = answer.lower()
        tokens = tokenize(answer)
        word_count = len(tokens)
        answer_tokens = _content_tokens(answer)

        # Which expected points does the answer actually touch?
        covered: list[str] = []
        missed: list[str] = []
        for point in expected_points:
            point_tokens = _content_tokens(point)
            if not point_tokens:
                continue
            hits = len(point_tokens & answer_tokens)
            ratio = hits / len(point_tokens)
            if hits >= 2 or ratio >= 0.5:
                covered.append(point)
            else:
                missed.append(point)

        coverage = len(covered) / len(expected_points) if expected_points else 0.5

        # Relevance is judged on the substantive terms of the question only, and
        # an answer that covers the expected points is relevant by definition -
        # so take the better of the two signals rather than the lexical one alone.
        question_tokens = _content_tokens(question_text) - _QUESTION_FRAME_WORDS
        lexical_overlap = (
            len(question_tokens & answer_tokens) / len(question_tokens)
            if question_tokens
            else 0.5
        )
        relevance_ratio = max(lexical_overlap, coverage)

        sentences = [s for s in re.split(r"[.!?\n]+", answer) if s.strip()]
        avg_sentence_len = word_count / len(sentences) if sentences else word_count
        markers = len(_STRUCTURE_MARKERS & set(tokens))
        says_unsure = any(marker in lowered for marker in _UNCERTAINTY_MARKERS)

        def clamp(value: float) -> int:
            return int(max(0, min(10, round(value))))

        if word_count < 8 or says_unsure:
            quality = AnswerQuality.INCOMPLETE
            correctness = clamp(1 + coverage * 3)
            relevance = clamp(1 + relevance_ratio * 4)
            clarity = clamp(2 + min(word_count, 20) / 10)
            completeness = clamp(coverage * 3)
            communication = clamp(2 + markers)
        else:
            # Length shapes the ceiling: very short answers cannot be complete,
            # very long ones lose clarity.
            length_factor = min(1.0, word_count / 90)
            verbosity_penalty = 1.5 if word_count > 450 else 0.0

            correctness = clamp(2.5 + coverage * 6.5 + relevance_ratio * 1.0)
            relevance = clamp(3.0 + relevance_ratio * 7.0)
            clarity = clamp(
                5.0
                + (2.0 if 8 <= avg_sentence_len <= 28 else -1.0)
                + min(markers, 3) * 0.8
                - verbosity_penalty
            )
            completeness = clamp(1.5 + coverage * 6.0 + length_factor * 2.5)
            communication = clamp(
                4.5 + min(markers, 4) * 0.9 + length_factor * 1.5 - verbosity_penalty
            )

            score_preview = (
                correctness * 0.35
                + relevance * 0.2
                + completeness * 0.25
                + clarity * 0.1
                + communication * 0.1
            )
            if score_preview >= 7.5:
                quality = AnswerQuality.STRONG
            elif score_preview >= 5.0:
                quality = AnswerQuality.ADEQUATE
            else:
                quality = AnswerQuality.WEAK

        score = clamp(
            correctness * 0.35
            + relevance * 0.20
            + completeness * 0.25
            + clarity * 0.10
            + communication * 0.10
        )

        strengths: list[str] = []
        if covered:
            strengths.append(f"Covered {len(covered)} of the key points, including: {covered[0]}")
        if markers >= 2:
            strengths.append("Structured the answer clearly with explicit reasoning steps")
        if relevance_ratio >= 0.4:
            strengths.append("Stayed on topic and addressed what was actually asked")
        if not strengths:
            strengths.append("Attempted the question rather than deflecting")

        weaknesses: list[str] = []
        if missed:
            weaknesses.append(f"Did not address {len(missed)} expected point(s)")
        if word_count < 40:
            weaknesses.append("Answer was too brief to demonstrate depth")
        if word_count > 450:
            weaknesses.append("Answer rambled; the main point was buried")
        if markers == 0 and word_count >= 40:
            weaknesses.append("No explicit structure or reasoning markers")
        if relevance_ratio < 0.25:
            weaknesses.append("Drifted away from the specific question asked")
        if says_unsure:
            weaknesses.append("Signalled uncertainty without attempting a partial answer")
        if not weaknesses:
            weaknesses.append("Could add a concrete example with real numbers")

        suggestions: list[str] = []
        for point in missed[:3]:
            suggestions.append(f"Next time, explicitly cover: {point.lower()}")
        if word_count < 40:
            suggestions.append("Aim for 90-150 words: claim, concrete example, trade-off")
        if markers == 0:
            suggestions.append("Signpost with 'first / then / the trade-off is' to aid the listener")
        if not suggestions:
            suggestions.append("Close with the trade-off you accepted and why")

        return AnswerEvaluation(
            score=score,
            correctness=correctness,
            relevance=relevance,
            clarity=clarity,
            completeness=completeness,
            communication=communication,
            quality=quality,
            strengths=strengths[:4],
            weaknesses=weaknesses[:4],
            suggestions=suggestions[:4],
            missed_points=missed[:5],
            rationale=(
                f"Covered {len(covered)}/{len(expected_points) or 0} expected points "
                f"in {word_count} words with {markers} structural markers."
            ),
        )

    # -- improvement plan --------------------------------------------------- #

    def create_improvement_plan(
        self,
        ctx: InterviewContext,
        transcript: str,
        overall_score: float,
        topic_scores: list[tuple[str, float]],
    ) -> ImprovementPlanOutput:
        ranked = sorted(topic_scores, key=lambda pair: pair[1])
        weak = [topic for topic, score in ranked if score < 6.5][:5]
        if not weak and ranked:
            weak = [ranked[0][0]]

        concepts: list[str] = []
        coding: list[CodingQuestionSuggestion] = []
        resources: list[ResourceSuggestion] = []
        for topic in weak:
            knowledge = knowledge_for(topic)
            concepts.extend(knowledge["points"][:2])
            for problem in knowledge["problems"][:1]:
                coding.append(
                    CodingQuestionSuggestion(
                        title=problem,
                        topic=topic,
                        difficulty=Difficulty.MEDIUM,
                        why=f"Directly targets your weakest area in this interview ({topic}).",
                    )
                )
            for resource in knowledge["resources"][:1]:
                resources.append(
                    ResourceSuggestion(
                        title=resource,
                        kind="documentation",
                        detail=f"Reference material for {topic}.",
                    )
                )

        daily: list[DailyPlanItem] = []
        focus_cycle = weak or ["interview fundamentals"]
        for day in range(1, 8):
            focus = focus_cycle[(day - 1) % len(focus_cycle)]
            if day == 7:
                daily.append(
                    DailyPlanItem(
                        day=7,
                        focus="Full mock interview",
                        activities=[
                            "Run a full timed practice interview in IntervueX",
                            "Re-answer the two questions you scored lowest on",
                            "Compare against last week's feedback",
                        ],
                        estimated_minutes=75,
                    )
                )
            else:
                daily.append(
                    DailyPlanItem(
                        day=day,
                        focus=str(focus),
                        activities=[
                            f"Review the fundamentals of {focus} for 25 minutes",
                            f"Solve one practice problem on {focus}",
                            "Write a 150-word spoken-style answer and read it aloud",
                        ],
                        estimated_minutes=60,
                    )
                )

        project_suggestions = [
            f"Add a written design note to {project} covering the trade-offs you chose - "
            "you will reuse it verbatim in interviews."
            for project in ctx.projects[:2]
        ] or [
            "Build one small project that exercises your weakest topic end to end, "
            "and document the decisions as you go."
        ]

        band = (
            "strong overall"
            if overall_score >= 7.5
            else "solid with clear gaps"
            if overall_score >= 5.5
            else "early - the fundamentals need work first"
        )
        overview = (
            f"You scored {overall_score:.1f}/10 across this interview, which is {band}. "
            f"The clearest gaps are {', '.join(weak) if weak else 'consistency across topics'}. "
            "This plan spends a week closing them, ending in a full mock interview."
        )

        return ImprovementPlanOutput(
            overview=overview,
            weak_topics=weak,
            recommended_concepts=concepts[:8],
            daily_plan=daily,
            coding_questions=coding[:6],
            project_suggestions=project_suggestions[:4],
            resources=resources[:6],
        )

    # -- document parsing --------------------------------------------------- #

    _SECTION_PATTERNS = {
        "skills": r"(?:technical\s+)?skills?|technologies|tech\s+stack|competenc",
        "education": r"education|academics?|qualification",
        "experience": r"experience|employment|work\s+history|professional",
        "projects": r"projects?|portfolio",
        "certifications": r"certificat|licen[sc]e|courses?",
    }

    def _split_sections(self, text: str) -> dict[str, list[str]]:
        lines = [line.strip() for line in text.splitlines()]
        sections: dict[str, list[str]] = {key: [] for key in self._SECTION_PATTERNS}
        current: str | None = None
        for line in lines:
            if not line:
                continue
            stripped = line.strip(" :#*-•\t")
            matched = None
            # A heading is short and matches a section name.
            if len(stripped) <= 40:
                for key, pattern in self._SECTION_PATTERNS.items():
                    if re.search(pattern, stripped, re.IGNORECASE):
                        matched = key
                        break
            if matched:
                current = matched
                continue
            if current:
                sections[current].append(line.lstrip("-•* \t"))
        return sections

    def parse_resume(self, text: str) -> ParsedResumeProfile:
        sections = self._split_sections(text)

        skills: list[str] = []
        for line in sections["skills"]:
            # Skill lines are usually comma/pipe/slash separated lists.
            parts = re.split(r"[,|/;•]|\s{2,}", line)
            for part in parts:
                cleaned = part.strip(" .:-")
                # Drop the "Languages:" style prefix if present.
                if ":" in cleaned:
                    cleaned = cleaned.split(":", 1)[1].strip()
                if 1 < len(cleaned) <= 40:
                    skills.append(cleaned)

        years: float | None = None
        match = re.search(r"(\d{1,2}(?:\.\d)?)\s*\+?\s*years?", text, re.IGNORECASE)
        if match:
            try:
                years = min(60.0, float(match.group(1)))
            except ValueError:
                years = None

        name: str | None = None
        for line in text.splitlines():
            candidate = line.strip()
            if 3 <= len(candidate) <= 60 and re.fullmatch(
                r"[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){1,3}", candidate
            ):
                name = candidate
                break

        return ParsedResumeProfile(
            full_name=name,
            headline=None,
            location=None,
            years_of_experience=years,
            skills=list(dict.fromkeys(skills))[:40],
            education=sections["education"][:6],
            experience=sections["experience"][:10],
            projects=sections["projects"][:10],
            certifications=sections["certifications"][:8],
            summary=None,
        )

    def parse_job_description(self, text: str) -> ParsedJobDescription:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = "Software Engineer"
        for line in lines[:8]:
            if 5 <= len(line) <= 80 and re.search(
                r"engineer|developer|scientist|analyst|manager|designer|architect|intern",
                line,
                re.IGNORECASE,
            ):
                title = line.strip(" -:#*")
                break

        company = None
        match = re.search(r"\bat\s+([A-Z][\w&.\- ]{2,40})", text)
        if match:
            company = match.group(1).strip(" .,")

        seniority = None
        match = re.search(
            r"\b(intern|junior|entry[- ]level|mid[- ]level|senior|staff|principal|lead)\b",
            text,
            re.IGNORECASE,
        )
        if match:
            seniority = match.group(1).title()

        required: list[str] = []
        for line in lines:
            if re.match(r"^[-•*]|\d+\.", line) and 5 < len(line) < 200:
                required.append(line.lstrip("-•*0123456789. ").strip())

        return ParsedJobDescription(
            title=title[:255],
            company=company,
            seniority=seniority,
            required_skills=required[:20],
            responsibilities=required[:20],
        )


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Resolve the configured LLM provider (memoised)."""
    global _provider
    if _provider is not None:
        return _provider

    choice = settings.llm_provider
    wants_anthropic = choice == "anthropic" or (
        choice == "auto" and bool(settings.anthropic_api_key)
    )
    wants_groq = choice == "groq" or (
        choice == "auto" and not wants_anthropic and bool(settings.groq_api_key)
    )

    if wants_anthropic:
        try:
            _provider = AnthropicProvider(settings.anthropic_api_key, settings.llm_model)
            logger.info("LLM provider: anthropic (%s)", settings.llm_model)
            return _provider
        except Exception as exc:  # pragma: no cover - depends on the environment
            if choice == "anthropic":
                raise
            logger.warning("Could not initialise the Anthropic client (%s); using offline", exc)

    if wants_groq:
        if not settings.groq_api_key:
            raise RuntimeError("LLM_PROVIDER=groq requires GROQ_API_KEY to be set")
        try:
            _provider = GroqProvider(settings.groq_api_key, settings.groq_model)
            logger.info("LLM provider: groq (%s)", settings.groq_model)
            return _provider
        except Exception as exc:  # pragma: no cover - depends on the environment
            if choice == "groq":
                raise
            logger.warning("Could not initialise the Groq client (%s); using offline", exc)

    _provider = OfflineProvider()
    logger.info(
        "LLM provider: offline (deterministic). Set ANTHROPIC_API_KEY for real generation."
    )
    return _provider


def reset_llm_provider() -> None:
    """Clear the memoised provider (used by tests)."""
    global _provider
    _provider = None
