#!/usr/bin/env python3
"""
Command-line interface for Botanical Medicine Repertory.

Usage:
    python cli.py [command] [options]

Commands:
    init              Initialize database
    ingest            Ingest data from documents
    index             Build search indexes
    search            Search indications
    repertorize       Repertorize symptoms
    export            Export results
    stats             Show database statistics
    test              Run test suite
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def cmd_init(args):
    """Initialize database."""
    from src.database import BotanicalDatabase
    
    db = BotanicalDatabase()
    db.initialize_schema()
    print("✅ Database initialized successfully")
    
    stats = db.get_stats()
    print(f"\nTables created:")
    for table, count in stats.items():
        print(f"  {table}: {count} rows")


def cmd_ingest(args):
    """Ingest data."""
    from ingestion.pipeline import IngestionPipeline
    
    pipeline = IngestionPipeline()
    
    if args.source == "documents":
        if not args.path:
            print("❌ Error: --path required for document ingestion")
            return 1
        print(f"⏳ Ingesting from {args.path}...")
        stats = pipeline.ingest_from_documents(args.path)
    else:
        print(f"❌ Unknown source: {args.source}")
        return 1
    
    print(f"\n✅ Ingestion complete!")
    print(f"   Duration: {stats.duration_seconds:.1f}s")
    print(f"   Records processed: {stats.records_processed}")
    print(f"   Botanicals added: {stats.botanicals_added}")
    print(f"   Indications added: {stats.indications_added}")
    print(f"   Edges added: {stats.edges_added}")
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(stats.to_dict(), f, indent=2)
        print(f"\n   Stats saved to {args.output}")
    
    return 0


def cmd_index(args):
    """Build search indexes."""
    if args.type in ["lexical", "all"]:
        print("⏳ Building lexical index...")
        from search.lexical_search import LexicalSearcher
        from src.database import BotanicalDatabase
        
        db = BotanicalDatabase()
        searcher = LexicalSearcher(db)
        result = searcher.build_index()
        print(f"✅ Lexical index: {result['indexed']} indications, {result['terms']} terms")
    
    if args.type in ["vector", "all"]:
        print("⏳ Building vector index...")
        from search.vector_index import VectorIndexBuilder
        
        builder = VectorIndexBuilder()
        result = builder.build(dim=args.dim, dtype=args.dtype)
        
        if result["built"]:
            print(f"✅ Vector index: {result['count']} vectors, {result['size_mb']:.1f} MB")
        else:
            print(f"⚠️  Vector index failed: {result.get('error', 'Unknown error')}")
    
    return 0


def cmd_search(args):
    """Search indications."""
    from src.repertory import BotanicalRepertory
    
    rep = BotanicalRepertory()
    
    results = rep.search_indications(
        args.query,
        mode=args.mode,
        limit=args.limit
    )
    
    print(f"\nSearch results for: '{args.query}'")
    print(f"Mode: {args.mode}")
    print("-" * 60)
    
    if not results:
        print("No results found.")
        return 0
    
    for i, r in enumerate(results, 1):
        cat = f" [{r.item.category}]" if r.item.category else ""
        print(f"{i}. [{r.score:.3f}] {r.item.indication_text}{cat}")
        if r.matched_text and r.matched_text != r.item.indication_text:
            print(f"   Matched: {r.matched_text}")
    
    return 0


def cmd_repertorize(args):
    """Repertorize symptoms."""
    from src.repertory import BotanicalRepertory
    
    rep = BotanicalRepertory()
    
    results = rep.repertorize(
        symptoms=args.symptoms,
        top_n=args.top,
        mode=args.mode,
        rubrics_per_symptom=args.rubrics,
        include_safety=not args.no_safety
    )
    
    if not results:
        print("No results found. Database may be empty.")
        return 0
    
    print(rep.format_repertorization_results(results, include_matches=args.verbose))
    
    if args.export:
        filepath = args.export
        if filepath.endswith('.json'):
            rep.export_repertorization_to_json(results, filepath)
        elif filepath.endswith('.csv'):
            rep.export_repertorization_to_csv(results, filepath)
        elif filepath.endswith('.md'):
            rep.export_repertorization_to_markdown(results, filepath, args.symptoms)
        else:
            print(f"❌ Unknown export format: {filepath}")
            return 1
        print(f"\n✅ Exported to {filepath}")
    
    return 0


def cmd_export(args):
    """Export database contents."""
    from src.database import BotanicalDatabase
    import csv
    
    db = BotanicalDatabase()
    
    if args.format == "json":
        # Export botanicals
        with db.connection() as conn:
            rows = conn.execute("SELECT * FROM botanicals").fetchall()
            data = [dict(row) for row in rows]
        
        with open(args.output, 'w') as f:
            json.dump(data, f, indent=2)
    
    elif args.format == "csv":
        with db.connection() as conn:
            rows = conn.execute("SELECT * FROM botanicals").fetchall()
        
        with open(args.output, 'w', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows([dict(row) for row in rows])
    
    print(f"✅ Exported to {args.output}")
    return 0


def cmd_stats(args):
    """Show database statistics."""
    from src.database import BotanicalDatabase
    from src.repertory import BotanicalRepertory
    
    db = BotanicalDatabase()
    rep = BotanicalRepertory()
    
    print("\n" + "=" * 50)
    print("DATABASE STATISTICS")
    print("=" * 50)
    
    stats = db.get_stats()
    for table, count in stats.items():
        print(f"  {table:30s}: {count:6d}")
    
    # Categories
    print("\n" + "-" * 50)
    print("INDICATION CATEGORIES")
    print("-" * 50)
    
    categories = rep.get_categories()
    for cat in categories[:20]:  # Limit output
        print(f"  {cat}")
    
    # Evidence levels
    print("\n" + "-" * 50)
    print("EVIDENCE LEVELS")
    print("-" * 50)
    
    evidence_levels = rep.get_evidence_levels()
    for level in evidence_levels:
        print(f"  {level}")
    
    print("\n" + "=" * 50)
    
    return 0


def cmd_test(args):
    """Run test suite."""
    import subprocess
    
    test_args = ["-v"]
    
    if args.unit:
        test_args.extend(["-m", "not integration"])
    elif args.integration:
        test_args.extend(["-m", "integration"])
    
    if args.coverage:
        test_args.extend(["--cov=src", "--cov=search", "--cov=ingestion"])
    
    test_args.append("tests/")
    
    result = subprocess.run(["python", "-m", "pytest"] + test_args)
    return result.returncode


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Botanical Medicine Repertory CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init
  %(prog)s ingest documents --path docs/
  %(prog)s index --type all
  %(prog)s search "anxiety" --mode hybrid
  %(prog)s repertorize anxiety insomnia --top 10 --export results.json
  %(prog)s stats
  %(prog)s test --unit
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    
    # ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest data')
    ingest_parser.add_argument('source', choices=['documents'],
                              help='Data source')
    ingest_parser.add_argument('--path', help='Path for document ingestion')
    ingest_parser.add_argument('-o', '--output', help='Save stats to file')
    
    # index command
    index_parser = subparsers.add_parser('index', help='Build search indexes')
    index_parser.add_argument('--type', choices=['lexical', 'vector', 'all'],
                             default='all', help='Index type')
    index_parser.add_argument('--dim', type=int, default=384,
                             help='Vector dimension')
    index_parser.add_argument('--dtype', default='float16',
                             help='Vector dtype')
    
    # search command
    search_parser = subparsers.add_parser('search', help='Search indications')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--mode', choices=['lexical', 'vector', 'hybrid'],
                              default='hybrid', help='Search mode')
    search_parser.add_argument('--limit', type=int, default=10,
                              help='Max results')
    
    # repertorize command
    rep_parser = subparsers.add_parser('repertorize',
                                      help='Repertorize symptoms')
    rep_parser.add_argument('symptoms', nargs='+', help='Symptoms to analyze')
    rep_parser.add_argument('--top', type=int, default=10,
                           help='Number of results')
    rep_parser.add_argument('--mode', choices=['lexical', 'vector', 'hybrid'],
                           default='hybrid', help='Search mode')
    rep_parser.add_argument('--rubrics', type=int, default=10,
                           help='Indications per symptom')
    rep_parser.add_argument('--no-safety', action='store_true',
                           help='Skip safety profiles')
    rep_parser.add_argument('--verbose', '-v', action='store_true',
                           help='Show match details')
    rep_parser.add_argument('--export', help='Export results to file')
    
    # export command
    export_parser = subparsers.add_parser('export', help='Export data')
    export_parser.add_argument('--format', choices=['json', 'csv'],
                              required=True, help='Export format')
    export_parser.add_argument('-o', '--output', required=True,
                              help='Output file')
    
    # stats command
    subparsers.add_parser('stats', help='Show statistics')
    
    # test command
    test_parser = subparsers.add_parser('test', help='Run tests')
    test_parser.add_argument('--unit', action='store_true',
                            help='Run only unit tests')
    test_parser.add_argument('--integration', action='store_true',
                            help='Run only integration tests')
    test_parser.add_argument('--coverage', action='store_true',
                            help='Generate coverage report')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Dispatch to command handler
    commands = {
        'init': cmd_init,
        'ingest': cmd_ingest,
        'index': cmd_index,
        'search': cmd_search,
        'repertorize': cmd_repertorize,
        'export': cmd_export,
        'stats': cmd_stats,
        'test': cmd_test,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"❌ Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
