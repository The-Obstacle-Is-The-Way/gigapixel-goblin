---
annotations_creators:
- expert-generated
- machine-generated
language:
- en
license: cc-by-4.0
multilinguality:
- monolingual
pretty_name: MultiPathQA
size_categories:
- n<1K
source_datasets:
- TCGA
- GTEx
- PANDA Challenge
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
- **Repository:** [https://github.com/Harvard-Ophthalmology-AI-Lab/GIANT](https://github.com/Harvard-Ophthalmology-AI-Lab/GIANT)
- **Paper:** [Navigating Gigapixel Pathology Images with Large Multimodal Models](https://arxiv.org/abs/2506.XXXXX)
- **Point of Contact:** Thomas A. Buckley (Harvard Medical School)

### Dataset Summary

MultiPathQA is a benchmark dataset for evaluating large multimodal models (LMMs) on **whole-slide image (WSI) question answering** in computational pathology. The dataset comprises **934 WSI-level questions** spanning **862 unique whole-slide images** across five clinically-relevant diagnostic tasks.

MultiPathQA is designed to evaluate whether LMMs can reason coherently and accurately over gigapixel pathology images. It accompanies the **GIANT (Gigapixel Image Agent for Navigating Tissue)** framework, which enables LMMs to iteratively pan, zoom, and reason across WSIs like a pathologist.

A key distinguishing feature of MultiPathQA is **ExpertVQA**, a subset of 128 questions authored by two professional pathologists (one resident, one board-certified attending) that require direct slide interpretation at multiple scales—the first pathologist-generated WSI question-answering benchmark.

### Supported Tasks and Leaderboards

MultiPathQA supports evaluation across five distinct pathology tasks:

| Task | Description | # Questions | # WSIs | Metric |
|------|-------------|-------------|--------|--------|
| **GTEx** | 20-way organ classification from non-diseased tissue | 191 | 191 | Balanced Accuracy |
| **TCGA** | 30-way cancer type diagnosis | 221 | 221 | Balanced Accuracy |
| **PANDA** | 6-class prostate cancer ISUP grading (0-5) | 197 | 197 | Balanced Accuracy |
| **SlideBenchVQA** | Free-form VQA from SlideChat benchmark | 197 | 183 | Accuracy |
| **ExpertVQA** | Pathologist-authored diagnostic questions | 128 | 76 | Accuracy |

**Benchmark Results (from GIANT paper):**

| Model | TCGA | GTEx | PANDA | SlideBenchVQA | ExpertVQA |
|-------|------|------|-------|---------------|-----------|
| GPT-5 + GIANT | 32.3% | 53.7% | 23.2% | 58.9% | 57.0% |
| GPT-5 + GIANT x5 | 29.3% | 60.7% | 25.4% | 59.4% | **62.5%** |
| TITAN (zero-shot) | **88.8%** | **96.3%** | 27.5% | 39.6% | 43.8% |
| SlideChat (zero-shot) | 3.3% | 5.0% | 17.0% | **71.6%** | 37.5% |

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
  "options": "['Low', 'Moderate', 'High', 'Very High']",
  "image_exists": true,
  "patch_exists": true,
  "is_valid": true,
  "metric_type": "accuracy",
  "file_id": "TCGA-HT-A616-01Z-00-DX1",
  "prompt": "What is the level of mitotic activity in the abnormal tissue?"
}
```

### Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `benchmark_name` | string | Task identifier: `gtex`, `tcga`, `panda`, `tcga_slidebench`, or `tcga_expert_vqa` |
| `benchmark_id` | string | Unique identifier for the question within its benchmark |
| `image_path` | string | Filename of the whole-slide image (`.svs` or `.tiff` format) |
| `answer` | string | Ground truth answer (organ name, class number, or diagnosis) |
| `options` | string | JSON-formatted list of multiple-choice options |
| `image_exists` | bool | Whether the WSI file is available |
| `patch_exists` | bool | Whether pre-extracted patches exist for the WSI |
| `is_valid` | bool | Whether the instance passed quality control |
| `metric_type` | string | Evaluation metric: `balanced_accuracy` or `accuracy` |
| `file_id` | string | Base identifier for the WSI (without extension) |
| `prompt` | string | The question prompt template for the model |

### Data Splits

MultiPathQA is released as a single evaluation set. It is intended for **benchmarking only**—not for training.

| Split | Examples |
|-------|----------|
| train | 934 |

> **Note:** The split is named "train" for compatibility with the Hugging Face datasets library, but this dataset should be used exclusively for evaluation purposes.

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

- **Source:** Subset of SlideChat-VQA-TCGA-plus benchmark
- **Task:** Free-form visual question answering
- **Note:** Questions were generated from TCGA pathology reports

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

1. **TCGA (The Cancer Genome Atlas):** Cancer tissue samples with pathologist-verified diagnoses. WSIs from the TCGA Uniform cohort were used after quality screening.

2. **GTEx (Genotype-Tissue Expression):** Non-diseased donor tissues with quality control for tissue integrity, autolysis, and processing artifacts.

3. **PANDA Challenge:** Prostate tissue biopsies with ISUP grade annotations from the Prostate cANcer graDe Assessment challenge (10,616 WSIs total).

#### Who are the source data producers?

- **TCGA:** National Cancer Institute (NCI) and National Human Genome Research Institute (NHGRI)
- **GTEx:** NIH Common Fund GTEx Consortium
- **PANDA:** Organized by Radboud University Medical Center with contributions from pathologists worldwide

### Annotations

#### Annotation Process

- **GTEx/TCGA/PANDA:** Labels derived from established clinical annotations in source datasets
- **SlideBenchVQA:** Questions generated from TCGA pathology reports using LLM-based pipelines (see SlideChat paper)
- **ExpertVQA:**
  - Two pathologists (one resident, one board-certified attending) reviewed slides
  - 90 WSIs selected via stratified sampling across 20 primary sites
  - Pathologists formulated 1-3 diagnostic questions per selected slide
  - Each question includes 4 answer choices with one verified correct label

#### Who are the annotators?

- **ExpertVQA:** Two professional pathologists from Massachusetts General Hospital and Brown University
- **Other benchmarks:** Annotations inherited from source datasets (TCGA, GTEx, PANDA) or prior work (SlideBench)

### Personal and Sensitive Information

WSIs in TCGA and GTEx are derived from de-identified tissue samples. Patient identifiers have been removed from all source datasets. The PANDA Challenge data was collected with appropriate IRB approval and de-identification protocols.

## Considerations for Using the Data

### Social Impact of Dataset

MultiPathQA aims to advance AI systems for computational pathology, which could:

- **Positive impacts:** Improve diagnostic accuracy, reduce pathologist workload, enable faster diagnoses in resource-limited settings
- **Potential risks:** Over-reliance on AI without expert oversight, disparities in performance across patient populations

### Discussion of Biases

Several potential biases should be considered:

1. **Geographic bias:** TCGA and GTEx samples are primarily from U.S. institutions
2. **Demographic representation:** May not fully represent global population diversity
3. **Question generation bias:** SlideBenchVQA questions were generated using LLMs, which may introduce systematic biases
4. **Cancer type distribution:** Stratified sampling was used, but rare cancer types may be underrepresented

### Other Known Limitations

1. **WSI availability:** This dataset contains metadata and prompts only—actual WSI files must be obtained from original sources (TCGA, GTEx, PANDA)
2. **File sizes:** WSIs are gigapixel images (typically 0.5-5 GB each); full benchmark requires ~500+ GB storage
3. **SlideBenchVQA overlap:** SlideChat was trained on data generated by the same pipeline as SlideBenchVQA, potentially inflating its benchmark scores
4. **Low-resolution limitations:** As noted in the paper, some SlideBench WSIs have unusually small file sizes suggestive of low-magnification scanning

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

This dataset is released under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** license.

Note that the underlying WSIs are subject to their original data use agreements:
- **TCGA:** Open access with acknowledgment requirements
- **GTEx:** dbGaP access for some data types
- **PANDA:** Kaggle competition terms

### Citation Information

If you use MultiPathQA in your research, please cite:

```bibtex
@article{buckley2025giant,
  title={Navigating Gigapixel Pathology Images with Large Multimodal Models},
  author={Buckley, Thomas A. and Weihrauch, Kian R. and Latham, Katherine and Zhou, Andrew Z. and Manrai, Padmini A. and Manrai, Arjun K.},
  journal={arXiv preprint},
  year={2025}
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
from datasets import load_dataset

# Load the dataset
dataset = load_dataset("tbuckley/MultiPathQA")

# Filter by benchmark
gtex_questions = dataset["train"].filter(lambda x: x["benchmark_name"] == "gtex")
expert_vqa = dataset["train"].filter(lambda x: x["benchmark_name"] == "tcga_expert_vqa")

# View a sample
print(expert_vqa[0])
```

## Data Acquisition

To obtain the actual WSI files:

1. **TCGA:** [GDC Data Portal](https://portal.gdc.cancer.gov/)
2. **GTEx:** [GTEx Portal](https://gtexportal.org/)
3. **PANDA:** [Kaggle PANDA Challenge](https://www.kaggle.com/c/prostate-cancer-grade-assessment)

For detailed download instructions, see the [GIANT repository](https://github.com/Harvard-Ophthalmology-AI-Lab/GIANT).
