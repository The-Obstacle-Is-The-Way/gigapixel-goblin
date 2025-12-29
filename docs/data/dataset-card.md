---
annotations_creators:
- expert-generated
- machine-generated
language:
- en
multilinguality:
- monolingual
pretty_name: MultiPathQA
size_categories:
- n<1K
task_categories:
- visual-question-answering
- image-classification
task_ids:
- multi-class-image-classification
- multiple-choice-qa
tags:
- pathology
- whole-slide-images
- medical-imaging
- computational-pathology
- cancer-diagnosis
- histopathology
- benchmark
- wsi
- gigapixel
- tcga
- gtex
- panda
dataset_info:
  features:
  - name: benchmark_name
    dtype: string
  - name: benchmark_id
    dtype: string
  - name: image_path
    dtype: string
  - name: answer
    dtype: string
  - name: options
    dtype: string
  - name: image_exists
    dtype: bool
  - name: patch_exists
    dtype: bool
  - name: is_valid
    dtype: bool
  - name: metric_type
    dtype: string
  - name: file_id
    dtype: string
  - name: prompt
    dtype: string
  splits:
  - name: train
    num_examples: 934
configs:
- config_name: default
  data_files:
  - split: train
    path: MultiPathQA.csv
---

# Dataset Card for MultiPathQA

## Table of Contents

- [Dataset Description](#dataset-description)
  - [Dataset Summary](#dataset-summary)
  - [Supported Tasks and Leaderboards](#supported-tasks-and-leaderboards)
  - [Languages](#languages)
- [Dataset Structure](#dataset-structure)
  - [Data Instances](#data-instances)
  - [Data Fields](#data-fields)
  - [Data Splits](#data-splits)
  - [Benchmark Tasks](#benchmark-tasks)
- [Dataset Creation](#dataset-creation)
  - [Curation Rationale](#curation-rationale)
  - [Source Data](#source-data)
  - [Annotations](#annotations)
  - [Personal and Sensitive Information](#personal-and-sensitive-information)
- [Considerations for Using the Data](#considerations-for-using-the-data)
  - [Social Impact of Dataset](#social-impact-of-dataset)
  - [Discussion of Biases](#discussion-of-biases)
  - [Other Known Limitations](#other-known-limitations)
- [Additional Information](#additional-information)
  - [Dataset Curators](#dataset-curators)
  - [Licensing Information](#licensing-information)
  - [Citation Information](#citation-information)
  - [Contributions](#contributions)

## Dataset Description

- **Homepage:** [https://huggingface.co/datasets/tbuckley/MultiPathQA](https://huggingface.co/datasets/tbuckley/MultiPathQA)
- **Paper:** [Navigating Gigapixel Pathology Images with Large Multimodal Models](https://arxiv.org/abs/2511.19652)
- **Point of Contact:** Thomas A. Buckley (Harvard Medical School)

### Dataset Summary

MultiPathQA is a benchmark dataset for evaluating large multimodal models (LMMs) on **whole-slide image (WSI) question answering** in computational pathology. The released `MultiPathQA.csv` contains **934 WSI-level questions** spanning **862 unique slides** (unique `file_id` / `image_path`) across five clinically-relevant tasks.

> **Note on WSI counts:** The GIANT paper reports 868 unique WSIs. The difference arises because 6 WSIs appear in multiple benchmarks (e.g., some TCGA slides are used in both the TCGA cancer classification task and SlideBenchVQA). Per-benchmark unique WSI counts sum to 868, but de-duplicating across the entire dataset yields 862.

MultiPathQA is designed to evaluate whether LMMs can reason coherently and accurately over gigapixel pathology images. It accompanies the **GIANT (Gigapixel Image Agent for Navigating Tissue)** framework, which enables LMMs to iteratively pan, zoom, and reason across WSIs like a pathologist.

A key distinguishing feature of MultiPathQA is **ExpertVQA**, a subset of 128 questions authored by two pathologists (one resident, one attending) that require direct slide interpretation at multiple scales—the first pathologist-generated WSI question-answering benchmark.

### Supported Tasks and Leaderboards

MultiPathQA supports evaluation across five distinct pathology tasks:

| Task | Description | # Questions | # WSIs | Metric |
|------|-------------|-------------|--------|--------|
| **GTEx** | 20-way organ classification from non-diseased tissue | 191 | 191 | Balanced Accuracy |
| **TCGA** | 30-way cancer type diagnosis | 221 | 221 | Balanced Accuracy |
| **PANDA** | 6-class prostate cancer ISUP grading (0-5) | 197 | 197 | Balanced Accuracy |
| **SlideBenchVQA** | Multiple-choice VQA sampled from SlideChat-VQA-TCGA-plus | 197 | 183 | Accuracy |
| **ExpertVQA** | Pathologist-authored diagnostic questions | 128 | 76 | Accuracy |

**Benchmark Results (selected rows from GIANT paper Table 1; mean ± bootstrap std.):**

> The full table in the paper includes additional baselines (thumbnail, patch) and other LMMs. Below are representative results for the GIANT agent and specialist pathology models.

| Model | TCGA | GTEx | PANDA | SlideBenchVQA | ExpertVQA |
|-------|------|------|-------|---------------|-----------|
| GPT-5 + GIANT | 32.3 ± 3.5 | 53.7 ± 3.4 | 23.2 ± 2.3 | 58.9 ± 3.5 | 57.0 ± 4.5 |
| GPT-5 + GIANT x5 | 29.3 ± 3.3 | 60.7 ± 3.2 | 25.4 ± 2.0 | 59.4 ± 3.4 | **62.5 ± 4.4** |
| TITAN (zero-shot) | **88.8 ± 1.7** | **96.3 ± 1.3** | 27.5 ± 2.3 | 39.6 ± 3.5 | 43.8 ± 4.2 |
| SlideChat (zero-shot) | 3.3 ± 1.2 | 5.0 ± 0.0 | 17.0 ± 0.4 | **71.6 ± 3.3** | 37.5 ± 4.3 |

### Languages

All prompts and annotations are in **English**.

## Dataset Structure

### Data Instances

An example instance from the GTEx organ classification task:

```json
{
  "benchmark_name": "gtex",
  "benchmark_id": "GTEX-OIZH-0626",
  "image_path": "GTEX-OIZH-0626.tiff",
  "answer": "Esophagus",
  "options": "['Esophagus', 'Artery', 'Skin', 'Adipose', 'Colon', 'Heart', 'Muscle', 'Nerve', 'Stomach', 'Thyroid', 'Breast', 'Spleen', 'Pancreas', 'Lung', 'Brain', 'Small Intestine', 'Adrenal Gland', 'Liver', 'Kidney', 'Prostate']",
  "image_exists": true,
  "patch_exists": true,
  "is_valid": true,
  "metric_type": "balanced_accuracy",
  "file_id": "GTEX-OIZH-0626",
  "prompt": "What organ type is shown in this histopathology image?\n\nSelect from the following options:\n{options}\n\nPlease choose the number of the correct option and respond in the following JSON format:\n```json\n{{\"answer\": YOUR_ANSWER}}\n```\n"
}
```

An example from ExpertVQA (pathologist-authored):

```json
{
  "benchmark_name": "tcga_expert_vqa",
  "benchmark_id": "0",
  "image_path": "TCGA-HT-A616-01Z-00-DX1.svs",
  "answer": "1",
  "options": "['Low', 'Medium', 'High', 'Cannot determine']",
  "image_exists": true,
  "patch_exists": true,
  "is_valid": true,
  "metric_type": "accuracy",
  "file_id": "844da204-79f6-4225-8b94-afeee971fd1a",
  "prompt": "What is the level of mitotic activity in the abnormal tissue?"
}
```

### Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_name` | string | Task identifier: `gtex`, `tcga`, `panda`, `tcga_slidebench`, or `tcga_expert_vqa` |
| `benchmark_id` | string | Unique identifier for the question within its benchmark |
| `image_path` | string | Filename of the whole-slide image (`.svs` or `.tiff` format); the WSI files are not included in this dataset repository |
| `answer` | string | Ground truth answer. For `gtex`, this is the correct label string. For `panda`, this is the ISUP grade group `0`–`5` (stored as a string). For `tcga`, `tcga_slidebench`, and `tcga_expert_vqa`, this is a 1-based index into `options` (stored as a string). |
| `options` | string | String encoding of a Python list of answer choices (parse with `ast.literal_eval`). Missing/empty for `panda`. |
| `image_exists` | bool | Whether the WSI existed in the authors' environment at dataset build time (always `True` in this release) |
| `patch_exists` | bool | Whether pre-extracted patches existed in the authors' environment (always `True` in this release) |
| `is_valid` | bool | Whether the instance passed dataset quality checks (always `True` in this release) |
| `metric_type` | string | Evaluation metric: `balanced_accuracy` or `accuracy` |
| `file_id` | string | Identifier for the WSI. Format varies by benchmark: GTEx uses base filename without extension (e.g., `GTEX-OIZH-0626`); TCGA/SlideBench/ExpertVQA use UUIDs (e.g., `844da204-79f6-4225-8b94-afeee971fd1a`); PANDA uses full filename with extension (e.g., `dbf7cc49ae2e9831448c3ca54ad92708.tiff`). |
| `prompt` | string | The question prompt; for `gtex` and `tcga` it includes a `{options}` placeholder. |

### Data Splits

MultiPathQA is released as a single split (named `train` for compatibility with the Hugging Face datasets CSV loader). The GIANT paper presents MultiPathQA as a benchmark; many users will treat this split as evaluation data rather than training data.

| Split | Examples |
|-------|----------|
| train | 934 |

> **Note:** If you want to compare against the GIANT paper's reported benchmark numbers, avoid training on these items and use them for evaluation only.

### Benchmark Tasks

#### GTEx Organ Classification (191 questions)

- **Source:** Genotype-Tissue Expression (GTEx) Project
- **Task:** 20-way classification of organ/tissue type
- **Classes:** Esophagus, Artery, Skin, Adipose, Colon, Heart, Muscle, Nerve, Stomach, Thyroid, Breast, Spleen, Pancreas, Lung, Brain, Small Intestine, Adrenal Gland, Liver, Kidney, Prostate
- **WSI Format:** `.tiff`

#### TCGA Cancer Diagnosis (221 questions)

- **Source:** The Cancer Genome Atlas (TCGA) Uniform Cohort
- **Task:** 30-way cancer type classification
- **WSI Format:** `.svs`

#### PANDA Prostate Cancer Grading (197 questions)

- **Source:** PANDA Challenge (Prostate cANcer graDe Assessment)
- **Task:** 6-class ISUP grade classification (Grade 0-5)
- **WSI Format:** `.tiff`

#### SlideBenchVQA (197 questions)

- **Source:** Random sample from SlideChat-VQA-TCGA-plus (SlideChat / SlideBench pipeline)
- **Task:** 4-option multiple-choice VQA (answers stored as 1-based indices)
- **Note:** The GIANT paper samples 200 questions; 3 slides were missing or failed segmentation, yielding 197 questions over 183 unique images.

#### ExpertVQA (128 questions)

- **Source:** Original questions authored by two pathologists
- **Task:** Diagnostic questions requiring direct slide interpretation
- **Note:** First pathologist-generated WSI-VQA benchmark

## Dataset Creation

### Curation Rationale

Prior studies evaluating LMMs on pathology used either low-resolution thumbnails or random patches, which likely underestimated model performance. MultiPathQA was created to provide a rigorous benchmark that reflects how pathologists actually analyze slides—by iteratively panning, zooming, and reasoning across the image.

The inclusion of ExpertVQA addresses a critical gap: existing WSI benchmarks rely on automatically-generated questions from pathology reports, which may not require genuine visual understanding. ExpertVQA questions were manually crafted by pathologists after direct slide review.

### Source Data

#### Initial Data Collection and Normalization

WSIs were obtained from three publicly available sources:

1. **TCGA (The Cancer Genome Atlas):** WSIs from the TCGA Uniform cohort were used after quality screening (as described in the GIANT paper).

2. **GTEx (Genotype-Tissue Expression):** Non-diseased donor tissues with quality control for tissue integrity, autolysis, and processing artifacts.

3. **PANDA Challenge:** Prostate tissue biopsies with ISUP grade annotations from the Prostate cANcer graDe Assessment challenge (10,616 WSIs total).

### Annotations

#### Annotation Process

- **GTEx/TCGA/PANDA:** Labels derived from established clinical annotations in source datasets
- **SlideBenchVQA:** Questions generated from TCGA pathology reports using LLM-based pipelines (see SlideChat paper)
- **ExpertVQA:**
  - Two pathologists (one resident, one attending) reviewed slides
  - 90 WSIs were sampled (one per patient) from the TCGA Uniform cohort via stratified sampling across the 20 most frequent primary sites; a subset of 76 WSIs was used for question writing
  - Pathologists formulated 1-3 diagnostic multiple-choice questions per selected slide
  - Each question includes 4 answer choices and one verified correct label

#### Who are the annotators?

- **ExpertVQA:** Two pathologists (one resident, one attending)
- **Other benchmarks:** Annotations inherited from source datasets (TCGA, GTEx, PANDA) or prior work (SlideBench)

### Personal and Sensitive Information

MultiPathQA is distributed as a CSV of prompts, labels, and slide filenames/identifiers; it does not include the underlying WSIs. Please consult the original source datasets (TCGA, GTEx, PANDA, and SlideChat/SlideBench) for their data access controls and usage terms.

## Considerations for Using the Data

### Social Impact of Dataset

MultiPathQA aims to advance AI systems for computational pathology, which could:

- **Positive impacts:** Improve diagnostic accuracy, reduce pathologist workload, enable faster diagnoses in resource-limited settings
- **Potential risks:** Over-reliance on AI without expert oversight, disparities in performance across patient populations

### Discussion of Biases

Potential biases/limitations to consider (not exhaustively analyzed in the GIANT paper) include:

1. **Cohort/site composition:** The underlying source datasets (TCGA, GTEx, PANDA) reflect their respective collection sites and patient populations; consult the source documentation for cohort details.
2. **Question-generation artifacts:** SlideBenchVQA is generated from pathology reports using LLM-based pipelines (per the GIANT paper), which may introduce template artifacts or systematic phrasing biases.
3. **Sampling choices:** Several tasks use stratified sampling (per the GIANT paper), which can affect class/site distributions relative to the full source datasets.

### Other Known Limitations

1. **WSI availability:** This dataset contains metadata and prompts only—actual WSI files must be obtained from original sources (TCGA, GTEx, PANDA)
2. **Storage/compute:** Whole-slide images are large and may require substantial storage and preprocessing to work with at scale
3. **SlideBenchVQA overlap:** SlideChat was trained on data generated by the same pipeline as SlideBenchVQA, potentially inflating its benchmark scores
4. **Low-resolution limitations:** As noted in the paper, some SlideBench WSIs have unusually small file sizes suggestive of low-magnification scanning
5. **Cross-benchmark WSI overlap:** Six WSIs appear in multiple benchmarks. Most notably, one slide (`TCGA-EA-A3HT-01Z-00-DX1.svs`) appears in both ExpertVQA and SlideBenchVQA in the released CSV. The GIANT paper states that patients included in "ExpertPathQA" were excluded from all other datasets; users concerned about leakage should verify overlaps in this release and apply any desired exclusions.

## Additional Information

### Dataset Curators

This dataset was curated by researchers at:

- **Harvard Medical School, Department of Biomedical Informatics**
- **Massachusetts General Hospital, Department of Pathology**
- **Brown University, Department of Pathology and Laboratory Medicine**

Primary curators:
- Thomas A. Buckley*
- Kian R. Weihrauch*
- Katherine Latham
- Andrew Z. Zhou
- Padmini A. Manrai
- Arjun K. Manrai

*Equal contribution

### Licensing Information

No explicit license information is included in the `tbuckley/MultiPathQA` Hugging Face dataset repository at the time of writing. If you plan to redistribute or use this dataset beyond local benchmarking, contact the dataset maintainers for intended terms. The underlying WSIs are subject to the access controls and licensing/terms of the source datasets (TCGA, GTEx, PANDA, and SlideChat/SlideBench).

### Citation Information

If you use MultiPathQA in your research, please cite:

```bibtex
@misc{buckley2025navigating,
  title={Navigating Gigapixel Pathology Images with Large Multimodal Models},
  author={Buckley, Thomas A. and Weihrauch, Kian R. and Latham, Katherine and Zhou, Andrew Z. and Manrai, Padmini A. and Manrai, Arjun K.},
  year={2025},
  eprint={2511.19652},
  archivePrefix={arXiv},
  primaryClass={cs.CV}
}
```

### Contributions

Thanks to the following for their contributions:
- [@tbuckley](https://huggingface.co/tbuckley) for creating and hosting this dataset
- The pathologists who authored ExpertVQA questions
- The GTEx Consortium, TCGA, and PANDA Challenge organizers for making WSI data publicly available
- Smart In Media for providing PathoZoom SlideCloud for pathologist annotations

---

## Quick Start

```python
import ast
from datasets import load_dataset

# Load the dataset
dataset = load_dataset("tbuckley/MultiPathQA")

# Filter by benchmark
gtex_questions = dataset["train"].filter(lambda x: x["benchmark_name"] == "gtex")
expert_vqa = dataset["train"].filter(lambda x: x["benchmark_name"] == "tcga_expert_vqa")

# View a sample and decode the multiple-choice options
row = expert_vqa[0]
options = ast.literal_eval(row["options"])
answer_index = int(row["answer"])  # 1-based
print(row["prompt"])
print("correct:", options[answer_index - 1])
```

## Data Acquisition

To obtain the actual WSI files:

1. **TCGA:** [GDC Data Portal](https://portal.gdc.cancer.gov/)
2. **GTEx:** [GTEx Portal](https://gtexportal.org/)
3. **PANDA:** [Kaggle PANDA Challenge](https://www.kaggle.com/c/prostate-cancer-grade-assessment)

For more details, see the [GIANT paper](https://arxiv.org/abs/2511.19652).
