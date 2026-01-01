# BUG-040-P1-2: OpenAI `StepResponse` Schema Hardening

**Status**: IMPLEMENTED (2026-01-01)
**Severity**: P1 (reliability + benchmark correctness)
**Components**:
- `src/giant/llm/schemas.py` (`step_response_json_schema_openai`)
- `src/giant/llm/openai_client.py` (`_build_json_schema` → `step_response_json_schema_openai`)

## Overview

The OpenAI structured output JSON schema for `StepResponse` was previously **less strict** than the
Pydantic `StepResponse` model constraints. This mismatch allows OpenAI to emit values that pass
schema validation but fail Pydantic validation, producing `LLMParseError` retries and occasionally
hard item failures that count as incorrect in benchmarks.

This spec tightens `step_response_json_schema_openai()` to align with `src/giant/llm/protocol.py`
field constraints without changing the Pydantic models.

## Root Cause Analysis

### Contract: Pydantic constraints (ground truth)

`StepResponse.reasoning` is required and must be non-empty:
- `src/giant/llm/protocol.py:88` (`reasoning: str = Field(..., min_length=1, ...)`)

`BoundingBoxAction` requires non-negative coords and strictly positive dimensions:
- `src/giant/llm/protocol.py:33` (`x: int = Field(..., ge=0, ...)`)
- `src/giant/llm/protocol.py:34` (`y: int = Field(..., ge=0, ...)`)
- `src/giant/llm/protocol.py:35` (`width: int = Field(..., gt=0, ...)`)
- `src/giant/llm/protocol.py:36` (`height: int = Field(..., gt=0, ...)`)

`FinalAnswerAction.answer_text` must be non-empty:
- `src/giant/llm/protocol.py:47` (`answer_text: str = Field(..., min_length=1, ...)`)

`ConchAction.hypotheses` must have at least 1 item, and each item must be non-empty:
- `src/giant/llm/protocol.py:61` + `src/giant/llm/protocol.py:62` (`hypotheses: list[HypothesisText] = Field(..., min_length=1, ...)`)
- `src/giant/llm/protocol.py:50` (`HypothesisText = Annotated[str, Field(min_length=1)]`)

### Mismatch (pre-fix): OpenAI JSON schema was too permissive

Before this fix, `step_response_json_schema_openai()` omitted multiple constraints, e.g.:
- `reasoning` allowed empty strings
- `x/y` allowed negatives
- `width/height` allowed 0/negatives
- `hypotheses` allowed empty arrays

Because OpenAI structured output uses this schema as the primary constraint surface, the model can
emit values that are schema-valid but Pydantic-invalid, triggering parse retries at runtime.

### Evidence (benchmark artifacts)

- `results/tcga_slidebench_giant_openai_gpt-5.2_results.json`: item `572` failed with
  `action.crop.y = -22000` (`LLMParseError` after max retries).
- `results/tcga-benchmark-20251227-084052.log:416`: example `action.crop.y = -12000` Pydantic failure.

## Implemented Fix

Tighten `step_response_json_schema_openai()` to encode the Pydantic constraints where JSON Schema
can express them, while preserving the “flattened union” shape (OpenAI limitation: no `oneOf`).

### Schema Changes (Implemented)

In `src/giant/llm/schemas.py:90-158`:

- `reasoning`: add `minLength: 1`
- `x`, `y`: add `minimum: 0` (still allow `null` for non-crop actions)
- `width`, `height`: add `exclusiveMinimum: 0` (still allow `null` for non-crop actions)
- `answer_text`: add `minLength: 1` (still allow `null` for non-answer actions)
- `hypotheses`: add `minItems: 1` (still allow `null` for non-conch actions)

### Patch Sketch

```python
# src/giant/llm/schemas.py

def step_response_json_schema_openai() -> dict[str, Any]:
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
                "properties": {
                    "action_type": {"type": "string", "enum": ["crop", "answer", "conch"]},
                    "x": {"type": ["integer", "null"], "minimum": 0},
                    "y": {"type": ["integer", "null"], "minimum": 0},
                    "width": {"type": ["integer", "null"], "exclusiveMinimum": 0},
                    "height": {"type": ["integer", "null"], "exclusiveMinimum": 0},
                    "answer_text": {"type": ["string", "null"], "minLength": 1},
                    "hypotheses": {
                        "type": ["array", "null"],
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                },
                "required": ["action_type", "x", "y", "width", "height", "answer_text", "hypotheses"],
            },
        },
        "required": ["reasoning", "action"],
    }
```

## Test Plan

### Unit Tests (schema-level)

Added assertions to ensure OpenAI schema matches Pydantic constraints:
- `tests/unit/llm/test_openai.py::TestBuildJsonSchema::test_schema_enforces_pydantic_field_constraints`

### Regression Coverage (behavior)

No reliable offline test can prove OpenAI will *stop* emitting invalid values, but schema tightening
is verifiable structurally via unit tests and is expected to reduce:
- negative `x/y`
- zero/negative `width/height`
- empty `reasoning`
- empty `hypotheses` arrays

## Acceptance Criteria

- `step_response_json_schema_openai()` enforces the same non-nullable constraints as
  `src/giant/llm/protocol.py` where JSON Schema can express them.
- New/updated unit tests assert the schema constraints (no regressions in OpenAI schema shape).
- No behavior changes outside OpenAI structured-output validation surface (no agent-loop changes).
