"""
Core Botanical Repertory API

Main interface for searching indications, retrieving botanicals,
and performing multi-symptom repertorization.

Features:
- Lexical, vector, and hybrid search modes
- Result caching for repeated queries
- Batch repertorization
- Evidence-weighted scoring
- Safety profile integration
- Export functions (JSON, CSV)
"""

import json
import csv
import io
import hashlib
import time
from typing import List, Dict, Optional, Any, Union, Tuple
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .database import BotanicalDatabase
from .models import (
    Botanical, Indication, BotanicalIndicationLink,
    SafetyProfile, RepertorizationResult, SearchResult
)


class ResultCache:
    """
    Simple in-memory cache for search results.
    
    Uses query hash as key to avoid recomputing expensive searches.
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of cached entries
            ttl_seconds: Time-to-live for cache entries
        """
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict] = {}
        self._access_times: Dict[str, float] = {}
    
    def _make_key(self, *args, **kwargs) -> str:
        """Create a cache key from arguments."""
        key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, *args, **kwargs) -> Optional[Any]:
        """Get cached result if it exists and hasn't expired."""
        key = self._make_key(*args, **kwargs)
        
        if key in self._cache:
            # Check TTL
            age = time.time() - self._access_times[key]
            if age < self.ttl:
                self._access_times[key] = time.time()  # Update access time
                return self._cache[key]
            else:
                # Expired
                del self._cache[key]
                del self._access_times[key]
        
        return None
    
    def set(self, value: Any, *args, **kwargs):
        """Store result in cache."""
        key = self._make_key(*args, **kwargs)
        
        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest = min(self._access_times, key=self._access_times.get)
            del self._cache[oldest]
            del self._access_times[oldest]
        
        self._cache[key] = value
        self._access_times[key] = time.time()
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()
        self._access_times.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl
        }


class BotanicalRepertory:
    """
    Main repertory interface for botanical medicine.
    
    Supports:
    - Lexical search (token-based with BM25)
    - Vector search (semantic similarity via random projection)
    - Hybrid search (combined lexical + vector with RRF fusion)
    - Multi-symptom repertorization with evidence-weighted scoring
    - Result caching for performance
    - Batch operations
    - Export to various formats
    """
    
    def __init__(
        self,
        config_path: str = "config/config.json",
        enable_cache: bool = True
    ):
        """
        Initialize repertory with configuration.
        
        Args:
            config_path: Path to configuration JSON
            enable_cache: Whether to enable result caching
        """
        self.config = self._load_config(config_path)
        self.db = BotanicalDatabase(self.config["database"]["path"])
        
        # Caching
        self.cache = ResultCache() if enable_cache else None
        
        # Lazy-loaded search modules
        self._lexical_searcher = None
        self._vector_searcher = None
        self._hybrid_searcher = None
    
    def _load_config(self, path: str) -> Dict:
        """Load configuration from JSON file."""
        import json
        with open(path, 'r') as f:
            return json.load(f)
    
    @property
    def lexical_searcher(self):
        """Lazy-load lexical search module."""
        if self._lexical_searcher is None:
            from search.lexical_search import LexicalSearcher
            self._lexical_searcher = LexicalSearcher(
                self.db,
                scoring=self.config["search"].get("scoring", "bm25")
            )
        return self._lexical_searcher
    
    @property
    def vector_searcher(self):
        """Lazy-load vector search module."""
        if self._vector_searcher is None:
            from search.vector_index import VectorSearcher
            self._vector_searcher = VectorSearcher(
                index_path=self.config["vector_search"]["index_path"],
                meta_path=self.config["vector_search"]["meta_path"],
                db_path=self.config["database"]["path"]
            )
        return self._vector_searcher
    
    @property
    def hybrid_searcher(self):
        """Lazy-load hybrid search module."""
        if self._hybrid_searcher is None:
            from search.hybrid_search import HybridSearcher
            self._hybrid_searcher = HybridSearcher(
                self.lexical_searcher,
                self.vector_searcher,
                self.config["search"]
            )
        return self._hybrid_searcher
    
    # ========================================================================
    # BASIC QUERIES
    # ========================================================================
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        return self.db.get_stats()
    
    def get_cache_stats(self) -> Optional[Dict[str, int]]:
        """Get cache statistics if caching is enabled."""
        if self.cache:
            return self.cache.get_stats()
        return None
    
    def clear_cache(self):
        """Clear result cache."""
        if self.cache:
            self.cache.clear()
    
    def get_botanical_by_binomial(self, latin_binomial: str) -> Optional[Botanical]:
        """Get a botanical by its Latin binomial name."""
        return self.db.get_botanical_by_binomial(latin_binomial)
    
    def search_botanicals(self, query: str, limit: int = 20) -> List[Botanical]:
        """Search botanicals by Latin or common name."""
        return self.db.search_botanicals(query, limit)
    
    def get_safety_profile(self, latin_binomial: str) -> Optional[SafetyProfile]:
        """Get complete safety profile for a botanical."""
        botanical = self.get_botanical_by_binomial(latin_binomial)
        if not botanical:
            return None
        return self.db.get_safety_profile(botanical.id)
    
    # ========================================================================
    # INDICATION SEARCH (Multiple Modes)
    # ========================================================================
    
    def search_indications(
        self, 
        query: str, 
        mode: str = "hybrid",
        limit: int = 20,
        category: Optional[str] = None,
        use_cache: bool = True
    ) -> List[SearchResult]:
        """
        Search for indications by query text.
        
        Args:
            query: Search text (symptom description)
            mode: "lexical", "vector", or "hybrid"
            limit: Maximum results to return
            category: Filter by category (optional)
            use_cache: Whether to use result caching
        
        Returns:
            List of SearchResult objects
        """
        # Check cache
        if use_cache and self.cache:
            cached = self.cache.get("search_indications", query, mode, limit, category)
            if cached is not None:
                return cached
        
        # Perform search
        if mode == "lexical":
            results = self.lexical_searcher.search(query, limit, category)
        elif mode == "vector":
            results = self.vector_searcher.search(query, limit)
        elif mode == "hybrid":
            results = self.hybrid_searcher.search(query, limit, category)
        else:
            raise ValueError(f"Unknown search mode: {mode}")
        
        # Cache results
        if use_cache and self.cache:
            self.cache.set(results, "search_indications", query, mode, limit, category)
        
        return results
    
    def search_indications_batch(
        self,
        queries: List[str],
        mode: str = "hybrid",
        limit: int = 20
    ) -> List[List[SearchResult]]:
        """
        Search multiple queries efficiently (batch operation).
        
        Args:
            queries: List of query strings
            mode: Search mode
            limit: Results per query
        
        Returns:
            List of result lists (one per query)
        """
        return [self.search_indications(q, mode, limit) for q in queries]
    
    def get_botanicals_for_indication(
        self, 
        indication_id: int,
        min_evidence: Optional[str] = None
    ) -> List[BotanicalIndicationLink]:
        """
        Get all botanicals linked to an indication.
        
        Args:
            indication_id: The indication ID
            min_evidence: Minimum evidence level filter (optional)
        
        Returns:
            List of BotanicalIndicationLink objects
        """
        edges = self.db.get_edges_by_indication(indication_id)
        
        if min_evidence:
            evidence_priority = {
                "systematic_review": 6,
                "clinical_trial": 5,
                "clinical_observation": 4,
                "traditional": 3,
                "in_vitro": 2,
                "ethnobotanical": 1,
                "theoretical": 0,
            }
            min_priority = evidence_priority.get(min_evidence, 0)
            edges = [
                e for e in edges 
                if evidence_priority.get(e.evidence_level, 0) >= min_priority
            ]
        
        return edges
    
    def get_indication_suggestions(
        self,
        prefix: str,
        limit: int = 10
    ) -> List[str]:
        """
        Get autocomplete suggestions for indication search.
        
        Args:
            prefix: Query prefix
            limit: Maximum suggestions
        
        Returns:
            List of suggestion strings
        """
        return self.lexical_searcher.suggest_completions(prefix, limit)
    
    # ========================================================================
    # REPERTORIZATION (Core Feature)
    # ========================================================================
    
    def repertorize(
        self,
        symptoms: List[str],
        top_n: int = 20,
        mode: str = "hybrid",
        rubrics_per_symptom: int = 10,
        include_safety: bool = True,
        evidence_weight: bool = True,
        use_cache: bool = True
    ) -> List[RepertorizationResult]:
        """
        Multi-symptom repertorization: find botanicals matching multiple symptoms.
        
        Args:
            symptoms: List of symptom descriptions
            top_n: Number of top botanicals to return
            mode: Search mode ("lexical", "vector", "hybrid")
            rubrics_per_symptom: Maximum indications to consider per symptom
            include_safety: Whether to include safety profiles in results
            evidence_weight: Whether to weight by evidence level
            use_cache: Whether to use result caching
        
        Returns:
            List of RepertorizationResult objects, ranked by score
        """
        # Check cache
        cache_key = (tuple(sorted(symptoms)), top_n, mode, rubrics_per_symptom, include_safety, evidence_weight)
        if use_cache and self.cache:
            cached = self.cache.get("repertorize", cache_key)
            if cached is not None:
                return cached
        
        # Accumulate scores for each botanical
        botanical_data = defaultdict(lambda: {
            "botanical": None,
            "total_score": 0.0,
            "matches": [],
            "evidence_scores": defaultdict(float)
        })
        
        for symptom in symptoms:
            # Find matching indications
            search_results = self.search_indications(
                symptom, 
                mode=mode, 
                limit=rubrics_per_symptom,
                use_cache=use_cache
            )
            
            for result in search_results:
                indication = result.item
                if not isinstance(indication, Indication):
                    continue
                
                # Get botanicals for this indication
                links = self.db.get_edges_by_indication(indication.id)
                
                for link in links:
                    bid = link.botanical_id
                    
                    # Store botanical reference
                    if botanical_data[bid]["botanical"] is None:
                        botanical_data[bid]["botanical"] = link.botanical
                    
                    # Calculate score with evidence weighting
                    base_score = link.weight
                    
                    if evidence_weight:
                        # Apply evidence level multiplier
                        evidence_multiplier = self._get_evidence_multiplier(link.evidence_level)
                        score = base_score * evidence_multiplier
                    else:
                        score = base_score
                    
                    # Boost if high retrieval score
                    score *= (0.5 + 0.5 * result.score)  # Normalize and apply
                    
                    botanical_data[bid]["total_score"] += score
                    
                    # Track evidence levels
                    botanical_data[bid]["evidence_scores"][link.evidence_level] += score
                    
                    # Track match details
                    botanical_data[bid]["matches"].append({
                        "symptom": symptom,
                        "indication": indication.indication_text,
                        "indication_id": indication.id,
                        "evidence_level": link.evidence_level,
                        "weight": link.weight,
                        "score_contribution": score,
                        "preparation": link.preparation,
                        "retrieval_score": result.score,
                        "match_type": result.match_type
                    })
        
        # Convert to results and sort
        results = []
        for bid, data in botanical_data.items():
            if data["botanical"] is None:
                continue
            
            # Get safety profile if requested
            safety = None
            if include_safety:
                safety = self.db.get_safety_profile(bid)
            
            # Determine primary evidence level
            primary_evidence = max(
                data["evidence_scores"].items(),
                key=lambda x: x[1]
            )[0] if data["evidence_scores"] else "unknown"
            
            results.append(RepertorizationResult(
                botanical=data["botanical"],
                total_score=data["total_score"],
                matches=data["matches"],
                safety_profile=safety
            ))
        
        # Sort by total score descending
        results.sort(key=lambda x: x.total_score, reverse=True)
        
        # Assign ranks
        for i, result in enumerate(results[:top_n], 1):
            result.rank = i
        
        final_results = results[:top_n]
        
        # Cache results
        if use_cache and self.cache:
            self.cache.set(final_results, "repertorize", cache_key)
        
        return final_results
    
    def repertorize_batch(
        self,
        cases: List[Dict[str, Any]]
    ) -> List[List[RepertorizationResult]]:
        """
        Repertorize multiple cases in batch.
        
        Args:
            cases: List of case dicts with keys:
                - symptoms: List of symptom strings
                - top_n: Optional, defaults to 20
                - mode: Optional, defaults to "hybrid"
        
        Returns:
            List of repertorization results (one per case)
        """
        results = []
        for case in cases:
            result = self.repertorize(
                symptoms=case.get("symptoms", []),
                top_n=case.get("top_n", 20),
                mode=case.get("mode", "hybrid"),
                rubrics_per_symptom=case.get("rubrics_per_symptom", 10),
                include_safety=case.get("include_safety", True)
            )
            results.append(result)
        return results
    
    def _get_evidence_multiplier(self, evidence_level: str) -> float:
        """Get weight multiplier for evidence level."""
        multipliers = self.config.get("evidence_levels", {
            "systematic_review": 3.0,
            "clinical_trial": 2.5,
            "clinical_observation": 2.0,
            "traditional": 1.0,
            "in_vitro": 0.8,
            "ethnobotanical": 0.7,
            "theoretical": 0.5,
        })
        return multipliers.get(evidence_level, 1.0)
    
    # ========================================================================
    # EXPORT FUNCTIONS
    # ========================================================================
    
    def export_repertorization_to_json(
        self,
        results: List[RepertorizationResult],
        filepath: Optional[str] = None
    ) -> str:
        """
        Export repertorization results to JSON.
        
        Args:
            results: Repertorization results
            filepath: Optional file path to save to
        
        Returns:
            JSON string
        """
        data = {
            "export_date": datetime.now().isoformat(),
            "total_results": len(results),
            "results": [r.to_dict() for r in results]
        }
        
        json_str = json.dumps(data, indent=2)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(json_str)
        
        return json_str
    
    def export_repertorization_to_csv(
        self,
        results: List[RepertorizationResult],
        filepath: Optional[str] = None
    ) -> str:
        """
        Export repertorization results to CSV.
        
        Args:
            results: Repertorization results
            filepath: Optional file path to save to
        
        Returns:
            CSV string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Rank", "Latin Binomial", "Common Names", "Family",
            "Total Score", "Match Count", "Top Evidence Level",
            "Safety Warnings", "Key Indications"
        ])
        
        # Data rows
        for r in results:
            b = r.botanical
            common_names = "; ".join(b.common_names[:3])
            
            # Get evidence levels
            evidence_levels = set(m["evidence_level"] for m in r.matches)
            top_evidence = max(evidence_levels, key=lambda e: self._get_evidence_multiplier(e)) if evidence_levels else "unknown"
            
            # Safety warnings
            safety_warning = "Yes" if (r.safety_profile and r.safety_profile.has_critical_warnings) else "No"
            
            # Key indications
            key_indications = "; ".join(list(dict.fromkeys(m["indication"] for m in r.matches))[:5])
            
            writer.writerow([
                r.rank,
                b.latin_binomial,
                common_names,
                b.family,
                f"{r.total_score:.2f}",
                len(r.matches),
                top_evidence,
                safety_warning,
                key_indications
            ])
        
        csv_str = output.getvalue()
        
        if filepath:
            with open(filepath, 'w', newline='') as f:
                f.write(csv_str)
        
        return csv_str
    
    def export_repertorization_to_markdown(
        self,
        results: List[RepertorizationResult],
        filepath: Optional[str] = None,
        symptoms: Optional[List[str]] = None
    ) -> str:
        """
        Export repertorization results to Markdown report.
        
        Args:
            results: Repertorization results
            filepath: Optional file path to save to
            symptoms: Optional list of symptoms for context
        
        Returns:
            Markdown string
        """
        lines = []
        lines.append("# Botanical Repertorization Report")
        lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        if symptoms:
            lines.append(f"\n**Symptoms:** {', '.join(symptoms)}")
        
        lines.append(f"\n**Total Results:** {len(results)}")
        lines.append("\n---\n")
        
        for r in results:
            b = r.botanical
            lines.append(f"## #{r.rank} {b.latin_binomial}")
            lines.append(f"\n**Common Names:** {', '.join(b.common_names[:5])}")
            lines.append(f"\n**Family:** {b.family or 'Unknown'}")
            lines.append(f"\n**Total Score:** {r.total_score:.2f}")
            
            if r.safety_profile:
                if r.safety_profile.has_critical_warnings:
                    lines.append("\n**⚠️ Safety Warnings Present**")
                    for contra in r.safety_profile.contraindications[:3]:
                        lines.append(f"- {contra.contraindication} ({contra.severity})")
            
            lines.append("\n**Matching Indications:**")
            seen = set()
            for match in r.matches[:8]:
                key = match["indication"]
                if key not in seen:
                    seen.add(key)
                    lines.append(f"- {key} [{match['evidence_level']}]")
            
            lines.append("\n---\n")
        
        md = "\n".join(lines)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(md)
        
        return md
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_indications_by_category(self, category: str) -> List[Indication]:
        """Get all indications in a category."""
        return self.db.get_indications_by_category(category)
    
    def get_categories(self) -> List[str]:
        """Get all unique indication categories."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM indications WHERE category IS NOT NULL"
            ).fetchall()
            return sorted([row["category"] for row in rows])
    
    def get_evidence_levels(self) -> List[str]:
        """Get all evidence levels in the database."""
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT evidence_level FROM indication_botanical_edges"
            ).fetchall()
            return sorted([row["evidence_level"] for row in rows if row["evidence_level"]])
    
    def compare_botanicals(
        self,
        binomials: List[str]
    ) -> Dict[str, Any]:
        """
        Compare multiple botanicals side-by-side.
        
        Args:
            binomials: List of Latin binomials to compare
        
        Returns:
            Comparison dictionary
        """
        botanicals = []
        for b in binomials:
            bot = self.get_botanical_by_binomial(b)
            if bot:
                botanicals.append(bot)
        
        # Get indications for each
        comparison = {
            "botanicals": [b.to_dict() for b in botanicals],
            "common_indications": [],
            "unique_indications": {}
        }
        
        all_indications = defaultdict(list)
        for bot in botanicals:
            edges = self.db.get_edges_by_botanical(bot.id)
            for edge in edges:
                all_indications[edge.indication.indication_text].append(bot.latin_binomial)
        
        for indication, bots in all_indications.items():
            if len(bots) > 1:
                comparison["common_indications"].append({
                    "indication": indication,
                    "botanicals": bots
                })
        
        return comparison
    
    def format_repertorization_results(
        self, 
        results: List[RepertorizationResult],
        include_matches: bool = False
    ) -> str:
        """Format repertorization results as readable text."""
        lines = []
        lines.append("=" * 70)
        lines.append("BOTANICAL REPERTORIZATION RESULTS")
        lines.append("=" * 70)
        lines.append("")
        
        for result in results:
            b = result.botanical
            lines.append(f"#{result.rank} {b.latin_binomial}")
            lines.append(f"    Common: {', '.join(b.common_names[:3])}")
            lines.append(f"    Family: {b.family or 'Unknown'}")
            lines.append(f"    Score: {result.total_score:.2f}")
            
            if result.safety_profile and result.safety_profile.has_critical_warnings:
                lines.append("    ⚠️  SAFETY WARNINGS PRESENT")
            
            if include_matches and result.matches:
                lines.append("    Matching indications:")
                for match in result.matches[:5]:
                    lines.append(f"      • {match['indication']} ({match['evidence_level']})")
            
            lines.append("")
        
        return "\n".join(lines)


def main():
    """CLI for repertory operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Botanical Repertory")
    subparsers = parser.add_subparsers(dest='command')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search indications')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--mode', choices=['lexical', 'vector', 'hybrid'],
                              default='hybrid', help='Search mode')
    search_parser.add_argument('--limit', type=int, default=10)
    
    # Repertorize command
    rep_parser = subparsers.add_parser('repertorize', help='Repertorize symptoms')
    rep_parser.add_argument('symptoms', nargs='+', help='Symptoms to analyze')
    rep_parser.add_argument('--top', type=int, default=10)
    rep_parser.add_argument('--mode', choices=['lexical', 'vector', 'hybrid'],
                           default='hybrid')
    rep_parser.add_argument('--export', help='Export to file (json, csv, md)')
    
    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')
    
    args = parser.parse_args()
    
    rep = BotanicalRepertory()
    
    if args.command == 'search':
        results = rep.search_indications(args.query, mode=args.mode, limit=args.limit)
        print(f"\nResults for '{args.query}':")
        for r in results:
            print(f"  [{r.score:.3f}] {r.item.indication_text}")
    
    elif args.command == 'repertorize':
        results = rep.repertorize(args.symptoms, top_n=args.top, mode=args.mode)
        print(rep.format_repertorization_results(results, include_matches=True))
        
        if args.export:
            if args.export.endswith('.json'):
                rep.export_repertorization_to_json(results, args.export)
            elif args.export.endswith('.csv'):
                rep.export_repertorization_to_csv(results, args.export)
            elif args.export.endswith('.md'):
                rep.export_repertorization_to_markdown(results, args.export, args.symptoms)
            print(f"\nExported to {args.export}")
    
    elif args.command == 'stats':
        stats = rep.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
