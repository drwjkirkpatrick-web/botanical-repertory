# Botanical Repertory — Project Manifest

**Repository:** [github.com/drwjkirkpatrick-web/botanical-repertory](https://github.com/drwjkirkpatrick-web/botanical-repertory)
**Git:** `main` branch

## What's In Here

A local-first botanical medicine repertory with vector search. Query by indication and get ranked botanical suggestions with safety data.

## Current State

| Component | Status |
|-----------|--------|
| SQLite database | 116 botanicals, 249 indications, 541 edges |
| Vector index | 384-dim float16, built |
| WHO Monographs | Vol 1-4 fully ingested |
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
| `scripts/create_sample_data.py` | Generate sample dataset for testing |
| `data/botanical.sqlite` | Main database (gitignored) |
| `data/botanical_vector_index.npz` | Vector index (gitignored) |

## How to Use

```bash
cd /path/to/botanical-repertory

# Check stats
python cli.py stats

# Search
python cli.py search "cough and bronchitis"

# Repertorize multiple indications
python cli.py repertorize "anxiety, insomnia"
```

## Data Sources

- **WHO Monographs on Selected Medicinal Plants** Vol 1-4 (public domain, from WHO IRIS)

The ingestion framework in `ingestion/` is designed to be extensible for additional monograph sources.

## Notes

- Vector embeddings use feature hashing + random projection (no ML model downloads required)
- All data stays local — no API calls after initial setup
