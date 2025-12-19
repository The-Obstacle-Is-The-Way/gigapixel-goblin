# BUG-020: “Official” Supplementary Prompts Not Incorporated

## Severity: P3 (Paper faithfulness / Reproducibility)

## Status: Open (Blocked on external artifact)

## Description
The GIANT paper states that the system prompt used for OpenAI and Anthropic models is included in the **Supplementary Material**. This repository’s prompt templates explicitly note that they are **reverse-engineered placeholders** pending that official text.

## Why This Matters
- **Exact paper replication:** Prompting details can change behavior materially; without the official prompts we cannot claim an exact reproduction of the paper’s prompting strategy.
- **Spec accuracy:** Spec-07 documents this as an explicit caveat, but it remains an unresolved dependency for full paper-faithful reproduction.

## Evidence
- Paper: `_literature/markdown/giant/giant.md` states the OpenAI/Anthropic system prompt is in the Supplementary Material.
- Code: `src/giant/prompts/templates.py` includes a placeholder warning.
- Spec: `docs/specs/spec-07-navigation-prompt.md` contains a “Note on Official Prompts” acknowledging this gap.

## Proposed Fix
1. Acquire the Supplementary Material prompt text(s) (OpenAI + Anthropic variants).
2. Version and integrate the exact prompt strings into `src/giant/prompts/templates.py`.
3. Add tests asserting key invariant phrases/structure from the official prompts (so future edits don’t drift).
