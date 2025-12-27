# WSI Data Directory

This directory contains the Whole-Slide Image (WSI) files required for running the MultiPathQA benchmark.

**This directory is gitignored** - WSI files are too large to commit to version control.

**Reality check:** TCGA alone is ~472 GiB for the 474 slides referenced by MultiPathQA. Total storage across TCGA + GTEx + PANDA is many hundreds of GiB (plus working space for crops/trajectories).

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
│   └── ...             # TCGA slides are large (total ~472 GiB for MultiPathQA)
├── gtex/               # GTEx Organ Classification slides
│   └── *.tiff
└── panda/              # PANDA Prostate Grading slides
    └── *.tiff
```

## File Lists

We provide exact file lists for each source:

- `tcga_files.txt` - 474 TCGA slide filenames
- `gtex_files.txt` - 191 GTEx slide filenames
- `panda_files.txt` - 197 PANDA slide filenames

Use these to verify downloads or create download manifests.

## How to Populate

See the full acquisition guide: **[docs/data-acquisition.md](../../docs/data-acquisition.md)**

### Quick Reference

| Dataset | Source | Command |
|---------|--------|---------|
| TCGA | GDC Portal | `gdc-client download -m manifest.txt -d data/wsi/tcga/` |
| GTEx | GTEx Portal | Download from https://www.gtexportal.org/home/histologyPage |
| PANDA | Kaggle | `kaggle competitions download -c prostate-cancer-grade-assessment` |

## Verification

Use the built-in verification command:

```bash
uv run giant check-data tcga
uv run giant check-data tcga_expert_vqa
uv run giant check-data tcga_slidebench
uv run giant check-data gtex
uv run giant check-data panda
```

This command handles both flat and gdc-client directory layouts.

## Usage

Spec-12 added a stable CLI. Use the Python entry points documented in:

- `docs/specs/spec-10-evaluation.md`
- `docs/specs/spec-11.5-e2e-validation-checkpoint.md`
