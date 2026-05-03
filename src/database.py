"""
Database management for Botanical Medicine Repertory
"""

import sqlite3
import json
import os
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path
from contextlib import contextmanager

from .models import (
    Botanical, Indication, BotanicalIndicationLink,
    Contraindication, DrugInteraction, SafetyProfile,
    Document, Chunk
)


class BotanicalDatabase:
    """Manages SQLite database connections and operations."""
    
    def __init__(self, db_path: str = "data/botanical.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = {}
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def initialize_schema(self, schema_file: str = "config/schema.sql") -> bool:
        """Initialize database schema from SQL file."""
        schema_path = Path(schema_file)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        with self.transaction() as conn:
            conn.executescript(schema_sql)
        
        return True
    
    # =========================================================================
    # BOTANICAL OPERATIONS
    # =========================================================================
    
    def insert_botanical(self, botanical: Botanical) -> int:
        """Insert a botanical and return its ID."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO botanicals 
                (latin_binomial, common_names, family, genus, species, 
                 parts_used, energetics, traditional_systems)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                botanical.latin_binomial,
                json.dumps(botanical.common_names),
                botanical.family,
                botanical.genus,
                botanical.species,
                json.dumps(botanical.parts_used),
                json.dumps(botanical.energetics),
                json.dumps(botanical.traditional_systems)
            ))
            
            if cursor.lastrowid:
                return cursor.lastrowid
            
            # Return existing ID if already present
            row = conn.execute(
                "SELECT id FROM botanicals WHERE latin_binomial = ?",
                (botanical.latin_binomial,)
            ).fetchone()
            return row["id"]
    
    def get_botanical_by_id(self, botanical_id: int) -> Optional[Botanical]:
        """Retrieve a botanical by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM botanicals WHERE id = ?",
                (botanical_id,)
            ).fetchone()
            
            if row:
                return self._row_to_botanical(row)
            return None
    
    def get_botanical_by_binomial(self, latin_binomial: str) -> Optional[Botanical]:
        """Retrieve a botanical by Latin binomial."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM botanicals WHERE latin_binomial = ?",
                (latin_binomial,)
            ).fetchone()
            
            if row:
                return self._row_to_botanical(row)
            return None
    
    def search_botanicals(self, query: str, limit: int = 20) -> List[Botanical]:
        """Search botanicals by name (Latin or common)."""
        pattern = f"%{query}%"
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT * FROM botanicals 
                WHERE latin_binomial LIKE ? 
                   OR common_names LIKE ?
                LIMIT ?
            """, (pattern, pattern, limit)).fetchall()
            
            return [self._row_to_botanical(row) for row in rows]
    
    @staticmethod
    def _json_or_list(val: Optional[str]) -> list:
        if not val:
            return []
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [str(parsed)]
        except json.JSONDecodeError:
            return [val]
    
    @staticmethod
    def _json_or_dict(val: Optional[str]) -> dict:
        if not val:
            return {}
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    
    def _row_to_botanical(self, row: sqlite3.Row) -> Botanical:
        """Convert a database row to Botanical object."""
        return Botanical(
            id=row["id"],
            latin_binomial=row["latin_binomial"],
            common_names=self._json_or_list(row["common_names"]),
            family=row["family"] or "",
            genus=row["genus"] or "",
            species=row["species"] or "",
            parts_used=self._json_or_list(row["parts_used"]),
            energetics=self._json_or_dict(row["energetics"]),
            traditional_systems=self._json_or_list(row["traditional_systems"]),
        )
    
    # =========================================================================
    # INDICATION OPERATIONS
    # =========================================================================
    
    def insert_indication(self, indication: Indication) -> int:
        """Insert an indication and return its ID."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO indications 
                (indication_text, normalized_text, category, subcategory, body_system)
                VALUES (?, ?, ?, ?, ?)
            """, (
                indication.indication_text,
                indication.normalized_text,
                indication.category,
                indication.subcategory,
                indication.body_system
            ))
            
            if cursor.lastrowid:
                return cursor.lastrowid
            
            row = conn.execute(
                "SELECT id FROM indications WHERE normalized_text = ?",
                (indication.normalized_text,)
            ).fetchone()
            return row["id"]
    
    def get_indication_by_id(self, indication_id: int) -> Optional[Indication]:
        """Retrieve an indication by ID."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM indications WHERE id = ?",
                (indication_id,)
            ).fetchone()
            
            if row:
                return self._row_to_indication(row)
            return None
    
    def search_indications_fts(self, query: str, limit: int = 50) -> List[Indication]:
        """Search indications using full-text search."""
        with self.connection() as conn:
            # Use FTS5 for fast text search
            rows = conn.execute("""
                SELECT i.* FROM indications i
                JOIN indications_fts fts ON i.id = fts.rowid
                WHERE indications_fts MATCH ?
                LIMIT ?
            """, (query, limit)).fetchall()
            
            return [self._row_to_indication(row) for row in rows]
    
    def get_indications_by_category(self, category: str, limit: int = 100) -> List[Indication]:
        """Get all indications in a category."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM indications WHERE category = ? LIMIT ?",
                (category, limit)
            ).fetchall()
            
            return [self._row_to_indication(row) for row in rows]
    
    def _row_to_indication(self, row: sqlite3.Row) -> Indication:
        """Convert a database row to Indication object."""
        return Indication(
            id=row["id"],
            indication_text=row["indication_text"],
            normalized_text=row["normalized_text"],
            category=row["category"],
            subcategory=row["subcategory"],
            body_system=row["body_system"],
        )
    
    # =========================================================================
    # EDGE/LINK OPERATIONS
    # =========================================================================
    
    def insert_edge(self, edge: BotanicalIndicationLink) -> int:
        """Insert a botanical-indication link."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO indication_botanical_edges 
                (indication_id, botanical_id, weight, evidence_level, 
                 source_ref, preparation, dosage_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                edge.indication_id,
                edge.botanical_id,
                edge.weight,
                edge.evidence_level,
                edge.source_ref,
                edge.preparation,
                edge.dosage_notes
            ))
            return cursor.lastrowid
    
    def get_edges_by_indication(self, indication_id: int) -> List[BotanicalIndicationLink]:
        """Get all botanicals linked to an indication."""
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT e.*, b.* FROM indication_botanical_edges e
                JOIN botanicals b ON e.botanical_id = b.id
                WHERE e.indication_id = ?
                ORDER BY e.weight DESC
            """, (indication_id,)).fetchall()
            
            return [self._row_to_edge(row, conn) for row in rows]
    
    def get_edges_by_botanical(self, botanical_id: int) -> List[BotanicalIndicationLink]:
        """Get all indications linked to a botanical."""
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT e.*, i.* FROM indication_botanical_edges e
                JOIN indications i ON e.indication_id = i.id
                WHERE e.botanical_id = ?
                ORDER BY e.weight DESC
            """, (botanical_id,)).fetchall()
            
            return [self._row_to_edge(row, conn) for row in rows]
    
    def _row_to_edge(self, row: sqlite3.Row, conn: sqlite3.Connection) -> BotanicalIndicationLink:
        """Convert a joined row to BotanicalIndicationLink."""
        # Determine which tables are in the row
        has_botanical = "latin_binomial" in row.keys()
        has_indication = "indication_text" in row.keys()
        
        # sqlite3.Row supports __getitem__ but not .get()
        edge = BotanicalIndicationLink(
            id=row["id"],
            indication_id=row["indication_id"],
            botanical_id=row["botanical_id"],
            weight=row["weight"],
            evidence_level=row["evidence_level"],
            source_ref=row["source_ref"] or "",
            preparation=row["preparation"] or "",
            dosage_notes=row["dosage_notes"] or "",
        )
        
        if has_botanical:
            edge.botanical = self._row_to_botanical(row)
        if has_indication:
            edge.indication = self._row_to_indication(row)
        
        return edge
    
    # =========================================================================
    # SAFETY OPERATIONS
    # =========================================================================
    
    def insert_contraindication(self, contra: Contraindication) -> int:
        """Insert a contraindication."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO contraindications 
                (botanical_id, contraindication, severity, population, mechanism, source_ref)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                contra.botanical_id,
                contra.contraindication,
                contra.severity,
                contra.population,
                contra.mechanism,
                contra.source_ref
            ))
            return cursor.lastrowid
    
    def insert_drug_interaction(self, interaction: DrugInteraction) -> int:
        """Insert a drug interaction."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO drug_interactions 
                (botanical_id, drug_class, specific_drugs, interaction_severity, mechanism, recommendation)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                interaction.botanical_id,
                interaction.drug_class,
                json.dumps(interaction.specific_drugs),
                interaction.interaction_severity,
                interaction.mechanism,
                interaction.recommendation
            ))
            return cursor.lastrowid
    
    def get_safety_profile(self, botanical_id: int) -> SafetyProfile:
        """Get complete safety profile for a botanical."""
        with self.connection() as conn:
            botanical = self.get_botanical_by_id(botanical_id)
            
            # Get contraindications
            contra_rows = conn.execute(
                "SELECT * FROM contraindications WHERE botanical_id = ?",
                (botanical_id,)
            ).fetchall()
            contras = [
                Contraindication(
                    id=row["id"],
                    botanical_id=row["botanical_id"],
                    contraindication=row["contraindication"],
                    severity=row["severity"],
                    population=row["population"],
                    mechanism=row["mechanism"] or "",
                    source_ref=row["source_ref"] or "",
                )
                for row in contra_rows
            ]
            
            # Get drug interactions
            interact_rows = conn.execute(
                "SELECT * FROM drug_interactions WHERE botanical_id = ?",
                (botanical_id,)
            ).fetchall()
            interactions = [
                DrugInteraction(
                    id=row["id"],
                    botanical_id=row["botanical_id"],
                    drug_class=row["drug_class"] or "",
                    specific_drugs=self._json_or_list(row["specific_drugs"]),
                    interaction_severity=row["interaction_severity"],
                    mechanism=row["mechanism"] or "",
                    recommendation=row["recommendation"] or "",
                )
                for row in interact_rows
            ]
            
            return SafetyProfile(
                botanical=botanical,
                contraindications=contras,
                drug_interactions=interactions
            )
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        with self.connection() as conn:
            stats = {}
            tables = [
                "botanicals", "indications", "indication_botanical_edges",
                "contraindications", "drug_interactions", "docs", "chunks"
            ]
            for table in tables:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                stats[table] = row[0]
            return stats
    
    def update_meta(self, key: str, value: str):
        """Update a metadata value."""
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO meta (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value))
    
    def get_meta(self, key: str) -> Optional[str]:
        """Get a metadata value."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else None