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
| **TCGA** | 474 | `.svs` | **~472 GiB total** (GDC API sum of `file_size`) | Open Access |
| **GTEx** | 191 | `.tiff` | Varies (see notes below) | GTEx Portal (terms vary) |
| **PANDA** | 197 | `.tiff` | Varies; Kaggle packaging is large | Kaggle Competition |
| **Total** | **862** | - | **≥ ~472 GiB** (TCGA alone) | Mixed |

**Reality check:** the earlier “~95–135 GB total” estimate was wrong by an order of magnitude. TCGA alone is ~472 GiB for the 474 slides referenced by MultiPathQA.

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
**Tool:** GDC Data Transfer Tool (recommended) or direct download via GDC API

1. **Install GDC Client:**
   ```bash
   # macOS
   brew install gdc-client

   # Or download from: https://gdc.cancer.gov/access-data/gdc-data-transfer-tool
   ```

2. **Create a manifest file** from the GDC Portal:
   - Go to https://portal.gdc.cancer.gov/
   - Filter: Data Type = "Slide Image", Data Format = "SVS"
   - Use the file list in `data/wsi/tcga_files.txt` to find specific slides
   - Add to cart and export manifest

3. **Download:**
   ```bash
   gdc-client download -m manifest.txt -d data/wsi/tcga/
   ```

**Important:** MultiPathQA includes a `file_id` column for TCGA rows (the GDC UUID). Also note that GDC’s downloaded `file_name` is UUID-suffixed (e.g. `TCGA-...-DX1.<uuid>.svs`), and `gdc-client` typically stores files under `data/wsi/tcga/<file_id>/<file_name>`.

The evaluation runner supports this default `gdc-client` layout (no manual renaming required), as long as you keep the `file_id` column in `MultiPathQA.csv`.

**Helper (recommended for planning / smoke data):**

```bash
# Estimate TCGA total size (uses GDC API, no download)
uv run python -m giant.data.tcga estimate

# Download the N smallest TCGA slides into data/wsi/tcga/<file_id>/<file_name>
uv run python -m giant.data.tcga download --smallest 5
```

### GTEx (Genotype-Tissue Expression)

**Source:** GTEx Portal
**Access:** Terms vary; verify your access/terms before bulk download
**Files Needed:** 191 `.tiff` files (see `data/wsi/gtex_files.txt`)
**URL:** https://www.gtexportal.org/

1. **Download via GTEx Portal:**
   - Navigate to: https://www.gtexportal.org/home/histologyPage
   - Filter by tissue type
   - Download individual slides or bulk

**Note:** The previously documented `s3://gtex-resources/histology/` bucket does not exist (NoSuchBucket). If you have a correct bulk-download source (AWS/GCP/etc), add it here once verified.

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

After downloading, verify your setup using the built-in checker:

```bash
# Check each dataset
uv run giant check-data tcga
uv run giant check-data gtex
uv run giant check-data panda

# For verbose output showing missing files
uv run giant check-data tcga -v
```

The `check-data` command:
- Validates against `MultiPathQA.csv`
- Handles both flat and `gdc-client` directory layouts
- Reports found/missing counts


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

For validation without downloading all hundreds of GiB, you can start with a subset:

```bash
# Download first 5 files from each source for Spec-11.5 validation
# See the file lists in data/wsi/*.txt
```

Recommended subset sizes:
- **Minimal:** 1–5 per source (expect multiple GiB depending on slide sizes)
- **Basic:** 10–20 per source
- **Full:** All 862 (hundreds of GiB; TCGA alone is ~472 GiB)

## Storage Requirements

| Component | Size |
|-----------|------|
| TCGA WSIs (474) | ~472 GiB |
| GTEx WSIs (191) | Varies |
| PANDA WSIs (197) | Varies |
| Working space (crops, trajectories) | ~10–50+ GiB (depends on run size) |
| **Total recommended** | **Plan for many hundreds of GiB free** |

## Estimated Download Times

Download time varies widely by source and mirror. As a rough rule of thumb:

`time ≈ size / bandwidth`

Example: TCGA is ~472 GiB. At 100 Mbps sustained, that’s on the order of ~10–11 hours (ignoring overhead/retries).

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
