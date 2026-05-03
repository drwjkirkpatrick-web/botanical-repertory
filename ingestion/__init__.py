"""
Data ingestion pipeline for Botanical Medicine Repertory

Modules:
- airtable_fetch: Airtable API integration
- document_parser: File parsing (MD, TXT, PDF)
- heuristics_v1: Extraction patterns
- pipeline: Orchestration and batch processing
"""

__all__ = [
    "AirtableClient",
    "DocumentParser",
    "MarkdownParser", 
    "TextParser",
    "IngestionPipeline",
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "AirtableClient":
        from .airtable_fetch import AirtableClient
        return AirtableClient
    elif name in ["DocumentParser", "MarkdownParser", "TextParser"]:
        from .document_parser import DocumentParser, MarkdownParser, TextParser
        return locals()[name]
    elif name == "IngestionPipeline":
        from .pipeline import IngestionPipeline
        return IngestionPipeline
    raise AttributeError(f"module 'ingestion' has no attribute '{name}'")