"""
Ingestion Pipeline for Botanical Medicine Repertory

Orchestrates data flow from local documents (Markdown, TXT):
- Batch processing with transaction safety
- Extensible parser framework for additional monograph sources

Usage:
    from ingestion.pipeline import IngestionPipeline
    
    pipeline = IngestionPipeline()
    
    # Ingest from documents
    stats = pipeline.ingest_from_documents("docs/")
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from src.database import BotanicalDatabase
from src.models import (
    Botanical, Indication, BotanicalIndicationLink,
    Contraindication, Document, Chunk
)

# Import ingestion modules
from .document_parser import DocumentParser
from .heuristics_v1 import (
    LatinBinomialExtractor,
    IndicationExtractor,
    EvidenceLevelDetector,
    SafetySignalDetector,
    TextChunker
)


logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Statistics from an ingestion run."""
    source: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    records_processed: int = 0
    botanicals_added: int = 0
    indications_added: int = 0
    edges_added: int = 0
    contraindications_added: int = 0
    documents_added: int = 0
    chunks_added: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration of ingestion."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source': self.source,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'records_processed': self.records_processed,
            'botanicals_added': self.botanicals_added,
            'indications_added': self.indications_added,
            'edges_added': self.edges_added,
            'contraindications_added': self.contraindications_added,
            'documents_added': self.documents_added,
            'chunks_added': self.chunks_added,
            'errors': self.errors,
        }


class IngestionPipeline:
    """
    Main ingestion pipeline coordinating multiple data sources.
    """
    
    def __init__(self, db_path: str = "data/botanical.sqlite"):
        """
        Initialize pipeline.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db = BotanicalDatabase(db_path)
        self.doc_parser = DocumentParser()
        
        # Heuristics
        self.binomial_extractor = LatinBinomialExtractor()
        self.indication_extractor = IndicationExtractor()
        self.evidence_detector = EvidenceLevelDetector()
        self.safety_detector = SafetySignalDetector()
        self.chunker = TextChunker(chunk_size=500, overlap=100)
        
        # Load config
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load project configuration."""
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def initialize_database(self) -> bool:
        """Initialize database schema if not exists."""
        schema_path = Path(__file__).parent.parent / "config" / "schema.sql"
        self.db.initialize_schema(str(schema_path))
        logger.info("Database initialized")
        return True
    
    # ========================================================================
    # DOCUMENT INGESTION
    # ========================================================================
    
    def ingest_from_documents(
        self,
        directory: str,
        extensions: Optional[List[str]] = None
    ) -> IngestionStats:
        """
        Ingest botanical data from local documents.
        
        Args:
            directory: Directory containing documents
            extensions: File extensions to process (default: .md, .txt)
        
        Returns:
            IngestionStats with results
        """
        stats = IngestionStats(source=f"documents:{directory}")
        
        try:
            doc_path = Path(directory)
            if not doc_path.exists():
                raise FileNotFoundError(f"Directory not found: {directory}")
            
            if extensions is None:
                extensions = ['.md', '.txt']
            
            # Find all matching files
            files = []
            for ext in extensions:
                files.extend(doc_path.glob(f"*{ext}"))
            
            logger.info(f"Found {len(files)} documents to process")
            stats.records_processed = len(files)
            
            for filepath in files:
                try:
                    doc_stats = self._process_document(filepath)
                    stats.documents_added += doc_stats['documents']
                    stats.chunks_added += doc_stats['chunks']
                    stats.botanicals_added += doc_stats['botanicals']
                    stats.indications_added += doc_stats['indications']
                    stats.edges_added += doc_stats['edges']
                except Exception as e:
                    error_msg = f"Failed to process {filepath}: {str(e)}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)
            
            logger.info("Document ingestion complete")
            
        except Exception as e:
            error_msg = f"Document ingestion failed: {str(e)}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
        
        finally:
            stats.end_time = datetime.now()
            self._update_meta_after_ingestion(stats)
        
        return stats
    
    def _process_document(self, filepath: Path) -> Dict[str, int]:
        """Process a single document."""
        stats = {'documents': 0, 'chunks': 0, 'botanicals': 0, 'indications': 0, 'edges': 0}
        
        # Parse document
        parsed = self.doc_parser.parse(filepath)
        
        with self.db.transaction() as conn:
            # Insert document record
            doc = Document(
                filename=parsed.filename,
                filepath=str(filepath),
                content=parsed.raw_text,
                source='file_import',
                doc_type=parsed.doc_type
            )
            
            # Store document in database
            cursor = conn.execute(
                """INSERT INTO docs (filename, filepath, content, source, doc_type, processed)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (doc.filename, doc.filepath, doc.content, doc.source, doc.doc_type)
            )
            doc_id = cursor.lastrowid
            stats['documents'] = 1
            
            # Chunk and store
            chunks = self.chunker.chunk_text(parsed.raw_text)
            for chunk_data in chunks:
                cursor = conn.execute(
                    """INSERT INTO chunks (doc_id, chunk_text, start_pos, end_pos, chunk_index)
                       VALUES (?, ?, ?, ?, ?)""",
                    (doc_id, chunk_data['text'], chunk_data['start'],
                     chunk_data['end'], chunk_data['index'])
                )
                stats['chunks'] += 1
            
            # Process extracted botanicals
            for bot_data in parsed.botanicals:
                botanical = Botanical(
                    latin_binomial=bot_data['latin_binomial'],
                    genus=bot_data['genus'],
                    species=bot_data['species']
                )
                botanical_id = self.db.insert_botanical(botanical)
                if botanical_id:
                    stats['botanicals'] += 1
                
                # Process indications for this botanical
                for ind_data in parsed.indications:
                    indication = Indication(
                        indication_text=ind_data['text'],
                        normalized_text=ind_data['text'],  # Already normalized by parser
                        category=ind_data.get('category')
                    )
                    indication_id = self.db.insert_indication(indication)
                    if indication_id:
                        stats['indications'] += 1
                    
                    # Create edge
                    edge = BotanicalIndicationLink(
                        indication_id=indication_id,
                        botanical_id=botanical_id,
                        weight=1.0,
                        evidence_level='traditional',
                        source_ref=str(filepath)
                    )
                    self.db.insert_edge(edge)
                    stats['edges'] += 1
        
        return stats
    
    # ========================================================================
    # METADATA & UTILITIES
    # ========================================================================
    
    def _update_meta_after_ingestion(self, stats: IngestionStats):
        """Update database metadata after ingestion."""
        self.db.update_meta('last_ingestion', stats.end_time.isoformat() if stats.end_time else '')
        self.db.update_meta('last_ingestion_source', stats.source)
        
        # Update counts
        db_stats = self.db.get_stats()
        self.db.update_meta('total_botanicals', str(db_stats.get('botanicals', 0)))
        self.db.update_meta('total_indications', str(db_stats.get('indications', 0)))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current database statistics."""
        return self.db.get_stats()


def main():
    """CLI for running ingestion pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Botanical ingestion pipeline")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--docs", metavar="DIR", help="Ingest from documents directory")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    parser.add_argument("--output", "-o", help="Save stats to JSON file")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    pipeline = IngestionPipeline()
    
    if args.init:
        pipeline.initialize_database()
        print("✅ Database initialized")
    
    elif args.docs:
        print(f"\n⏳ Ingesting from {args.docs}...")
        stats = pipeline.ingest_from_documents(args.docs)
        print(f"\n✅ Ingestion complete!")
        print(f"   Documents processed: {stats.records_processed}")
        print(f"   Documents added: {stats.documents_added}")
        print(f"   Chunks added: {stats.chunks_added}")
        print(f"   Botanicals added: {stats.botanicals_added}")
    
    elif args.stats:
        stats = pipeline.get_stats()
        print("\n=== Database Statistics ===")
        for table, count in stats.items():
            print(f"  {table}: {count}")
        print()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
