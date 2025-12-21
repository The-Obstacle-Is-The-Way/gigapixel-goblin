# BUG-029: Low TCGA Benchmark Accuracy Investigation

## Severity: P3 (Investigation - Not a Bug)

## Status: Investigated - Expected Behavior

## Observation

After fixing BUG-027/028, a 5-item TCGA benchmark run showed:
- **0% accuracy** (0/5 correct)
- **0% extraction failures** (down from 88%)

This initially seemed suspicious, but investigation reveals this is expected behavior.

---

## Evidence

### Test Run Configuration

```
max_steps: 2
items: 5
provider: openai (gpt-5.2)
```

### Results

| Item | Predicted | Truth | Correct |
|------|-----------|-------|---------|
| TCGA-06-0875-01Z-00-DX1 | 4 (Lung squamous) | 1 (GBM) | No |
| TCGA-06-0875-01Z-00-DX2 | 4 (Lung squamous) | 1 (GBM) | No |
| TCGA-08-0386-01Z-00-DX1 | 19 | 1 (GBM) | No |
| TCGA-08-0348-01Z-00-DX1 | 26 | 1 (GBM) | No |
| TCGA-12-3648-01Z-00-DX1 | 19 | 1 (GBM) | No |

### Model Reasoning (Turn 2)

```
"On the zoomed region, tissue is composed of cohesive nests/sheets of
atypical epithelial cells with high cellularity and prominent hemorrhage.
There is suggestion of keratinization/whorled squamoid nests rather than
gland formation (no clear acini/papillae/mucin). This fits best with
squamous cell carcinoma"
```

The model IS analyzing the histopathology and making a reasoned (but wrong) diagnosis.

---

## Root Cause Analysis

### 1. Sample Size

- 5 samples is statistically insignificant
- Random chance on 30-way classification: 3.3%
- 0/5 is not surprising with small samples

### 2. max_steps Configuration

From the GIANT paper:
> "For more challenging benchmarks such as TCGA and PANDA, accuracy
> continues to increase up to 20 iterations. Across datasets, we found
> that the best-performing configuration used T = 20."

We ran with `max_steps=2`. The paper shows accuracy improves significantly
with more navigation steps.

### 3. Paper-Reported Accuracy

| Mode | TCGA Accuracy |
|------|---------------|
| Thumbnail baseline | 9.2% |
| Patch baseline | 12.8% |
| GIANT (T=20) | 32.3% |
| Random chance | 3.3% |

Even the paper's best GIANT configuration only achieves 32.3% on this
30-way classification task.

---

## Conclusion

**This is NOT a bug.** The 0% accuracy is explained by:

1. **Small sample (n=5)**: 0/5 is within expected variance for 32% base rate
2. **Low max_steps (2 vs 20)**: Paper shows accuracy improves with more steps
3. **Hard task**: 30-way cancer classification from histopathology is inherently difficult

The fixes (BUG-027/028) are working correctly:
- Extraction failures: 88% → 0%
- Model sees correct options (verified in trajectory)
- Model outputs valid JSON answers
- Model provides medical reasoning

---

## Recommendations

1. **For production benchmarks**: Use `max_steps=20` as per paper
2. **For smoke tests**: Low accuracy is expected with `max_steps=2`
3. **For validation**: Focus on extraction success rate, not accuracy

---

## Verification Checklist

- [x] Options correctly parsed (737/737)
- [x] Options correctly injected into prompts
- [x] Model sees numbered options (verified in trajectory)
- [x] Model outputs valid JSON answer format
- [x] Extraction correctly maps answer to label
- [x] Model reasoning shows actual pathology analysis

---

## References

- GIANT Paper: "diagnostic accuracy improves rapidly over the first few
  iterations and plateaus after approximately 10–15 steps"
- Previous benchmark (pre-fix): 88% extraction failures
- Current benchmark (post-fix): 0% extraction failures
