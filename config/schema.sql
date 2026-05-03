-- Botanical Medicine Repertory Database Schema
-- SQLite with Full-Text Search support

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Botanicals: The remedies (herbs, plants) in the repertory
CREATE TABLE IF NOT EXISTS botanicals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    latin_binomial TEXT UNIQUE NOT NULL,
    common_names TEXT,  -- JSON array of common names
    family TEXT,
    genus TEXT,
    species TEXT,
    parts_used TEXT,  -- JSON array
    energetics TEXT,  -- JSON object: temperature, moisture, tone
    traditional_systems TEXT,  -- JSON array: TCM, Ayurveda, Western, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indications: Symptoms, conditions, or uses (like rubrics in homeopathy)
CREATE TABLE IF NOT EXISTS indications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indication_text TEXT NOT NULL,
    normalized_text TEXT UNIQUE NOT NULL,
    category TEXT,  -- e.g., 'pain', 'digestive', 'mood', 'skin', 'respiratory'
    subcategory TEXT,
    body_system TEXT,  -- e.g., 'nervous', 'cardiovascular', 'immune'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Links between indications and botanicals (the core repertory data)
CREATE TABLE IF NOT EXISTS indication_botanical_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indication_id INTEGER NOT NULL,
    botanical_id INTEGER NOT NULL,
    weight REAL DEFAULT 1.0,  -- Base strength of association
    evidence_level TEXT DEFAULT 'traditional',  -- See config.evidence_levels
    source_ref TEXT,  -- Citation, study reference, traditional text
    preparation TEXT,  -- e.g., 'tincture', 'tea', 'capsule', 'essential oil'
    dosage_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (indication_id) REFERENCES indications(id) ON DELETE CASCADE,
    FOREIGN KEY (botanical_id) REFERENCES botanicals(id) ON DELETE CASCADE,
    UNIQUE(indication_id, botanical_id, preparation)
);

-- ============================================================================
-- SAFETY TABLES
-- ============================================================================

-- Contraindications and safety information
CREATE TABLE IF NOT EXISTS contraindications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    botanical_id INTEGER NOT NULL,
    contraindication TEXT NOT NULL,
    severity TEXT DEFAULT 'moderate',  -- 'mild', 'moderate', 'severe', 'absolute'
    population TEXT,  -- e.g., 'pregnancy', 'children', 'elderly', 'all'
    mechanism TEXT,  -- Brief explanation of why
    source_ref TEXT,
    FOREIGN KEY (botanical_id) REFERENCES botanicals(id) ON DELETE CASCADE
);

-- Drug interactions
CREATE TABLE IF NOT EXISTS drug_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    botanical_id INTEGER NOT NULL,
    drug_class TEXT,  -- e.g., 'anticoagulants', 'SSRIs', 'sedatives'
    specific_drugs TEXT,  -- JSON array of specific drug names
    interaction_severity TEXT DEFAULT 'moderate',  -- 'mild', 'moderate', 'severe'
    mechanism TEXT,
    recommendation TEXT,  -- e.g., 'avoid', 'monitor', 'separate by 4 hours'
    FOREIGN KEY (botanical_id) REFERENCES botanicals(id) ON DELETE CASCADE
);

-- ============================================================================
-- DOCUMENT & CHUNK TABLES (for corpus-based extraction)
-- ============================================================================

-- Source documents (texts, PDFs, markdown files)
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT UNIQUE NOT NULL,
    filepath TEXT,
    content TEXT,
    source TEXT,  -- 'who_monograph', 'file_import', 'manual_entry'
    doc_type TEXT,  -- 'monograph', 'clinical_guide', 'research_paper', 'textbook'
    author TEXT,
    year INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT 0
);

-- Text chunks for vector indexing
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    start_pos INTEGER,
    end_pos INTEGER,
    chunk_index INTEGER,  -- Position within document
    has_indications BOOLEAN DEFAULT 0,
    FOREIGN KEY (doc_id) REFERENCES docs(id) ON DELETE CASCADE
);

-- Extracted indications from chunks (for training/validation)
CREATE TABLE IF NOT EXISTS chunk_indications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL,
    extracted_text TEXT NOT NULL,
    confidence REAL,
    matched_indication_id INTEGER,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE,
    FOREIGN KEY (matched_indication_id) REFERENCES indications(id)
);

-- ============================================================================
-- METADATA & INDEXING
-- ============================================================================

-- Search index metadata
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize metadata
INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1.0.0');
INSERT OR IGNORE INTO meta (key, value) VALUES ('last_ingestion', '');
INSERT OR IGNORE INTO meta (key, value) VALUES ('vector_index_built', 'false');
INSERT OR IGNORE INTO meta (key, value) VALUES ('total_botanicals', '0');
INSERT OR IGNORE INTO meta (key, value) VALUES ('total_indications', '0');

-- ============================================================================
-- INDICES FOR PERFORMANCE
-- ============================================================================

-- Search indices
CREATE INDEX IF NOT EXISTS idx_indications_category ON indications(category);
CREATE INDEX IF NOT EXISTS idx_indications_body_system ON indications(body_system);
CREATE INDEX IF NOT EXISTS idx_indications_normalized ON indications(normalized_text);

CREATE INDEX IF NOT EXISTS idx_edges_indication ON indication_botanical_edges(indication_id);
CREATE INDEX IF NOT EXISTS idx_edges_botanical ON indication_botanical_edges(botanical_id);
CREATE INDEX IF NOT EXISTS idx_edges_evidence ON indication_botanical_edges(evidence_level);

CREATE INDEX IF NOT EXISTS idx_botanicals_family ON botanicals(family);
CREATE INDEX IF NOT EXISTS idx_botanicals_genus ON botanicals(genus);

CREATE INDEX IF NOT EXISTS idx_contras_botanical ON contraindications(botanical_id);
CREATE INDEX IF NOT EXISTS idx_interactions_botanical ON drug_interactions(botanical_id);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_has_indications ON chunks(has_indications);

-- Full-text search virtual tables
CREATE VIRTUAL TABLE IF NOT EXISTS indications_fts USING fts5(
    indication_text,
    content='indications',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS botanicals_fts USING fts5(
    latin_binomial,
    common_names,
    content='botanicals',
    content_rowid='id'
);

-- Triggers to keep FTS indices in sync
CREATE TRIGGER IF NOT EXISTS indications_ai AFTER INSERT ON indications BEGIN
    INSERT INTO indications_fts(rowid, indication_text) VALUES (new.id, new.indication_text);
END;

CREATE TRIGGER IF NOT EXISTS indications_ad AFTER DELETE ON indications BEGIN
    INSERT INTO indications_fts(indications_fts, rowid, indication_text) VALUES ('delete', old.id, old.indication_text);
END;

CREATE TRIGGER IF NOT EXISTS indications_au AFTER UPDATE ON indications BEGIN
    INSERT INTO indications_fts(indications_fts, rowid, indication_text) VALUES ('delete', old.id, old.indication_text);
    INSERT INTO indications_fts(rowid, indication_text) VALUES (new.id, new.indication_text);
END;