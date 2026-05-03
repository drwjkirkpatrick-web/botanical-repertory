"""
Tests for search functionality.
"""

import pytest
import numpy as np
from search.vector_index import TextEmbedding, VectorIndexBuilder, VectorSearcher
from search.lexical_search import Tokenizer, PorterStemmer, FuzzyMatcher


class TestPorterStemmer:
    """Test Porter Stemmer."""
    
    def test_basic_stemming(self):
        """Test basic word stemming."""
        stemmer = PorterStemmer()
        
        assert stemmer.stem("running") == "run"
        assert stemmer.stem("flies") == "fli"
        assert stemmer.stem("depression") == "depress"
    
    def test_short_words(self):
        """Test that short words are preserved."""
        stemmer = PorterStemmer()
        
        assert stemmer.stem("at") == "at"
        assert stemmer.stem("is") == "is"


class TestFuzzyMatcher:
    """Test Fuzzy Matcher."""
    
    def test_levenshtein_distance(self):
        """Test Levenshtein distance calculation."""
        matcher = FuzzyMatcher()
        
        # Same string
        assert matcher.levenshtein("test", "test") == 0
        
        # One edit
        assert matcher.levenshtein("test", "tent") == 1
        
        # Two edits
        assert matcher.levenshtein("kitten", "sitting") == 3
    
    def test_similarity(self):
        """Test similarity calculation."""
        matcher = FuzzyMatcher()
        
        # Identical
        assert matcher.similarity("test", "test") == 1.0
        
        # Similar
        sim = matcher.similarity("headache", "headach")
        assert sim > 0.8
        
        # Different
        sim = matcher.similarity("anxiety", "botanical")
        assert sim < 0.5


class TestTokenizer:
    """Test Tokenizer."""
    
    def test_basic_tokenization(self):
        """Test basic tokenization."""
        tokenizer = Tokenizer(stem=False)
        
        text = "anxiety and depression"
        tokens = tokenizer.tokenize(text, include_bigrams=False)
        
        assert "anxiety" in tokens
        assert "depression" in tokens
    
    def test_bigram_generation(self):
        """Test bigram generation."""
        tokenizer = Tokenizer(stem=False)
        
        text = "chronic anxiety disorder"
        tokens = tokenizer.tokenize(text, include_bigrams=True)
        
        assert "chronic_anxiety" in tokens
        assert "anxiety_disorder" in tokens
    
    def test_synonym_expansion(self):
        """Test synonym expansion."""
        tokenizer = Tokenizer(stem=False, use_synonyms=True)
        
        tokens = ["insomnia"]
        expanded = tokenizer.expand_synonyms(tokens)
        
        assert "sleeplessness" in expanded
        assert "sleep disorder" in expanded


class TestTextEmbedding:
    """Test Text Embedding."""
    
    def test_embedding_shape(self):
        """Test that embeddings have correct shape."""
        embedder = TextEmbedding(dim=128, random_seed=42)
        
        text = "anxiety"
        vector = embedder.embed(text)
        
        assert vector.shape == (128,)
    
    def test_embedding_normalization(self):
        """Test that embeddings are normalized."""
        embedder = TextEmbedding(dim=128, random_seed=42)
        
        text = "anxiety and depression"
        vector = embedder.embed(text)
        
        # Should be unit vector (approximately)
        norm = np.linalg.norm(vector)
        assert abs(norm - 1.0) < 0.001
    
    def test_similar_texts_have_high_similarity(self):
        """Test that similar texts have high cosine similarity."""
        embedder = TextEmbedding(dim=128, random_seed=42)
        
        v1 = embedder.embed("anxiety and stress")
        v2 = embedder.embed("anxiety and worry")
        v3 = embedder.embed("botanical garden")
        
        sim_12 = np.dot(v1, v2)
        sim_13 = np.dot(v1, v3)
        
        # Similar texts should have higher similarity
        assert sim_12 > sim_13
    
    def test_batch_embedding(self):
        """Test batch embedding."""
        embedder = TextEmbedding(dim=64, random_seed=42)
        
        texts = ["anxiety", "depression", "insomnia"]
        vectors = embedder.embed_batch(texts)
        
        assert vectors.shape == (3, 64)
        
        # All should be normalized
        for v in vectors:
            assert abs(np.linalg.norm(v) - 1.0) < 0.001


class TestVectorSearchIntegration:
    """Integration tests for vector search (requires database)."""
    
    @pytest.mark.skip(reason="Requires database with indications")
    def test_index_building(self):
        """Test building vector index."""
        builder = VectorIndexBuilder()
        result = builder.build(dim=64, dtype="float32")
        
        assert result["built"] is True
        assert result["count"] > 0
    
    @pytest.mark.skip(reason="Requires existing index")
    def test_vector_search(self):
        """Test vector search."""
        searcher = VectorSearcher()
        
        if not searcher.is_ready():
            pytest.skip("No vector index available")
        
        results = searcher.search("anxiety", limit=5)
        
        assert len(results) <= 5
        assert all(hasattr(r, "score") for r in results)
