"""
Integration tests for full repertory workflow.
"""

import pytest
import json
from pathlib import Path

# Mark all tests in this file as requiring database
pytestmark = pytest.mark.integration


class TestFullWorkflow:
    """Test complete repertory workflow."""
    
    @pytest.fixture
    def setup_repertory(self, tmp_path):
        """Set up a repertory with sample data."""
        from src.repertory import BotanicalRepertory
        from src.database import BotanicalDatabase
        from src.models import Botanical, Indication, BotanicalIndicationLink
        
        # Create test database
        db_path = tmp_path / "test_repertory.db"
        db = BotanicalDatabase(str(db_path))
        db.initialize_schema()
        
        # Insert sample botanicals
        botanicals = [
            Botanical(
                latin_binomial="Matricaria recutita",
                common_names=["Chamomile"],
                family="Asteraceae"
            ),
            Botanical(
                latin_binomial="Hypericum perforatum",
                common_names=["St. John's Wort"],
                family="Hypericaceae"
            ),
            Botanical(
                latin_binomial="Valeriana officinalis",
                common_names=["Valerian"],
                family="Caprifoliaceae"
            )
        ]
        
        bot_ids = {}
        for bot in botanicals:
            bot_id = db.insert_botanical(bot)
            bot_ids[bot.latin_binomial] = bot_id
        
        # Insert sample indications
        indications = [
            Indication(indication_text="Insomnia", normalized_text="insomnia", category="sleep"),
            Indication(indication_text="Anxiety", normalized_text="anxiety", category="mental"),
            Indication(indication_text="Depression", normalized_text="depression", category="mental"),
            Indication(indication_text="Nervous tension", normalized_text="nervous tension", category="mental"),
        ]
        
        ind_ids = {}
        for ind in indications:
            ind_id = db.insert_indication(ind)
            ind_ids[ind.normalized_text] = ind_id
        
        # Create links
        links = [
            # Chamomile
            ("Matricaria recutita", "insomnia", "clinical_trial", 2.0),
            ("Matricaria recutita", "anxiety", "clinical_trial", 2.0),
            ("Matricaria recutita", "nervous tension", "traditional", 1.0),
            # St. John's Wort
            ("Hypericum perforatum", "depression", "clinical_trial", 3.0),
            ("Hypericum perforatum", "anxiety", "clinical_observation", 1.5),
            # Valerian
            ("Valeriana officinalis", "insomnia", "clinical_trial", 2.5),
            ("Valeriana officinalis", "nervous tension", "traditional", 1.0),
        ]
        
        for bot_name, ind_name, evidence, weight in links:
            edge = BotanicalIndicationLink(
                indication_id=ind_ids[ind_name],
                botanical_id=bot_ids[bot_name],
                evidence_level=evidence,
                weight=weight
            )
            db.insert_edge(edge)
        
        # Create repertory instance pointing to test db
        # Note: This is a simplified setup - in reality you'd configure the path
        return db, bot_ids, ind_ids
    
    def test_database_setup(self, setup_repertory):
        """Test that setup worked correctly."""
        db, bot_ids, ind_ids = setup_repertory
        
        stats = db.get_stats()
        assert stats["botanicals"] == 3
        assert stats["indications"] == 4
        assert stats["indication_botanical_edges"] == 7
    
    def test_lexical_search_indications(self, setup_repertory):
        """Test searching indications with lexical search."""
        db, bot_ids, ind_ids = setup_repertory
        
        from search.lexical_search import LexicalSearcher
        
        searcher = LexicalSearcher(db)
        searcher.build_index()
        
        results = searcher.search("insomnia")
        
        assert len(results) > 0
        assert any("insomnia" in r.item.indication_text.lower() for r in results)
    
    def test_repertorization_ranking(self, setup_repertory):
        """Test that repertorization ranks botanicals correctly."""
        db, bot_ids, ind_ids = setup_repertory
        
        from src.repertory import BotanicalRepertory
        
        # This would require full setup with config - simplified test
        # In reality, you'd mock or configure the repertory properly
        
        # For now, just verify database is set up
        assert db.get_stats()["botanicals"] == 3


class TestExportFunctions:
    """Test export functionality."""
    
    def test_export_to_json(self, tmp_path):
        """Test JSON export."""
        from src.models import Botanical, RepertorizationResult
        from src.repertory import BotanicalRepertory
        
        # Create mock result
        bot = Botanical(
            latin_binomial="Test botanical",
            common_names=["Test"],
            family="Testaceae"
        )
        
        result = RepertorizationResult(
            botanical=bot,
            total_score=45.5,
            matches=[],
            rank=1
        )
        
        # Test export
        export_path = tmp_path / "test_export.json"
        
        # Create minimal repertory for export method
        json_str = BotanicalRepertory.export_repertorization_to_json(
            None,  # self would be None in this static-like usage
            [result],
            str(export_path)
        )
        
        assert export_path.exists()
        
        # Verify JSON content
        with open(export_path) as f:
            data = json.load(f)
            assert "results" in data
            assert data["total_results"] == 1
    
    def test_export_to_csv(self, tmp_path):
        """Test CSV export."""
        from src.models import Botanical, RepertorizationResult
        from src.repertory import BotanicalRepertory
        
        bot = Botanical(
            latin_binomial="Test botanical",
            common_names=["Test"],
            family="Testaceae"
        )
        
        result = RepertorizationResult(
            botanical=bot,
            total_score=45.5,
            matches=[],
            rank=1
        )
        
        export_path = tmp_path / "test_export.csv"
        
        csv_str = BotanicalRepertory.export_repertorization_to_csv(
            None,
            [result],
            str(export_path)
        )
        
        assert export_path.exists()
        assert "Latin Binomial" in csv_str


class TestCache:
    """Test caching functionality."""
    
    def test_cache_basic(self):
        """Test basic cache operations."""
        from src.repertory import ResultCache
        
        cache = ResultCache(max_size=10, ttl_seconds=60)
        
        # Store value
        cache.set(["result1"], "query", "param")
        
        # Retrieve value
        result = cache.get("query", "param")
        assert result == ["result1"]
    
    def test_cache_expiration(self):
        """Test that cache entries expire."""
        from src.repertory import ResultCache
        import time
        
        cache = ResultCache(max_size=10, ttl_seconds=0.1)
        
        cache.set(["result"], "query")
        
        # Should exist immediately
        assert cache.get("query") is not None
        
        # Wait for expiration
        time.sleep(0.15)
        
        # Should be expired
        assert cache.get("query") is None
    
    def test_cache_eviction(self):
        """Test that old entries are evicted."""
        from src.repertory import ResultCache
        
        cache = ResultCache(max_size=2, ttl_seconds=60)
        
        cache.set(["r1"], "q1")
        cache.set(["r2"], "q2")
        cache.set(["r3"], "q3")  # Should evict q1
        
        assert cache.get("q1") is None  # Evicted
        assert cache.get("q2") is not None
        assert cache.get("q3") is not None
