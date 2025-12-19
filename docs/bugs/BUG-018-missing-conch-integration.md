# BUG-018: CONCH Tool Ablation Not Implemented (Paper Coverage Gap)

## Severity: P3 (Paper feature gap)

## Status: Open

## Description
The GIANT paper includes an ablation in Section **6.2 “Adding a Pathology Foundation Model to GI-ANT”** where GIANT is augmented with access to the **CONCH** pathology model for localized image–text retrieval. In that variant, the agent can choose between:
- continuing navigation (crop), or
- invoking CONCH with the current crop + a set of textual hypotheses, receiving cosine similarity scores.

This repository currently implements the **baseline Algorithm 1 loop** (thumbnail → repeated crop decisions → final answer) and does **not** implement a CONCH tool action or any generalized tool-calling pathway.

## Why This Matters
- **Paper reproduction:** We cannot reproduce the paper’s “+ CONCH” ablation results (Table 3) without implementing this tool.
- **Architecture:** The action space is currently hard-coded to `crop` / `answer`, so adding specialist tools later likely requires protocol + agent-loop refactoring.

## Evidence
- Paper: `_literature/markdown/giant/giant.md` (Section 6.2) explicitly describes CONCH augmentation and reports results.
- Protocol: `src/giant/llm/protocol.py` defines only `BoundingBoxAction` and `FinalAnswerAction`.
- Agent loop: `src/giant/agent/runner.py` assumes the only non-terminal action is a bounding-box crop.

## Scope / Non-Goals
- This is **not required** for the baseline GIANT loop (Algorithm 1) or the paper’s main comparisons in Table 1; it is specifically for the CONCH ablation variant.

## Proposed Fix (Design-Level)
1. Introduce a tool/action abstraction (e.g., `ToolAction` with a `tool_name` and structured args).
2. Add a `ConchTool` interface (real implementation or stub) that accepts `(image, hypotheses[]) → scores[]`.
3. Expose tool availability + call format in the system prompt and record tool calls + outputs in the trajectory.
4. Keep CONCH optional behind config/flags so core GIANT remains unchanged when CONCH is unavailable.
