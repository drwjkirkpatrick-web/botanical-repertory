# Botanical Repertory — Project Manifest

**Location**: `~/.hermes/projects/botanical_repertory/`
**Git**: Initialized (`master` branch, commit `9328c5e`)

## What's In Here

A local-first botanical medicine repertory with vector search. Query by symptom/indication and get ranked botanical suggestions with safety data.

## Current State

| Component | Status |
|-----------|--------|
| SQLite database | 116 botanicals, 249 indications, 541 edges |
| Vector index | 384-dim float16, built |
| WHO Monographs | Vol 1-4 fully ingested |
| EMA HMPC parser | Built and tested, awaiting more PDFs |
| CLI | `search`, `repertorize`, `stats` working |

## Key Files

| File | Purpose |
|------|---------|
| `cli.py` | Entry point — run `python cli.py --help` |
| `src/database.py` | All SQLite operations |
| `src/repertory.py` | `repertorize()` and `search()` APIs |
| `src/models.py` | Dataclasses: Botanical, Indication, etc. |
| `search/vector_index.py` | Build/query vector index |
| `scripts/parse_who_monographs.py` | One-time WHO bulk ingest |
| `scripts/parse_ema_monographs.py` | Per-PDF EMA ingest |
| `data/botanical.sqlite` | Main database (gitignored) |
| `data/botanical_vector_index.npz` | Vector index (gitignored) |

## How to Use

```bash
cd ~/.hermes/projects/botanical_repertory

# Check stats
python cli.py stats

# Search
python cli.py search "cough and bronchitis"

# Repertorize multiple symptoms
python cli.py repertorize "anxiety, insomnia"
```

## Adding EMA Monographs Later

```bash
python scripts/parse_ema_monographs.py /path/to/ema_monograph.pdf data/botanical.sqlite
```

Then rebuild the vector index if you want new indications searchable by vector similarity.

## Data Sources

- **WHO Monographs on Selected Medicinal Plants** Vol 1-4 (public domain, from WHO IRIS)
- **EMA HMPC European Union Herbal Monographs** (public, from ema.europa.eu)

## Notes

- The EMA parser uses `pdfplumber` to handle two-column table layouts
- Vector embeddings use `sentence-transformers/all-MiniLM-L6-v2`
- All data stays local — no API calls after initial setup
