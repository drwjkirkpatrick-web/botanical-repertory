"""
Vector search implementation using random projection.

This module provides:
- VectorIndexBuilder: Build vector index from indications
- VectorSearcher: Search using cosine similarity
- Random projection for fast, local embedding (no API calls)

Based on the OOREP approach: hashed n-gram features + random projection.
"""

import json
import numpy as np
import sqlite3
import re
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass

from src.database import BotanicalDatabase
from src.models import SearchResult, Indication


@dataclass
class VectorMeta:
    """Metadata for vector index."""
    count: int
    dim: int
    dtype: str
    random_seed: int
    built_at: str
    source: str = "indications"


class TextEmbedding:
    """
    Embed text using feature hashing + random projection.
    
    This is a lightweight, local embedding method that doesn't require
    downloading large ML models or making API calls.
    """
    
    def __init__(
        self,
        dim: int = 384,
        feature_dim: int = 10000,
        ngram_range: Tuple[int, int] = (1, 2),
        random_seed: int = 42
    ):
        """
        Initialize embedder.
        
        Args:
            dim: Output vector dimension (projection size)
            feature_dim: Hashing feature space size (higher = more discriminative)
            ngram_range: N-gram range to extract (1,2) = unigrams + bigrams
            random_seed: Seed for reproducible random projection
        """
        self.dim = dim
        self.feature_dim = feature_dim
        self.ngram_range = ngram_range
        
        # Generate random projection matrix (Gaussian)
        np.random.seed(random_seed)
        self.projection = np.random.randn(dim, feature_dim)
        
        # Normalize projection vectors
        self.projection = self.projection / np.linalg.norm(
            self.projection, axis=1, keepdims=True
        )
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words and n-grams.
        
        Args:
            text: Input text
        
        Returns:
            List of tokens (unigrams and bigrams)
        """
        # Clean and normalize
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        
        tokens = []
        min_n, max_n = self.ngram_range
        
        for n in range(min_n, max_n + 1):
            for i in range(len(words) - n + 1):
                ngram = ' '.join(words[i:i + n])
                tokens.append(ngram)
        
        return tokens
    
    def _hash_feature(self, token: str) -> int:
        """
        Hash a token to a feature index using MurmurHash-style hashing.
        
        Args:
            token: String token
        
        Returns:
            Integer hash in range [0, feature_dim)
        """
        # Use hashlib for consistent hashing
        hash_bytes = hashlib.md5(token.encode('utf-8')).digest()
        hash_int = int.from_bytes(hash_bytes[:4], byteorder='little', signed=False)
        return hash_int % self.feature_dim
    
    def _text_to_features(self, text: str) -> np.ndarray:
        """
        Convert text to feature vector using hashing trick.
        
        Args:
            text: Input text
        
        Returns:
            Feature vector of shape (feature_dim,)
        """
        features = np.zeros(self.feature_dim)
        tokens = self._tokenize(text)
        
        for token in tokens:
            idx = self._hash_feature(token)
            # TF-style weighting (can be enhanced with IDF)
            features[idx] += 1.0
        
        # Normalize
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm
        
        return features
    
    def embed(self, text: str) -> np.ndarray:
        """
        Embed text into dense vector.
        
        Args:
            text: Input text
        
        Returns:
            Dense vector of shape (dim,)
        """
        features = self._text_to_features(text)
        
        # Project to lower dimension
        vector = np.dot(self.projection, features)
        
        # Normalize output
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        Embed multiple texts efficiently.
        
        Args:
            texts: List of input texts
        
        Returns:
            Matrix of shape (n_texts, dim)
        """
        vectors = np.array([self.embed(t) for t in texts])
        return vectors


class VectorIndexBuilder:
    """
    Build vector index from indications database.
    """
    
    def __init__(
        self,
        db_path: str = "data/botanical.sqlite",
        index_path: str = "data/botanical_vector_index.npz",
        meta_path: str = "data/botanical_vector_meta.json"
    ):
        self.db = BotanicalDatabase(db_path)
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        
        # Ensure directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
    
    def build(
        self,
        dim: int = 384,
        dtype: str = "float16",
        random_seed: int = 42,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Build vector index from all indications in database.
        
        Args:
            dim: Vector dimension
            dtype: NumPy dtype for storage (float16 for memory efficiency)
            random_seed: Random seed for reproducibility
            batch_size: Number of indications to process at once
        
        Returns:
            Statistics dict with count, path, etc.
        """
        print(f"Building vector index (dim={dim}, dtype={dtype})...")
        
        # Initialize embedder
        embedder = TextEmbedding(dim=dim, random_seed=random_seed)
        
        # Get all indications from database
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT id, indication_text, normalized_text FROM indications"
            )
            rows = cursor.fetchall()
        
        if not rows:
            print("No indications found in database. Run ingestion first.")
            return {"built": False, "count": 0, "error": "No indications"}
        
        print(f"Processing {len(rows)} indications...")
        
        # Process in batches
        all_ids = []
        all_vectors = []
        
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            
            # Prepare texts (prefer normalized, fallback to original)
            texts = [
                row["normalized_text"] or row["indication_text"]
                for row in batch
            ]
            ids = [row["id"] for row in batch]
            
            # Embed batch
            vectors = embedder.embed_batch(texts)
            
            all_ids.extend(ids)
            all_vectors.append(vectors)
            
            print(f"  Processed {min(i + batch_size, len(rows))}/{len(rows)}")
        
        # Concatenate all vectors
        all_vectors = np.vstack(all_vectors)
        
        # Convert to target dtype
        if dtype == "float16":
            all_vectors = all_vectors.astype(np.float16)
        elif dtype == "float32":
            all_vectors = all_vectors.astype(np.float32)
        
        # Save index
        np.savez(
            self.index_path,
            vectors=all_vectors,
            ids=np.array(all_ids, dtype=np.int32)
        )
        
        # Save metadata
        meta = {
            "count": len(all_ids),
            "dim": dim,
            "dtype": dtype,
            "random_seed": random_seed,
            "built_at": str(np.datetime64('now')),
            "source": "indications"
        }
        
        with open(self.meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        
        # Update database metadata
        self.db.update_meta("vector_index_built", "true")
        self.db.update_meta("vector_index_count", str(len(all_ids)))
        
        print(f"\n✅ Index built successfully!")
        print(f"   Vectors: {len(all_ids)}")
        print(f"   Dimension: {dim}")
        print(f"   Size: {all_vectors.nbytes / 1024 / 1024:.1f} MB")
        print(f"   Path: {self.index_path}")
        
        return {
            "built": True,
            "count": len(all_ids),
            "dim": dim,
            "dtype": dtype,
            "path": str(self.index_path),
            "size_mb": all_vectors.nbytes / 1024 / 1024
        }
    
    def incremental_update(
        self,
        since: Optional[str] = None,
        dim: int = 384,
        random_seed: int = 42
    ) -> Dict[str, Any]:
        """
        Incrementally update index with new indications.
        
        Args:
            since: Timestamp to filter new indications (ISO format)
            dim: Vector dimension (must match existing index)
            random_seed: Random seed (must match existing index)
        
        Returns:
            Update statistics
        """
        # Load existing index
        if not self.index_path.exists():
            print("No existing index found. Run full build first.")
            return self.build(dim=dim, random_seed=random_seed)
        
        # Load existing data
        data = np.load(self.index_path)
        existing_vectors = data["vectors"]
        existing_ids = data["ids"]
        
        # Get new indications
        with self.db.connection() as conn:
            if since:
                cursor = conn.execute(
                    """SELECT id, indication_text, normalized_text 
                       FROM indications 
                       WHERE created_at > ?
                       AND id NOT IN ({})
                    """.format(','.join(map(str, existing_ids))),
                    (since,)
                )
            else:
                cursor = conn.execute(
                    """SELECT id, indication_text, normalized_text 
                       FROM indications 
                       WHERE id NOT IN ({})
                    """.format(','.join(map(str, existing_ids)))
                )
            
            rows = cursor.fetchall()
        
        if not rows:
            print("No new indications to add.")
            return {"updated": False, "added": 0}
        
        print(f"Adding {len(rows)} new indications to index...")
        
        # Embed new indications
        embedder = TextEmbedding(dim=dim, random_seed=random_seed)
        
        texts = [row["normalized_text"] or row["indication_text"] for row in rows]
        new_ids = [row["id"] for row in rows]
        new_vectors = embedder.embed_batch(texts)
        
        # Convert to same dtype as existing
        dtype = existing_vectors.dtype
        new_vectors = new_vectors.astype(dtype)
        
        # Merge
        all_vectors = np.vstack([existing_vectors, new_vectors])
        all_ids = np.concatenate([existing_ids, new_ids])
        
        # Save
        np.savez(self.index_path, vectors=all_vectors, ids=all_ids)
        
        # Update metadata
        with open(self.meta_path, 'r') as f:
            meta = json.load(f)
        
        meta["count"] = len(all_ids)
        meta["updated_at"] = str(np.datetime64('now'))
        
        with open(self.meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        
        print(f"✅ Incremental update complete. Total vectors: {len(all_ids)}")
        
        return {"updated": True, "added": len(rows), "total": len(all_ids)}


class VectorSearcher:
    """
    Search vector index using cosine similarity.
    """
    
    def __init__(
        self,
        index_path: str = "data/botanical_vector_index.npz",
        meta_path: str = "data/botanical_vector_meta.json",
        db_path: str = "data/botanical.sqlite"
    ):
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.db = BotanicalDatabase(db_path)
        
        self.vectors = None
        self.ids = None
        self.meta = None
        self.embedder = None
        
        self._load_index()
    
    def _load_index(self) -> bool:
        """Load vector index from disk."""
        if not self.index_path.exists() or not self.meta_path.exists():
            print("Vector index not found. Run build_index() first.")
            return False
        
        try:
            # Load vectors and IDs
            data = np.load(self.index_path)
            self.vectors = data["vectors"]
            self.ids = data["ids"]
            
            # Load metadata
            with open(self.meta_path, 'r') as f:
                self.meta = json.load(f)
            
            # Initialize embedder with same parameters
            self.embedder = TextEmbedding(
                dim=self.meta["dim"],
                random_seed=self.meta.get("random_seed", 42)
            )
            
            print(f"Loaded vector index: {len(self.ids)} vectors, dim={self.meta['dim']}")
            return True
            
        except Exception as e:
            print(f"Error loading index: {e}")
            return False
    
    def is_ready(self) -> bool:
        """Check if index is loaded and ready."""
        return self.vectors is not None and len(self.vectors) > 0
    
    def search(
        self,
        query: str,
        limit: int = 20,
        min_score: float = 0.0
    ) -> List[SearchResult]:
        """
        Search for similar indications using cosine similarity.
        
        Args:
            query: Search query text
            limit: Maximum number of results
            min_score: Minimum similarity score (0-1)
        
        Returns:
            List of SearchResult objects
        """
        if not self.is_ready():
            print("Vector index not ready. Run build_index() first.")
            return []
        
        # Embed query
        query_vector = self.embedder.embed(query)
        
        # Convert to float32 for computation
        query_vector = query_vector.astype(np.float32)
        vectors = self.vectors.astype(np.float32)
        
        # Compute cosine similarities (dot product of normalized vectors)
        similarities = np.dot(vectors, query_vector)
        
        # Filter by minimum score
        valid_indices = np.where(similarities >= min_score)[0]
        
        # Get top-k
        if len(valid_indices) > limit:
            top_indices = valid_indices[np.argsort(similarities[valid_indices])[-limit:]]
        else:
            top_indices = valid_indices[np.argsort(similarities[valid_indices])]
        
        # Reverse to get descending order
        top_indices = top_indices[::-1]
        
        # Build results
        results = []
        for idx in top_indices:
            indication_id = int(self.ids[idx])
            score = float(similarities[idx])
            
            # Fetch indication from database
            indication = self.db.get_indication_by_id(indication_id)
            
            if indication:
                results.append(SearchResult(
                    item=indication,
                    score=score,
                    match_type="vector",
                    matched_text=indication.indication_text
                ))
        
        return results
    
    def search_batch(
        self,
        queries: List[str],
        limit: int = 20
    ) -> List[List[SearchResult]]:
        """
        Search multiple queries efficiently.
        
        Args:
            queries: List of query strings
            limit: Results per query
        
        Returns:
            List of result lists (one per query)
        """
        return [self.search(q, limit) for q in queries]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self.is_ready():
            return {"ready": False}
        
        return {
            "ready": True,
            "count": len(self.ids),
            "dim": self.meta["dim"],
            "dtype": self.meta["dtype"],
            "size_mb": self.vectors.nbytes / 1024 / 1024,
            "built_at": self.meta.get("built_at", "unknown"),
        }


def main():
    """CLI for vector index operations."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vector index management")
    parser.add_argument("--build", action="store_true", help="Build vector index")
    parser.add_argument("--search", metavar="QUERY", help="Search index")
    parser.add_argument("--stats", action="store_true", help="Show index stats")
    parser.add_argument("--dim", type=int, default=384, help="Vector dimension")
    parser.add_argument("--limit", type=int, default=10, help="Search result limit")
    
    args = parser.parse_args()
    
    if args.build:
        builder = VectorIndexBuilder()
        result = builder.build(dim=args.dim)
        print(json.dumps(result, indent=2))
    
    elif args.search:
        searcher = VectorSearcher()
        if not searcher.is_ready():
            print("Index not ready. Run --build first.")
            return
        
        results = searcher.search(args.search, limit=args.limit)
        print(f"\nSearch results for: '{args.search}'")
        print("-" * 50)
        for r in results:
            print(f"[{r.score:.3f}] {r.item.indication_text}")
    
    elif args.stats:
        searcher = VectorSearcher()
        stats = searcher.get_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()