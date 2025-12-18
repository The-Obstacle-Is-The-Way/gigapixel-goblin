"""Shared JSON schemas for LLM structured outputs.

We intentionally hand-author the JSON Schema for `StepResponse` instead of using
`pydantic`'s `model_json_schema()` output because:
- Provider "strict JSON schema" support often has limitations around `$ref`
  / `$defs`.
- A small, explicit schema is easier to reason about and test.
"""

from __future__ import annotations

from typing import Any


def step_response_json_schema() -> dict[str, Any]:
    """Return a provider-friendly JSON Schema for `StepResponse`."""
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
                ],
            },
        },
        "required": ["reasoning", "action"],
    }
