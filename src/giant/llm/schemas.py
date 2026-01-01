"""Shared JSON schemas for LLM structured outputs.

We intentionally hand-author the JSON Schema for `StepResponse` instead of using
`pydantic`'s `model_json_schema()` output because:
- Provider "strict JSON schema" support often has limitations around `$ref`
  / `$defs`.
- A small, explicit schema is easier to reason about and test.
- OpenAI's structured output doesn't support `oneOf`, requiring a flattened schema.
"""

from __future__ import annotations

from typing import Any


def step_response_json_schema() -> dict[str, Any]:
    """Return a provider-friendly JSON Schema for `StepResponse`.

    This schema uses `oneOf` for the action discriminated union.
    Works with Anthropic tool use but NOT OpenAI structured output.
    For OpenAI, use `step_response_json_schema_openai()`.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reasoning": {
                "type": "string",
                "minLength": 1,
                "description": "Concise reasoning for the action",
            },
            "action": {
                "description": "The action to take",
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "action_type": {"type": "string", "enum": ["crop"]},
                            "x": {"type": "integer", "minimum": 0},
                            "y": {"type": "integer", "minimum": 0},
                            "width": {"type": "integer", "exclusiveMinimum": 0},
                            "height": {"type": "integer", "exclusiveMinimum": 0},
                        },
                        "required": ["action_type", "x", "y", "width", "height"],
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "action_type": {"type": "string", "enum": ["answer"]},
                            "answer_text": {"type": "string", "minLength": 1},
                        },
                        "required": ["action_type", "answer_text"],
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "action_type": {"type": "string", "enum": ["conch"]},
                            "hypotheses": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                                "description": "Text hypotheses to score with CONCH",
                            },
                        },
                        "required": ["action_type", "hypotheses"],
                    },
                ],
            },
        },
        "required": ["reasoning", "action"],
    }


def step_response_json_schema_openai() -> dict[str, Any]:
    """Return an OpenAI-compatible JSON Schema for `StepResponse`.

    OpenAI's structured output doesn't support `oneOf`, so we flatten the
    action union into a single object with all fields. The `action_type`
    discriminator indicates which fields are meaningful.

    Schema design:
    - `action_type`: "crop", "answer", or "conch" (discriminator)
    - For "crop": x, y, width, height are populated; answer_text is null
    - For "answer": answer_text is populated; x, y, width, height are null
    - For "conch": hypotheses is populated; all other action fields are null
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reasoning": {
                "type": "string",
                "minLength": 1,
                "description": "Concise reasoning for the action",
            },
            "action": {
                "type": "object",
                "additionalProperties": False,
                "description": "Action: crop (x/y/width/height) or answer (text)",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["crop", "answer", "conch"],
                        "description": (
                            "crop=zoom region, answer=final response, "
                            "conch=score hypotheses"
                        ),
                    },
                    "x": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                        "description": "X coord (crop only, null for answer)",
                    },
                    "y": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                        "description": "Y coord (crop only, null for answer)",
                    },
                    "width": {
                        "type": ["integer", "null"],
                        "exclusiveMinimum": 0,
                        "description": "Width (crop only, null for answer)",
                    },
                    "height": {
                        "type": ["integer", "null"],
                        "exclusiveMinimum": 0,
                        "description": "Height (crop only, null for answer)",
                    },
                    "answer_text": {
                        "type": ["string", "null"],
                        "minLength": 1,
                        "description": "Final answer (answer only, null for crop)",
                    },
                    "hypotheses": {
                        "type": ["array", "null"],
                        "minItems": 1,
                        "description": (
                            "Text hypotheses to score (conch only, null otherwise)"
                        ),
                        "items": {"type": "string", "minLength": 1},
                    },
                },
                "required": [
                    "action_type",
                    "x",
                    "y",
                    "width",
                    "height",
                    "answer_text",
                    "hypotheses",
                ],
            },
        },
        "required": ["reasoning", "action"],
    }
