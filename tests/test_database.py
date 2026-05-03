"""
Tests for database operations.
"""

import pytest
import sqlite3
from pathlib import Path

from src.database import BotanicalDatabase
from src.models import Botanical, Indication, Contraindication


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    db = BotanicalDatabase(str(db_path))
    db.initialize_schema()
    return db


class TestDatabaseInitialization:
    """Test database initialization."""
    
    def test_schema_creation(self, temp_db):
        """Test that schema is created."""
        stats = temp_db.get_stats()
        assert isinstance(stats, dict)
        assert "botanicals" in stats
    
    def test_meta_table(self, temp_db):
        """Test that meta table exists."""
        version = temp_db.get_meta("schema_version")
        assert version is not None
        assert version == "1.0.0"


class TestBotanicalOperations:
    """Test botanical CRUD operations."""
    
    def test_insert_botanical(self, temp_db):
        """Test inserting a botanical."""
        bot = Botanical(
            latin_binomial="Matricaria recutita",
            common_names=["Chamomile", "German Chamomile"],
            family="Asteraceae"
        )
        
        bot_id = temp_db.insert_botanical(bot)
        assert bot_id is not None
        assert bot_id > 0
    
    def test_get_botanical_by_binomial(self, temp_db):
        """Test retrieving by binomial."""
        # Insert first
        bot = Botanical(latin_binomial="Hypericum perforatum")
        temp_db.insert_botanical(bot)
        
        # Retrieve
        retrieved = temp_db.get_botanical_by_binomial("Hypericum perforatum")
        assert retrieved is not None
        assert retrieved.latin_binomial == "Hypericum perforatum"
    
    def test_get_nonexistent_botanical(self, temp_db):
        """Test retrieving non-existent botanical."""
        result = temp_db.get_botanical_by_binomial("Nonexistent species")
        assert result is None
    
    def test_duplicate_insertion(self, temp_db):
        """Test that duplicates are handled."""
        bot = Botanical(latin_binomial="Test botanical")
        
        id1 = temp_db.insert_botanical(bot)
        id2 = temp_db.insert_botanical(bot)
        
        # Should return same ID
        assert id1 == id2


class TestIndicationOperations:
    """Test indication CRUD operations."""
    
    def test_insert_indication(self, temp_db):
        """Test inserting an indication."""
        ind = Indication(
            indication_text="Anxiety with depression",
            normalized_text="anxiety with depression",
            category="mental"
        )
        
        ind_id = temp_db.insert_indication(ind)
        assert ind_id is not None
        assert ind_id > 0
    
    def test_get_indication_by_id(self, temp_db):
        """Test retrieving indication by ID."""
        ind = Indication(indication_text="Insomnia", normalized_text="insomnia")
        ind_id = temp_db.insert_indication(ind)
        
        retrieved = temp_db.get_indication_by_id(ind_id)
        assert retrieved is not None
        assert retrieved.indication_text == "Insomnia"
    
    def test_normalized_text_uniqueness(self, temp_db):
        """Test that normalized text is unique."""
        ind1 = Indication(indication_text="Anxiety", normalized_text="anxiety")
        ind2 = Indication(indication_text="anxiety", normalized_text="anxiety")
        
        id1 = temp_db.insert_indication(ind1)
        id2 = temp_db.insert_indication(ind2)
        
        # Should return same ID due to UNIQUE constraint
        assert id1 == id2


class TestSafetyOperations:
    """Test safety-related operations."""
    
    def test_insert_contraindication(self, temp_db):
        """Test inserting contraindication."""
        # First insert botanical
        bot = Botanical(latin_binomial="Test botanical")
        bot_id = temp_db.insert_botanical(bot)
        
        contra = Contraindication(
            botanical_id=bot_id,
            contraindication="Pregnancy",
            severity="moderate"
        )
        
        contra_id = temp_db.insert_contraindication(contra)
        assert contra_id is not None
    
    def test_get_safety_profile(self, temp_db):
        """Test retrieving safety profile."""
        # Insert botanical
        bot = Botanical(latin_binomial="Test botanical")
        bot_id = temp_db.insert_botanical(bot)
        
        # Insert contraindication
        contra = Contraindication(
            botanical_id=bot_id,
            contraindication="Pregnancy",
            severity="moderate"
        )
        temp_db.insert_contraindication(contra)
        
        # Get safety profile
        profile = temp_db.get_safety_profile(bot_id)
        assert profile is not None
        assert profile.botanical is not None
        assert len(profile.contraindications) == 1
        assert profile.contraindications[0].contraindication == "Pregnancy"


class TestStats:
    """Test statistics methods."""
    
    def test_empty_stats(self, temp_db):
        """Test stats on empty database."""
        stats = temp_db.get_stats()
        
        assert stats["botanicals"] == 0
        assert stats["indications"] == 0
        assert stats["indication_botanical_edges"] == 0
    
    def test_stats_after_insertion(self, temp_db):
        """Test stats after inserting data."""
        # Insert botanical
        bot = Botanical(latin_binomial="Test")
        temp_db.insert_botanical(bot)
        
        stats = temp_db.get_stats()
        assert stats["botanicals"] == 1


class TestMetaOperations:
    """Test metadata operations."""
    
    def test_update_meta(self, temp_db):
        """Test updating meta value."""
        temp_db.update_meta("test_key", "test_value")
        
        value = temp_db.get_meta("test_key")
        assert value == "test_value"
    
    def test_get_nonexistent_meta(self, temp_db):
        """Test getting non-existent meta key."""
        value = temp_db.get_meta("nonexistent_key")
        assert value is None
