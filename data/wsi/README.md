# WSI Data Directory

This directory contains the Whole-Slide Image (WSI) files required for running the MultiPathQA benchmark.

**This directory is gitignored** - WSI files are too large (~95-135 GB total) to commit to version control.

## MultiPathQA Benchmark Summary

| Benchmark | Questions | Unique WSIs | Files | Format |
|-----------|-----------|-------------|-------|--------|
| `tcga` | 221 | 221 | In tcga/ | `.svs` |
| `tcga_expert_vqa` | 128 | 76 | In tcga/ | `.svs` |
| `tcga_slidebench` | 197 | 183 | In tcga/ | `.svs` |
| `gtex` | 191 | 191 | In gtex/ | `.tiff` |
| `panda` | 197 | 197 | In panda/ | `.tiff` |
| **Total** | **934** | **862** | - | - |

**Note:** All 3 TCGA benchmarks share the same directory. Total unique TCGA files: **474**.

## Directory Structure

```
data/wsi/
├── README.md           # This file
├── tcga_files.txt      # List of 474 TCGA filenames needed
├── gtex_files.txt      # List of 191 GTEx filenames needed
├── panda_files.txt     # List of 197 PANDA filenames needed
├── tcga/               # TCGA slides (all 3 benchmarks)
│   └── *.svs           # 474 files, ~60-80 GB
├── gtex/               # GTEx Organ Classification slides
│   └── *.tiff          # 191 files, ~15-25 GB
└── panda/              # PANDA Prostate Grading slides
    └── *.tiff          # 197 files, ~20-30 GB
```

## File Lists

We provide exact file lists for each source:

- `tcga_files.txt` - 474 TCGA slide filenames
- `gtex_files.txt` - 191 GTEx slide filenames
- `panda_files.txt` - 197 PANDA slide filenames

Use these to verify downloads or create download manifests.

## How to Populate

See the full acquisition guide: **[docs/DATA_ACQUISITION.md](../../docs/DATA_ACQUISITION.md)**

### Quick Reference

| Dataset | Source | Command |
|---------|--------|---------|
| TCGA | GDC Portal | `gdc-client download -m manifest.txt -d data/wsi/tcga/` |
| GTEx | GTEx Portal / AWS | `aws s3 sync s3://gtex-resources/histology/ data/wsi/gtex/` |
| PANDA | Kaggle | `kaggle competitions download -c prostate-cancer-grade-assessment` |

## Verification

After downloading, verify your files:

```bash
# Count files
find tcga -name "*.svs" 2>/dev/null | wc -l    # Should be 474
find gtex -name "*.tiff" 2>/dev/null | wc -l   # Should be 191
find panda -name "*.tiff" 2>/dev/null | wc -l  # Should be 197

# Check against file lists
for f in $(cat tcga_files.txt | grep -v '^#'); do
    [ -f "tcga/$f" ] || echo "Missing: tcga/$f"
done
```

## Usage

Once populated, run the benchmark:

```bash
# Run GIANT on a single benchmark
giant eval --benchmark tcga --wsi-root data/wsi

# Run on all 5 benchmarks
giant eval --benchmark all --wsi-root data/wsi

# Run with specific sample size for testing
giant eval --benchmark gtex --wsi-root data/wsi --sample-size 10
```
