# BUG-028: Options Not Displayed in Prompts (tcga_slidebench, tcga_expert_vqa)

## Severity: P2 (Medium - affects 2 benchmarks, accuracy may be reduced)

## Status: Fixed

## Description

The `tcga_slidebench` and `tcga_expert_vqa` benchmarks have answer options in the CSV, but their prompt templates do not include the `{options}` placeholder. This means the model sees the question but not the available choices, forcing it to guess the answer format.

---

## Evidence

### tcga_slidebench

**Prompt in CSV:**
```
What is the secondary Gleason pattern observed in this case of prostate adenocarcinoma?
```

**Options in CSV:**
```
['2', '3', '4', '5']
```

**What the model sees:**
```
What is the secondary Gleason pattern observed in this case of prostate adenocarcinoma?
```

**What the model should see:**
```
What is the secondary Gleason pattern observed in this case of prostate adenocarcinoma?

Select from the following options:
1. 2
2. 3
3. 4
4. 5

Please respond with the number of your answer.
```

### tcga_expert_vqa

**Prompt in CSV:**
```
What is the level of mitotic activity in the abnormal tissue?
```

**Options in CSV:**
```
['Low', 'Medium', 'High', 'Cannot determine']
```

---

## Impact

Without seeing the options, the model may:
1. Answer in free-form text that doesn't match extraction patterns
2. Use different terminology than the expected options
3. Provide correct diagnoses that don't match the expected answer format

This likely reduces accuracy even when the model's reasoning is correct.

---

## Affected Code

`src/giant/eval/runner.py` (pre-fix):

```python
# Build prompt (substitute {options} if needed)
prompt = row.get("prompt", row.get("question", ""))
if options and "{options}" in prompt:  # This check FAILS
    formatted_options = "\n".join(
        f"{i}. {opt}" for i, opt in enumerate(options, start=1)
    )
    prompt = prompt.replace("{options}", formatted_options)
```

The check `"{options}" in prompt` evaluates to `False`, so options are never added.

---

## Proposed Fix

### Option 1: Append Options If Not Present (Recommended)

```python
# Build prompt (substitute {options} if needed)
prompt = row.get("prompt", row.get("question", ""))
if options:
    formatted_options = "\n".join(
        f"{i}. {opt}" for i, opt in enumerate(options, start=1)
    )
    if "{options}" in prompt:
        prompt = prompt.replace("{options}", formatted_options)
    else:
        # Append options if placeholder missing
        prompt = (
            f"{prompt}\n\n"
            f"Select from the following options:\n{formatted_options}\n\n"
            f"Please respond with the number of your answer."
        )
```

### Option 2: Fix the CSV

Add `{options}` placeholder to all prompts in `MultiPathQA.csv`. This requires editing the source data.

---

## Resolution

Fixed by always injecting options into the prompt when an `options` list is present:

- If `{options}` exists in the prompt, substitute it with a formatted list.
- Otherwise, append a standardized options block and instruct the model to respond with a
  1-based option index.

- Code: `src/giant/eval/runner.py` (`BenchmarkRunner._inject_options`)
- Tests: `tests/unit/eval/test_runner.py` (`test_appends_options_when_placeholder_missing`)

---

## Testing Checklist

- [x] Add unit test: prompts with `{options}` placeholder work correctly
- [x] Add unit test: prompts without `{options}` get options appended
- [ ] Verify `tcga_slidebench` and `tcga_expert_vqa` show options to model
- [ ] Run sample inference to confirm answer extraction works

---

## References

- Related: BUG-027 (options parsing issue - must fix first)
- CSV data: `data/multipathqa/MultiPathQA.csv`
- Loader: `src/giant/eval/runner.py`
