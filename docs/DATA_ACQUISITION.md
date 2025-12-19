# Data Acquisition Guide

## Overview

GIANT evaluates against the **MultiPathQA** benchmark, which comprises **934 WSI-level questions** across **862 unique whole-slide images (WSIs)**. The benchmark metadata (questions, prompts, answers) is available on HuggingFace, but **the WSI files themselves must be acquired separately** from their original sources due to licensing and size constraints.

**This is a critical operational requirement.** Without the actual WSI files, you cannot:
- Run the GIANT agent on real pathology images
- Reproduce the paper's benchmark results
- Validate the end-to-end system

## MultiPathQA Benchmark Structure

The benchmark contains **5 distinct tasks** spanning 3 data sources:

| Benchmark | Questions | Unique WSIs | Task | Data Source | Metric |
|-----------|-----------|-------------|------|-------------|--------|
| `tcga` | 221 | 221 | Cancer Diagnosis (30-way) | TCGA | Balanced Accuracy |
| `tcga_expert_vqa` | 128 | 76 | Pathologist-Authored VQA | TCGA | Accuracy |
| `tcga_slidebench` | 197 | 183 | SlideBench VQA | TCGA | Accuracy |
| `gtex` | 191 | 191 | Organ Classification (20-way) | GTEx | Balanced Accuracy |
| `panda` | 197 | 197 | Prostate Grading (6-way) | PANDA | Balanced Accuracy |
| **Total** | **934** | **862** | - | - | - |

**Note:** The 3 TCGA benchmarks share some slides. Total unique TCGA files needed: **474** (not 221).

## Data Components

### 1. MultiPathQA Metadata (Already Available)

| File | Location | Size | Status |
|------|----------|------|--------|
| `MultiPathQA.csv` | `data/multipathqa/` | ~150KB | Included |

This CSV contains:
- `benchmark_name`: Task identifier (tcga, gtex, panda, tcga_expert_vqa, tcga_slidebench)
- `image_path`: Filename of the WSI (e.g., `GTEX-OIZH-0626.tiff`)
- `prompt`: Question to ask about the slide
- `answer`: Ground truth label
- `options`: Multiple choice options (when applicable)

### 2. Whole-Slide Images (Must Be Acquired)

| Source | Files Needed | Format | Size (Approx) | License |
|--------|--------------|--------|---------------|---------|
| **TCGA** | 474 | `.svs` | ~60-80 GB | Open Access |
| **GTEx** | 191 | `.tiff` | ~15-25 GB | dbGaP (requires approval) |
| **PANDA** | 197 | `.tiff` | ~20-30 GB | Kaggle Competition |
| **Total** | **862** | - | **~95-135 GB** | Mixed |

### 3. File Lists (Provided)

We have generated exact file lists from the MultiPathQA CSV:

| File | Contents |
|------|----------|
| `data/wsi/tcga_files.txt` | 474 TCGA slide filenames |
| `data/wsi/gtex_files.txt` | 191 GTEx slide filenames |
| `data/wsi/panda_files.txt` | 197 PANDA slide filenames |

Use these to verify downloads or create download manifests.

## Directory Structure

WSIs should be placed under a `wsi_root` directory with the following structure:

```
data/
├── multipathqa/
│   └── MultiPathQA.csv          # Benchmark metadata (already here)
└── wsi/                          # WSI files (you must populate this)
    ├── tcga_files.txt            # File list for TCGA
    ├── gtex_files.txt            # File list for GTEx
    ├── panda_files.txt           # File list for PANDA
    ├── tcga/                     # TCGA slides (all 3 benchmarks)
    │   ├── TCGA-02-0266-01Z-00-DX1.svs
    │   ├── TCGA-HT-A616-01Z-00-DX1.svs  # Used in expert_vqa
    │   ├── TCGA-HC-7080-01Z-00-DX1.svs  # Used in slidebench
    │   └── ... (474 total)
    ├── gtex/                     # GTEx organ classification slides
    │   ├── GTEX-OIZH-0626.tiff
    │   └── ... (191 total)
    └── panda/                    # PANDA prostate grading slides
        ├── dbf7cc49ae2e9831448c3ca54ad92708.tiff
        └── ... (197 total)
```

The evaluation runner accepts `--wsi-root data/wsi` and resolves each `image_path` from the CSV to the appropriate subdirectory based on `benchmark_name`.

## Acquisition Instructions

### TCGA (The Cancer Genome Atlas)

**Source:** NIH Genomic Data Commons (GDC)
**Access:** Open access (no approval required)
**Files Needed:** 474 `.svs` files (see `data/wsi/tcga_files.txt`)
**Tool:** GDC Data Transfer Tool

1. **Install GDC Client:**
   ```bash
   # macOS
   brew install gdc-client

   # Or download from: https://gdc.cancer.gov/access-data/gdc-data-transfer-tool
   ```

2. **Create a manifest file** from the GDC Portal:
   - Go to https://portal.gdc.cancer.gov/
   - Filter: Data Type = "Slide Image", Data Format = "SVS"
   - Use the file list in `data/wsi/tcga_files.txt` to find specific UUIDs
   - Add to cart and export manifest

3. **Download:**
   ```bash
   gdc-client download -m manifest.txt -d data/wsi/tcga/
   ```

**Note:** TCGA files are named like `TCGA-02-0266-01Z-00-DX1.svs`. The GDC stores them by UUID, so you may need to map filenames to UUIDs.

### GTEx (Genotype-Tissue Expression)

**Source:** GTEx Portal
**Access:** Requires dbGaP approval for some data
**Files Needed:** 191 `.tiff` files (see `data/wsi/gtex_files.txt`)
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
**Files Needed:** 197 `.tiff` files (see `data/wsi/panda_files.txt`)
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

   **Warning:** The full PANDA dataset is ~400GB. You only need 197 files for MultiPathQA. After unzipping, you can delete files not in `data/wsi/panda_files.txt`.

## Verification

After downloading, verify your setup:

```bash
# Check file counts
find data/wsi/tcga -name "*.svs" 2>/dev/null | wc -l    # Should be 474
find data/wsi/gtex -name "*.tiff" 2>/dev/null | wc -l   # Should be 191
find data/wsi/panda -name "*.tiff" 2>/dev/null | wc -l  # Should be 197

# Validate against MultiPathQA.csv
python -c "
import pandas as pd
from pathlib import Path

csv = pd.read_csv('data/multipathqa/MultiPathQA.csv')
wsi_root = Path('data/wsi')

# Map benchmark to subdirectory
benchmark_to_dir = {
    'tcga': 'tcga',
    'tcga_expert_vqa': 'tcga',
    'tcga_slidebench': 'tcga',
    'gtex': 'gtex',
    'panda': 'panda',
}

missing = []
found = 0
for _, row in csv.iterrows():
    benchmark = row['benchmark_name']
    image_path = row['image_path']
    subdir = benchmark_to_dir.get(benchmark, benchmark)

    full_path = wsi_root / subdir / image_path
    if full_path.exists():
        found += 1
    else:
        missing.append(f'{subdir}/{image_path}')

unique_missing = set(missing)
print(f'Found: {found} / {len(csv)} questions have WSIs')
print(f'Missing unique files: {len(unique_missing)}')
if unique_missing:
    print('First 5 missing:')
    for m in sorted(unique_missing)[:5]:
        print(f'  {m}')
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

## Subset Testing

For validation without downloading all ~100GB, you can start with a subset:

```bash
# Download first 5 files from each source for Spec-11.5 validation
# See the file lists in data/wsi/*.txt
```

Recommended subset sizes:
- **Minimal:** 5 per source (15 total, ~1-2 GB)
- **Basic:** 20 per source (60 total, ~5-10 GB)
- **Full:** All 862 (~95-135 GB)

## Storage Requirements

| Component | Size |
|-----------|------|
| WSI files | ~95-135 GB |
| Working space (crops, trajectories) | ~10-20 GB |
| **Total recommended** | **~150 GB free** |

## Estimated Download Times

| Dataset | Files | Size | Time (100 Mbps) | Time (1 Gbps) |
|---------|-------|------|-----------------|---------------|
| TCGA | 474 | ~70 GB | ~1.5 hours | ~10 min |
| GTEx | 191 | ~20 GB | ~30 min | ~3 min |
| PANDA | 197 | ~25 GB | ~35 min | ~4 min |
| **Total** | **862** | **~115 GB** | **~2.5 hours** | **~17 min** |

## Troubleshooting

### "WSI file not found" errors

1. Check the file exists: `ls data/wsi/tcga/<filename>.svs`
2. Check file extension case: `.SVS` vs `.svs`
3. Verify the directory structure matches expected layout
4. Ensure benchmark-to-directory mapping is correct (all TCGA benchmarks use `tcga/`)

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

### PANDA dataset too large

The full PANDA Kaggle download is ~400GB but we only need 197 files:
```bash
# After download, keep only needed files
cd data/wsi/panda
while read -r file; do
    if [ ! -f "$file" ]; then
        echo "Missing: $file"
    fi
done < ../panda_files.txt

# Delete extra files (be careful!)
# find . -name "*.tiff" | while read f; do
#     grep -q "$(basename $f)" ../panda_files.txt || rm "$f"
# done
```

## References

- [GIANT Paper](https://arxiv.org/abs/2511.19652)
- [MultiPathQA on HuggingFace](https://huggingface.co/datasets/tbuckley/MultiPathQA)
- [GDC Data Portal](https://portal.gdc.cancer.gov/)
- [GTEx Portal](https://www.gtexportal.org/)
- [PANDA Challenge](https://www.kaggle.com/c/prostate-cancer-grade-assessment)
- [OpenSlide Test Data](https://openslide.cs.cmu.edu/download/openslide-testdata/)
