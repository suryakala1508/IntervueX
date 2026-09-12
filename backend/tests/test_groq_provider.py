"""The Groq provider's schema handling and response validation.

These run offline: the HTTP layer is stubbed. What is worth testing is the part
that is easy to get wrong - turning a Pydantic schema into the strict JSON
subset Groq accepts, and refusing to pass a malformed response upstream.
"""

from __future__ import annotations

import json

import pytest

from app.ai.llm import GroqProvider, LLMError, _strictify
from app.ai.schemas import AnswerEvaluation, GeneratedQuestion


def every_object(node):
    """Yield every object-typed subschema, so assertions can cover nested models."""
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for value in node.values():
            yield from every_object(value)
    elif isinstance(node, list):
        for item in node:
            yield from every_object(item)


class TestStrictify:
    def test_every_object_forbids_extra_properties(self) -> None:
        schema = _strictify(AnswerEvaluation.model_json_schema())

        objects = list(every_object(schema))
        assert objects, "the schema should contain at least one object"
        assert all(obj["additionalProperties"] is False for obj in objects)

    def test_every_property_is_required(self) -> None:
        # Strict mode has no notion of an optional field; omitting one is an error.
        schema = _strictify(AnswerEvaluation.model_json_schema())

        for obj in every_object(schema):
            assert set(obj["required"]) == set(obj.get("properties", {}))

    def test_unsupported_keywords_are_dropped(self) -> None:
        # AnswerEvaluation bounds its scores with ge/le, which Pydantic emits as
        # minimum/maximum - not part of the strict dialect.
        raw = json.dumps(AnswerEvaluation.model_json_schema())
        assert "minimum" in raw, "precondition: the model should carry bounds"

        strict = json.dumps(_strictify(AnswerEvaluation.model_json_schema()))
        for keyword in ("minimum", "maximum", "default", "minItems", "maxLength"):
            assert f'"{keyword}"' not in strict

    def test_the_shape_of_the_schema_survives(self) -> None:
        schema = _strictify(AnswerEvaluation.model_json_schema())

        assert schema["type"] == "object"
        assert set(schema["properties"]) == set(AnswerEvaluation.model_fields)
        assert schema["properties"]["strengths"]["type"] == "array"

    def test_nested_models_are_rewritten_too(self) -> None:
        from app.ai.schemas import ImprovementPlanOutput

        schema = _strictify(ImprovementPlanOutput.model_json_schema())

        # The plan nests DailyPlanItem and friends under $defs.
        assert "$defs" in schema
        nested = list(every_object(schema["$defs"]))
        assert nested
        assert all(obj["additionalProperties"] is False for obj in nested)

    def test_enums_are_preserved(self) -> None:
        # Dropping these would let the model invent a category or difficulty.
        schema = _strictify(GeneratedQuestion.model_json_schema())

        defs = schema["$defs"]
        assert defs["Difficulty"]["enum"] == ["easy", "medium", "hard"]
        assert set(defs["QuestionCategory"]["enum"]) == {
            "technical",
            "project",
            "behavioral",
            "role_specific",
        }

    def test_a_non_schema_value_passes_through_unchanged(self) -> None:
        assert _strictify("text") == "text"
        assert _strictify(7) == 7
        assert _strictify([1, 2]) == [1, 2]


def make_provider() -> GroqProvider:
    return GroqProvider("test-key", "openai/gpt-oss-120b")


def completion(content: str, finish_reason: str = "stop") -> dict:
    return {"choices": [{"finish_reason": finish_reason, "message": {"content": content}}]}


VALID_EVALUATION = {
    "score": 8,
    "correctness": 8,
    "relevance": 9,
    "clarity": 7,
    "completeness": 7,
    "communication": 8,
    "quality": "strong",
    "strengths": ["Named the right tool"],
    "weaknesses": [],
    "suggestions": [],
    "missed_points": [],
    "rationale": "Solid and concrete.",
}


class TestResponseValidation:
    def test_a_valid_response_is_parsed_into_the_model(self) -> None:
        result = make_provider()._validate(
            completion(json.dumps(VALID_EVALUATION)), AnswerEvaluation
        )

        assert isinstance(result, AnswerEvaluation)
        assert result.score == 8
        assert result.quality == "strong"

    def test_a_truncated_response_is_reported_as_such(self) -> None:
        # Silently accepting half a plan would be worse than failing.
        with pytest.raises(LLMError, match="token limit"):
            make_provider()._validate(
                completion('{"score": 8', finish_reason="length"), AnswerEvaluation
            )

    def test_non_json_content_is_rejected(self) -> None:
        with pytest.raises(LLMError, match="not JSON"):
            make_provider()._validate(
                completion("I'm sorry, I can't help with that."), AnswerEvaluation
            )

    def test_an_empty_response_is_rejected(self) -> None:
        with pytest.raises(LLMError, match="empty"):
            make_provider()._validate(completion("   "), AnswerEvaluation)

    def test_out_of_range_values_are_caught_by_the_model(self) -> None:
        # The bounds stripped for strict mode are still enforced here, which is
        # the reason dropping them from the schema is safe.
        payload = {**VALID_EVALUATION, "score": 47}

        with pytest.raises(LLMError, match="did not match"):
            make_provider()._validate(completion(json.dumps(payload)), AnswerEvaluation)

    def test_a_missing_field_is_caught(self) -> None:
        payload = {key: value for key, value in VALID_EVALUATION.items() if key != "score"}

        with pytest.raises(LLMError, match="did not match"):
            make_provider()._validate(completion(json.dumps(payload)), AnswerEvaluation)

    def test_an_unexpected_envelope_is_reported_clearly(self) -> None:
        with pytest.raises(LLMError, match="Unexpected response shape"):
            make_provider()._validate({"error": "something went wrong"}, AnswerEvaluation)
