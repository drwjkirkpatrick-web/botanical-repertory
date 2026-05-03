"""
Data ingestion pipeline for Botanical Medicine Repertory

Modules:
- document_parser: File parsing (MD, TXT, PDF)
- heuristics_v1: Extraction patterns
- pipeline: Orchestration and batch processing
"""

__all__ = [
    "DocumentParser",
    "MarkdownParser", 
    "TextParser",
    "IngestionPipeline",
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name in ["DocumentParser", "MarkdownParser", "TextParser"]:
        from .document_parser import DocumentParser, MarkdownParser, TextParser
        return locals()[name]
    elif name == "IngestionPipeline":
        from .pipeline import IngestionPipeline
        return IngestionPipeline
    raise AttributeError(f"module 'ingestion' has no attribute '{name}'")
