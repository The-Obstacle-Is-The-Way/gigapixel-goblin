# WSI Data Directory

This directory contains the Whole-Slide Image (WSI) files required for running the MultiPathQA benchmark.

**This directory is gitignored** - WSI files are too large (~85-100 GB total) to commit to version control.

## Directory Structure

```
data/wsi/
├── README.md           # This file
├── tcga/               # TCGA Cancer Diagnosis slides (.svs)
│   └── *.svs           # ~221 files, ~30-50 GB
├── gtex/               # GTEx Organ Classification slides (.tiff)
│   └── *.tiff          # ~191 files, ~15-25 GB
└── panda/              # PANDA Prostate Grading slides (.tiff)
    └── *.tiff          # ~197 files, ~20-30 GB
```

## How to Populate

See the full acquisition guide: **[docs/DATA_ACQUISITION.md](../../docs/DATA_ACQUISITION.md)**

### Quick Reference

| Dataset | Source | Command |
|---------|--------|---------|
| TCGA | GDC Portal | `gdc-client download -m manifest.txt -d data/wsi/tcga/` |
| GTEx | GTEx Portal / AWS | `aws s3 sync s3://gtex-resources/histology/ data/wsi/gtex/` |
| PANDA | Kaggle | `kaggle competitions download -c prostate-cancer-grade-assessment` |

## Verification

After downloading, verify your files match what MultiPathQA.csv expects:

```bash
# Count files
find tcga -name "*.svs" | wc -l    # Should be ~221
find gtex -name "*.tiff" | wc -l   # Should be ~191
find panda -name "*.tiff" | wc -l  # Should be ~197

# Run validation script
python -m giant.eval.validate_wsi_root --wsi-root data/wsi
```

## Usage

Once populated, run the benchmark:

```bash
# Run GIANT on MultiPathQA benchmark
giant eval --benchmark tcga --wsi-root data/wsi

# Or specify all benchmarks
giant eval --benchmark all --wsi-root data/wsi
```
