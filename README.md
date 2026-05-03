# Botanical Medicine Repertory

A local, vector-searchable botanical medicine database for clinical and educational use. Inspired by homeopathic repertory systems, adapted for botanical materia medica.

## Overview

Maps **indications → botanical remedies** (Latin binomials) with evidence levels, safety profiles, and contraindications. Runs entirely offline after initial setup.

### Key Features

- **Local SQLite database** — No cloud dependency, full data ownership
- **Vector + Lexical hybrid search** — Feature-hashing + random projection vectors plus BM25-style lexical matching
- **Evidence-weighted scoring** — Clinical trials weighted higher than traditional use
- **Safety integration** — Contraindications and drug interactions built-in
- **Extensible source system** — Parser framework for ingesting monograph collections

## Current Data Status

| Source | Botanicals | Indications | Edges | Status |
|--------|-----------|-------------|-------|--------|
| WHO Monographs Vol 1-4 | 116 | 249 | 541 | ✅ Ingested |

## Project Structure

```
botanical_repertory/
├── cli.py                      # Command-line interface
├── config/
│   ├── config.json             # Project configuration
│   └── schema.sql              # SQLite database schema
├── data/                       # SQLite DB and vector indexes (gitignored)
├── docs/
│   ├── sample_chamomile.md     # Sample botanical monograph
│   └── who_monographs/         # WHO source text extracts
├── ingestion/                  # Data import pipeline
│   ├── pipeline.py
│   ├── document_parser.py
│   └── heuristics_v1.py
├── scripts/                    # One-off ingestion scripts
│   ├── create_sample_data.py   # Generate test data
│   └── parse_who_monographs.py # WHO Vol 1-4 → SQLite
├── search/                     # Search implementations
│   ├── hybrid_search.py
│   ├── lexical_search.py
│   └── vector_index.py
├── src/                        # Core library
│   ├── models.py               # Data classes
│   ├── database.py             # SQLite operations
│   └── repertory.py            # Repertory API
├── tests/                      # Test suite
│   ├── test_database.py
│   ├── test_search.py
│   └── test_integration.py
└── README.md
```

## Quick Start

### 1. Check Database Stats

```bash
python cli.py stats
```

### 2. Search Indications

```bash
# Hybrid search (vector + lexical)
python cli.py search "cough and bronchitis"

# Repertorize multiple symptoms
python cli.py repertorize "anxiety, insomnia"
```

### 3. Ingest WHO Monographs

```bash
python scripts/parse_who_monographs.py data/botanical.sqlite
```

### 4. Rebuild Vector Index (after adding new indications)

```python
from search.vector_index import VectorIndexBuilder
builder = VectorIndexBuilder()
builder.build_from_indications(dim=384)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python cli.py stats` | Show database statistics |
| `python cli.py search "query"` | Search indications |
| `python cli.py repertorize "symptom1, symptom2"` | Multi-symptom repertorization |
| `python cli.py botanical "Latin Name"` | Look up botanical details |

## Evidence Levels

| Level | Multiplier | Description |
|-------|------------|-------------|
| systematic_review | 3.0 | Meta-analyses, systematic reviews |
| clinical_trial | 2.5 | RCTs, controlled studies |
| clinical_observation | 2.0 | Practitioner case series |
| traditional | 1.0 | Traditional/herbal medicine systems |
| in_vitro | 0.8 | Laboratory/mechanistic studies |
| ethnobotanical | 0.7 | Traditional use documentation |
| theoretical | 0.5 | Theoretical/phytochemical rationale |

## Safety Features

- **Contraindications** — Population-specific (pregnancy, children, etc.)
- **Drug interactions** — Class and specific drug warnings
- **Severity levels** — mild, moderate, severe, absolute
- **Mechanism notes** — Brief explanation of interaction/contraindication

## Data Sources

- **WHO Monographs on Selected Medicinal Plants** Vol 1-4 (public domain, from WHO IRIS)

The ingestion pipeline is designed to be extensible. Additional monograph sources can be added by implementing a parser module following the `DocumentParser` interface in `ingestion/document_parser.py`.

## Technical Details

- **Backend**: SQLite 3 with FTS5 full-text search
- **Vector index**: NumPy float16, 384-dim (feature hashing + random projection — no ML model downloads)
- **Search**: Hybrid lexical (BM25-like) + cosine similarity
- **Index size**: ~0.2 MB for 249 indications

## Development

Run tests:
```bash
python -m pytest tests/
```

## License

GPL v3

## Clinical Disclaimer

This tool is for **educational and decision-support purposes only**. All botanical recommendations must be verified by a qualified healthcare practitioner. The system does not replace clinical judgment, proper diagnosis, or individualized patient assessment.
