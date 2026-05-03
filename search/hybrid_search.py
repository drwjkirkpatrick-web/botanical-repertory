"""
Hybrid search: combines lexical + vector using Reciprocal Rank Fusion (RRF).

The RRF formula: score = sum(1 / (k + rank))
where k is a constant (typically 60) and rank is the position in each list.

This provides a robust way to combine results from different retrieval methods
without requiring score normalization.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from collections import defaultdict

from src.models import SearchResult, Indication


@dataclass
class RankedResult:
    """Internal structure for ranked result."""
    indication: Indication
    lexical_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    lexical_score: float = 0.0
    vector_score: float = 0.0
    
    def rrf_score(self, k: int = 60) -> float:
        """Calculate RRF score."""
        score = 0.0
        if self.lexical_rank is not None:
            score += 1.0 / (k + self.lexical_rank)
        if self.vector_rank is not None:
            score += 1.0 / (k + self.vector_rank)
        return score
    
    def weighted_score(
        self,
        lexical_weight: float = 0.4,
        vector_weight: float = 0.6
    ) -> float:
        """Calculate weighted score from original retrieval scores."""
        score = 0.0
        if self.lexical_score > 0:
            score += lexical_weight * self.lexical_score
        if self.vector_score > 0:
            score += vector_weight * self.vector_score
        return score


class HybridSearcher:
    """
    Hybrid search combining lexical and vector results.
    
    Supports multiple fusion strategies:
    - RRF (Reciprocal Rank Fusion): default, robust
    - Weighted score fusion: uses original retrieval scores
    - Interleaving: alternate between sources
    """
    
    def __init__(
        self,
        lexical_searcher,
        vector_searcher,
        config: Dict[str, Any]
    ):
        """
        Initialize hybrid searcher.
        
        Args:
            lexical_searcher: LexicalSearcher instance
            vector_searcher: VectorSearcher instance
            config: Configuration dict with keys:
                - lexical_weight: weight for lexical scores
                - vector_weight: weight for vector scores
                - rrf_k: RRF constant (default 60)
                - fusion_method: 'rrf', 'weighted', or 'interleave'
        """
        self.lexical = lexical_searcher
        self.vector = vector_searcher
        self.config = config
        
        self.lexical_weight = config.get("lexical_weight", 0.4)
        self.vector_weight = config.get("vector_weight", 0.6)
        self.rrf_k = config.get("rrf_k", 60)
        self.fusion_method = config.get("fusion_method", "rrf")
    
    def search(
        self,
        query: str,
        limit: int = 20,
        category: Optional[str] = None,
        lexical_limit: int = 50,
        vector_limit: int = 50
    ) -> List[SearchResult]:
        """
        Search using hybrid approach.
        
        Args:
            query: Search query
            limit: Number of results to return
            category: Filter by category
            lexical_limit: Number of lexical results to fetch
            vector_limit: Number of vector results to fetch
        
        Returns:
            Fused and ranked list of SearchResult objects
        """
        # Get lexical results
        lexical_results = self.lexical.search(
            query,
            limit=lexical_limit,
            category=category
        )
        
        # Get vector results (if available)
        vector_results = []
        if self.vector.is_ready():
            vector_results = self.vector.search(query, limit=vector_limit)
        
        # Fuse results
        if self.fusion_method == "rrf":
            return self._fuse_rrf(lexical_results, vector_results, limit)
        elif self.fusion_method == "weighted":
            return self._fuse_weighted(lexical_results, vector_results, limit)
        elif self.fusion_method == "interleave":
            return self._fuse_interleave(lexical_results, vector_results, limit)
        else:
            raise ValueError(f"Unknown fusion method: {self.fusion_method}")
    
    def _fuse_rrf(
        self,
        lexical_results: List[SearchResult],
        vector_results: List[SearchResult],
        limit: int
    ) -> List[SearchResult]:
        """
        Fuse results using Reciprocal Rank Fusion.
        
        RRF gives equal opportunity to both retrieval methods regardless
        of their score distributions.
        """
        # Build map of indication_id -> RankedResult
        result_map: Dict[int, RankedResult] = {}
        
        # Add lexical results
        for rank, result in enumerate(lexical_results, 1):
            ind_id = result.item.id
            if ind_id not in result_map:
                result_map[ind_id] = RankedResult(indication=result.item)
            result_map[ind_id].lexical_rank = rank
            result_map[ind_id].lexical_score = result.score
        
        # Add vector results
        for rank, result in enumerate(vector_results, 1):
            ind_id = result.item.id
            if ind_id not in result_map:
                result_map[ind_id] = RankedResult(indication=result.item)
            result_map[ind_id].vector_rank = rank
            result_map[ind_id].vector_score = result.score
        
        # Calculate RRF scores and sort
        scored_results = []
        for ranked in result_map.values():
            scored_results.append({
                'result': ranked,
                'score': ranked.rrf_score(self.rrf_k)
            })
        
        # Sort by RRF score descending
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Build final results
        final_results = []
        for item in scored_results[:limit]:
            ranked = item['result']
            
            # Determine match type
            if ranked.lexical_rank and ranked.vector_rank:
                match_type = "hybrid"
            elif ranked.lexical_rank:
                match_type = "lexical"
            else:
                match_type = "vector"
            
            final_results.append(SearchResult(
                item=ranked.indication,
                score=item['score'],
                match_type=match_type,
                matched_text=ranked.indication.indication_text
            ))
        
        return final_results
    
    def _fuse_weighted(
        self,
        lexical_results: List[SearchResult],
        vector_results: List[SearchResult],
        limit: int
    ) -> List[SearchResult]:
        """
        Fuse results using weighted score combination.
        
        This requires the retrieval scores to be on comparable scales.
        """
        # Build map of indication_id -> RankedResult
        result_map: Dict[int, RankedResult] = {}
        
        # Add lexical results
        for result in lexical_results:
            ind_id = result.item.id
            if ind_id not in result_map:
                result_map[ind_id] = RankedResult(indication=result.item)
            result_map[ind_id].lexical_score = result.score
        
        # Add vector results
        for result in vector_results:
            ind_id = result.item.id
            if ind_id not in result_map:
                result_map[ind_id] = RankedResult(indication=result.item)
            result_map[ind_id].vector_score = result.score
        
        # Calculate weighted scores
        scored_results = []
        for ranked in result_map.values():
            score = ranked.weighted_score(
                self.lexical_weight,
                self.vector_weight
            )
            scored_results.append({
                'result': ranked,
                'score': score
            })
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Build final results
        final_results = []
        for item in scored_results[:limit]:
            ranked = item['result']
            
            # Determine match type
            if ranked.lexical_score > 0 and ranked.vector_score > 0:
                match_type = "hybrid"
            elif ranked.lexical_score > 0:
                match_type = "lexical"
            else:
                match_type = "vector"
            
            final_results.append(SearchResult(
                item=ranked.indication,
                score=item['score'],
                match_type=match_type,
                matched_text=ranked.indication.indication_text
            ))
        
        return final_results
    
    def _fuse_interleave(
        self,
        lexical_results: List[SearchResult],
        vector_results: List[SearchResult],
        limit: int
    ) -> List[SearchResult]:
        """
        Fuse results by interleaving lexical and vector results.
        
        Simple round-robin: lexical[0], vector[0], lexical[1], vector[1], ...
        """
        final_results = []
        seen_ids = set()
        
        # Interleave
        max_len = max(len(lexical_results), len(vector_results))
        for i in range(max_len):
            # Add lexical result
            if i < len(lexical_results):
                result = lexical_results[i]
                if result.item.id not in seen_ids:
                    seen_ids.add(result.item.id)
                    final_results.append(SearchResult(
                        item=result.item,
                        score=result.score,
                        match_type="lexical",
                        matched_text=result.item.indication_text
                    ))
            
            # Add vector result
            if i < len(vector_results):
                result = vector_results[i]
                if result.item.id not in seen_ids:
                    seen_ids.add(result.item.id)
                    final_results.append(SearchResult(
                        item=result.item,
                        score=result.score,
                        match_type="vector",
                        matched_text=result.item.indication_text
                    ))
            
            if len(final_results) >= limit:
                break
        
        return final_results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hybrid searcher statistics."""
        return {
            "fusion_method": self.fusion_method,
            "lexical_weight": self.lexical_weight,
            "vector_weight": self.vector_weight,
            "rrf_k": self.rrf_k,
            "lexical_indexed": self.lexical.get_stats()["indexed"],
            "vector_ready": self.vector.is_ready()
        }


def main():
    """CLI for hybrid search testing."""
    import argparse
    import sys
    from pathlib import Path
    
    # Add parent to path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from src.database import BotanicalDatabase
    from search.lexical_search import LexicalSearcher
    from search.vector_index import VectorSearcher
    
    parser = argparse.ArgumentParser(description="Hybrid search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--method", choices=['rrf', 'weighted', 'interleave'],
                       default='rrf', help="Fusion method")
    parser.add_argument("--lexical-weight", type=float, default=0.4)
    parser.add_argument("--vector-weight", type=float, default=0.6)
    parser.add_argument("--k", type=int, default=60, help="RRF constant")
    parser.add_argument("--limit", type=int, default=10)
    
    args = parser.parse_args()
    
    # Initialize searchers
    db = BotanicalDatabase()
    lexical = LexicalSearcher(db)
    vector = VectorSearcher()
    
    config = {
        "lexical_weight": args.lexical_weight,
        "vector_weight": args.vector_weight,
        "rrf_k": args.k,
        "fusion_method": args.method
    }
    
    searcher = HybridSearcher(lexical, vector, config)
    results = searcher.search(args.query, limit=args.limit)
    
    print(f"\nHybrid search results for: '{args.query}'")
    print(f"Method: {args.method}")
    print("-" * 60)
    for r in results:
        print(f"[{r.score:.4f}] ({r.match_type}) {r.item.indication_text}")


if __name__ == "__main__":
    main()
