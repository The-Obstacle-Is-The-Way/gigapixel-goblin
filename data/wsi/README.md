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

See the full acquisition guide: **[docs/DATA_ACQUISITION.md](../../docs/DATA_ACQUISITION.md)**

### Quick Reference

| Dataset | Source | Command |
|---------|--------|---------|
| TCGA | GDC Portal | `gdc-client download -m manifest.txt -d data/wsi/tcga/` |
| GTEx | GTEx Portal | Download from https://www.gtexportal.org/home/histologyPage |
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

Spec-12 will add a stable CLI. Until then, use the Python entry points documented in:

- `docs/specs/spec-10-evaluation.md`
- `docs/specs/spec-11.5-e2e-validation-checkpoint.md`
