"""
Ingestion Pipeline for Botanical Medicine Repertory

Orchestrates data flow from multiple sources:
- Airtable API
- Local documents (Markdown, TXT)
- Batch processing with transaction safety

Usage:
    from ingestion.pipeline import IngestionPipeline
    
    pipeline = IngestionPipeline()
    
    # Ingest from Airtable
    stats = pipeline.ingest_from_airtable()
    
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
from .airtable_fetch import AirtableClient
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
    # AIRTABLE INGESTION
    # ========================================================================
    
    def ingest_from_airtable(
        self,
        max_records: Optional[int] = None,
        batch_size: int = 100
    ) -> IngestionStats:
        """
        Ingest botanical records from Airtable.
        
        Args:
            max_records: Maximum records to fetch (None = all)
            batch_size: Number of records to process per transaction batch
        
        Returns:
            IngestionStats with results
        """
        stats = IngestionStats(source="airtable")
        
        try:
            # Connect to Airtable
            client = AirtableClient()
            
            # First, inspect schema to see available fields
            logger.info("Inspecting Airtable schema...")
            fields = client.inspect_fields()
            field_names = [f['name'] for f in fields]
            logger.info(f"Found fields: {field_names}")
            
            # Fetch records
            logger.info(f"Fetching records (max: {max_records or 'unlimited'})...")
            records = client.fetch_all_records(max_records=max_records)
            
            logger.info(f"Fetched {len(records)} records")
            stats.records_processed = len(records)
            
            # Process in batches
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(records)-1)//batch_size + 1}")
                
                try:
                    batch_stats = self._process_airtable_batch(batch)
                    stats.botanicals_added += batch_stats['botanicals']
                    stats.indications_added += batch_stats['indications']
                    stats.edges_added += batch_stats['edges']
                    stats.contraindications_added += batch_stats['contraindications']
                except Exception as e:
                    error_msg = f"Batch {i//batch_size} failed: {str(e)}"
                    logger.error(error_msg)
                    stats.errors.append(error_msg)
            
            logger.info("Airtable ingestion complete")
            
        except Exception as e:
            error_msg = f"Airtable ingestion failed: {str(e)}"
            logger.error(error_msg)
            stats.errors.append(error_msg)
        
        finally:
            stats.end_time = datetime.now()
            self._update_meta_after_ingestion(stats)
        
        return stats
    
    def _process_airtable_batch(self, records: List[Dict]) -> Dict[str, int]:
        """Process a batch of Airtable records."""
        stats = {'botanicals': 0, 'indications': 0, 'edges': 0, 'contraindications': 0}
        
        with self.db.transaction() as conn:
            for record in records:
                fields = record.get('fields', {})
                
                # Extract botanical
                botanical = self._extract_botanical_from_airtable(fields)
                if not botanical:
                    continue
                
                botanical_id = self.db.insert_botanical(botanical)
                if botanical_id:
                    stats['botanicals'] += 1
                
                # Extract indications
                indications = self._extract_indications_from_airtable(fields)
                for ind_data in indications:
                    indication = Indication(
                        indication_text=ind_data['text'],
                        normalized_text=ind_data['normalized'],
                        category=ind_data.get('category'),
                    )
                    indication_id = self.db.insert_indication(indication)
                    
                    if indication_id:
                        stats['indications'] += 1
                    
                    # Create edge
                    edge = BotanicalIndicationLink(
                        indication_id=indication_id,
                        botanical_id=botanical_id,
                        weight=ind_data.get('weight', 1.0),
                        evidence_level=ind_data.get('evidence_level', 'traditional'),
                        source_ref='Airtable'
                    )
                    self.db.insert_edge(edge)
                    stats['edges'] += 1
                
                # Extract contraindications
                contras = self._extract_contraindications_from_airtable(fields)
                for contra_data in contras:
                    contra = Contraindication(
                        botanical_id=botanical_id,
                        contraindication=contra_data['description'],
                        severity=contra_data.get('severity', 'moderate'),
                        population=contra_data.get('population', 'all')
                    )
                    self.db.insert_contraindication(contra)
                    stats['contraindications'] += 1
        
        return stats
    
    def _extract_botanical_from_airtable(self, fields: Dict) -> Optional[Botanical]:
        """Extract botanical data from Airtable fields."""
        # Try common field names for Latin binomial
        latin_field = None
        for field_name in ['Latin Binomial', 'Scientific Name', 'Latin Name', 'Binomial']:
            if field_name in fields:
                latin_field = fields[field_name]
                break
        
        if not latin_field:
            return None
        
        # Parse binomial
        parts = latin_field.split()
        if len(parts) < 2:
            return None
        
        # Get common names (might be list or string)
        common_names = []
        for field_name in ['Common Names', 'Common Name', 'Vernacular Names']:
            if field_name in fields:
                value = fields[field_name]
                if isinstance(value, list):
                    common_names = value
                elif isinstance(value, str):
                    common_names = [n.strip() for n in value.split(',')]
                break
        
        # Get family
        family = fields.get('Family', '')
        
        # Get parts used
        parts_used = []
        for field_name in ['Parts Used', 'Plant Part', 'Part Used']:
            if field_name in fields:
                value = fields[field_name]
                if isinstance(value, list):
                    parts_used = value
                elif isinstance(value, str):
                    parts_used = [p.strip() for p in value.split(',')]
                break
        
        return Botanical(
            latin_binomial=latin_field,
            common_names=common_names,
            family=family,
            genus=parts[0],
            species=parts[1] if len(parts) > 1 else '',
            parts_used=parts_used
        )
    
    def _extract_indications_from_airtable(self, fields: Dict) -> List[Dict]:
        """Extract indications from Airtable fields."""
        indications = []
        
        # Try common field names
        for field_name in ['Indications', 'Uses', 'Actions', 'Therapeutic Uses']:
            if field_name not in fields:
                continue
            
            value = fields[field_name]
            items = []
            
            if isinstance(value, list):
                items = value
            elif isinstance(value, str):
                # Split on newlines or semicolons
                items = [i.strip() for i in re.split(r'[\n;]', value) if i.strip()]
            
            for item in items:
                normalized = self.indication_extractor.normalize(item)
                category = self.indication_extractor.categorize(normalized)
                
                # Detect evidence level
                evidence = 'traditional'
                for field_name_ev in ['Evidence', 'Evidence Level', 'Research']:
                    if field_name_ev in fields:
                        evidence_text = str(fields[field_name_ev])
                        detected, _ = self.evidence_detector.detect(evidence_text)
                        evidence = detected
                        break
                
                indications.append({
                    'text': item,
                    'normalized': normalized,
                    'category': category,
                    'evidence_level': evidence,
                    'weight': 1.0
                })
        
        return indications
    
    def _extract_contraindications_from_airtable(self, fields: Dict) -> List[Dict]:
        """Extract contraindications from Airtable fields."""
        contras = []
        
        for field_name in ['Contraindications', 'Precautions', 'Safety', 'Warnings']:
            if field_name not in fields:
                continue
            
            value = fields[field_name]
            items = []
            
            if isinstance(value, list):
                items = value
            elif isinstance(value, str):
                items = [i.strip() for i in re.split(r'[\n;]', value) if i.strip()]
            
            for item in items:
                severity = self.safety_detector._detect_severity(item)
                
                # Detect population
                population = 'all'
                if 'pregnancy' in item.lower() or 'pregnant' in item.lower():
                    population = 'pregnancy'
                elif 'child' in item.lower() or 'pediatric' in item.lower():
                    population = 'children'
                
                contras.append({
                    'description': item,
                    'severity': severity,
                    'population': population
                })
        
        return contras
    
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
    
    def inspect_airtable_schema(self) -> List[Dict]:
        """Inspect Airtable schema without ingesting."""
        client = AirtableClient()
        return client.inspect_fields()


def main():
    """CLI for running ingestion pipeline."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Botanical ingestion pipeline")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--airtable", action="store_true", help="Ingest from Airtable")
    parser.add_argument("--docs", metavar="DIR", help="Ingest from documents directory")
    parser.add_argument("--max-records", type=int, help="Max Airtable records")
    parser.add_argument("--inspect", action="store_true", help="Inspect Airtable schema")
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
    
    elif args.inspect:
        print("\n=== Airtable Schema ===")
        fields = pipeline.inspect_airtable_schema()
        for f in fields:
            print(f"  {f['name']} ({f['type']})")
        print()
    
    elif args.airtable:
        print("\n⏳ Ingesting from Airtable...")
        stats = pipeline.ingest_from_airtable(max_records=args.max_records)
        print(f"\n✅ Ingestion complete!")
        print(f"   Duration: {stats.duration_seconds:.1f}s")
        print(f"   Records processed: {stats.records_processed}")
        print(f"   Botanicals added: {stats.botanicals_added}")
        print(f"   Indications added: {stats.indications_added}")
        print(f"   Edges added: {stats.edges_added}")
        if stats.errors:
            print(f"   ⚠️  Errors: {len(stats.errors)}")
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(stats.to_dict(), f, indent=2)
            print(f"\n   Stats saved to {args.output}")
    
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
