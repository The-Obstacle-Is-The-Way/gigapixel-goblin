# Data Acquisition Guide

## Overview

GIANT evaluates against the **MultiPathQA** benchmark, which comprises 934 WSI-level questions across 868 unique whole-slide images (WSIs). The benchmark metadata (questions, prompts, answers) is available on HuggingFace, but **the WSI files themselves must be acquired separately** from their original sources due to licensing and size constraints.

**This is a critical operational requirement.** Without the actual WSI files, you cannot:
- Run the GIANT agent on real pathology images
- Reproduce the paper's benchmark results
- Validate the end-to-end system

## Data Components

### 1. MultiPathQA Metadata (Already Available)

| File | Location | Size | Status |
|------|----------|------|--------|
| `MultiPathQA.csv` | `data/multipathqa/` | ~2MB | ✅ Downloaded |

This CSV contains:
- `benchmark_name`: Task identifier (tcga, gtex, panda, etc.)
- `image_path`: Filename of the WSI (e.g., `GTEX-OIZH-0626.tiff`)
- `prompt`: Question to ask about the slide
- `answer`: Ground truth label
- `options`: Multiple choice options (when applicable)

### 2. Whole-Slide Images (Must Be Acquired)

| Source | Count | Format | Size (Approx) | License |
|--------|-------|--------|---------------|---------|
| **TCGA** | 221 | `.svs` | ~30-50 GB | Open Access |
| **GTEx** | 191 | `.tiff` | ~15-25 GB | dbGaP (requires approval) |
| **PANDA** | 197 | `.tiff` | ~20-30 GB | Kaggle Competition |
| **Total** | **609** | - | **~65-105 GB** | Mixed |

## Directory Structure

WSIs should be placed under a `wsi_root` directory with the following structure:

```
data/
├── multipathqa/
│   └── MultiPathQA.csv          # Benchmark metadata (already here)
└── wsi/                          # WSI files (you must populate this)
    ├── tcga/                     # TCGA cancer diagnosis slides
    │   ├── TCGA-*.svs
    │   └── ...
    ├── gtex/                     # GTEx organ classification slides
    │   ├── GTEX-*.tiff
    │   └── ...
    └── panda/                    # PANDA prostate grading slides
        ├── *.tiff
        └── ...
```

The evaluation runner accepts `--wsi-root data/wsi` and resolves each `image_path` from the CSV to the appropriate subdirectory.

## Acquisition Instructions

### TCGA (The Cancer Genome Atlas)

**Source:** NIH Genomic Data Commons (GDC)
**Access:** Open access (no approval required)
**Tool:** GDC Data Transfer Tool

1. **Install GDC Client:**
   ```bash
   # macOS
   brew install gdc-client

   # Or download from: https://gdc.cancer.gov/access-data/gdc-data-transfer-tool
   ```

2. **Create a manifest file** listing the specific slide UUIDs needed (cross-reference with MultiPathQA.csv)

3. **Download:**
   ```bash
   gdc-client download -m manifest.txt -d data/wsi/tcga/
   ```

**Alternative (Faster for subset):**
- Use the GDC Portal web interface: https://portal.gdc.cancer.gov/
- Filter: Data Type = "Slide Image", Data Format = "SVS"
- Add to cart and download

**Direct links for specific files:**
Each TCGA slide has a UUID. Example download:
```bash
# Single file example (replace UUID)
gdc-client download <uuid> -d data/wsi/tcga/
```

### GTEx (Genotype-Tissue Expression)

**Source:** GTEx Portal
**Access:** Requires dbGaP approval for some data
**URL:** https://www.gtexportal.org/

1. **Request Access:**
   - Some GTEx histology images require dbGaP authorization
   - Apply at: https://dbgap.ncbi.nlm.nih.gov/

2. **Download via GTEx Portal:**
   - Navigate to: https://www.gtexportal.org/home/histologyPage
   - Filter by tissue type
   - Download individual slides or bulk

3. **Alternative - AWS Open Data:**
   ```bash
   # GTEx data is available on AWS Open Data
   aws s3 sync s3://gtex-resources/histology/ data/wsi/gtex/ --no-sign-request
   ```

### PANDA (Prostate Cancer Grade Assessment)

**Source:** Kaggle Competition (2020)
**Access:** Requires Kaggle account and competition rules acceptance
**URL:** https://www.kaggle.com/c/prostate-cancer-grade-assessment

1. **Accept Competition Rules:**
   - Visit the competition page
   - Click "Late Submission" or "Join Competition"
   - Accept the rules

2. **Install Kaggle CLI:**
   ```bash
   pip install kaggle
   # Configure: ~/.kaggle/kaggle.json with your API key
   ```

3. **Download:**
   ```bash
   kaggle competitions download -c prostate-cancer-grade-assessment -p data/wsi/panda/
   unzip data/wsi/panda/prostate-cancer-grade-assessment.zip -d data/wsi/panda/
   ```

## Verification

After downloading, verify your setup:

```bash
# Check file counts
find data/wsi/tcga -name "*.svs" | wc -l    # Should be ~221
find data/wsi/gtex -name "*.tiff" | wc -l   # Should be ~191
find data/wsi/panda -name "*.tiff" | wc -l  # Should be ~197

# Validate against MultiPathQA.csv
python -c "
import pandas as pd
from pathlib import Path

csv = pd.read_csv('data/multipathqa/MultiPathQA.csv')
wsi_root = Path('data/wsi')

missing = []
for _, row in csv.iterrows():
    benchmark = row['benchmark_name']
    image_path = row['image_path']

    # Try both direct and subdirectory paths
    paths_to_try = [
        wsi_root / image_path,
        wsi_root / benchmark / image_path,
    ]

    if not any(p.exists() for p in paths_to_try):
        missing.append(f'{benchmark}/{image_path}')

print(f'Missing: {len(missing)} / {len(csv)} WSIs')
if missing[:5]:
    print('Examples:', missing[:5])
"
```

## Quick Start (Minimal Testing)

For development and CI, you can use a single test WSI:

```bash
# Download OpenSlide test data (~10MB)
mkdir -p tests/integration/wsi/data
curl -L -o tests/integration/wsi/data/CMU-1-Small-Region.svs \
    https://openslide.cs.cmu.edu/download/openslide-testdata/Aperio/CMU-1-Small-Region.svs

# Run integration tests
WSI_TEST_FILE=tests/integration/wsi/data/CMU-1-Small-Region.svs \
    uv run pytest tests/integration/wsi/ -v
```

## Estimated Download Times

| Dataset | Size | Time (100 Mbps) | Time (1 Gbps) |
|---------|------|-----------------|---------------|
| TCGA | ~40 GB | ~1 hour | ~5 min |
| GTEx | ~20 GB | ~30 min | ~3 min |
| PANDA | ~25 GB | ~35 min | ~4 min |
| **Total** | **~85 GB** | **~2 hours** | **~12 min** |

## Storage Requirements

| Component | Size |
|-----------|------|
| WSI files | ~85-100 GB |
| Working space (crops, trajectories) | ~10-20 GB |
| **Total recommended** | **~150 GB free** |

## Troubleshooting

### "WSI file not found" errors

1. Check the file exists: `ls data/wsi/tcga/<filename>.svs`
2. Check file extension case: `.SVS` vs `.svs`
3. Verify the directory structure matches expected layout

### OpenSlide errors

```bash
# Verify OpenSlide can read your files
python -c "
import openslide
slide = openslide.OpenSlide('data/wsi/tcga/some_file.svs')
print(f'Dimensions: {slide.dimensions}')
print(f'Levels: {slide.level_count}')
"
```

### Disk space issues

WSIs are large. Check available space:
```bash
df -h data/
```

## References

- [GIANT Paper](https://arxiv.org/abs/2511.19652)
- [MultiPathQA on HuggingFace](https://huggingface.co/datasets/tbuckley/MultiPathQA)
- [GDC Data Portal](https://portal.gdc.cancer.gov/)
- [GTEx Portal](https://www.gtexportal.org/)
- [PANDA Challenge](https://www.kaggle.com/c/prostate-cancer-grade-assessment)
- [OpenSlide Test Data](https://openslide.cs.cmu.edu/download/openslide-testdata/)
