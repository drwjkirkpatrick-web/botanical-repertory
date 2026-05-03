"""
Tests for data models.
"""

import pytest
from src.models import (
    Botanical, Indication, BotanicalIndicationLink,
    Contraindication, SafetyProfile, RepertorizationResult
)


class TestBotanical:
    """Test Botanical dataclass."""
    
    def test_basic_creation(self):
        """Test basic botanical creation."""
        bot = Botanical(
            id=1,
            latin_binomial="Matricaria recutita",
            common_names=["Chamomile", "German Chamomile"],
            family="Asteraceae"
        )
        assert bot.id == 1
        assert bot.latin_binomial == "Matricaria recutita"
        assert len(bot.common_names) == 2
    
    def test_short_name(self):
        """Test short name generation."""
        bot = Botanical(latin_binomial="Hypericum perforatum")
        assert bot.short_name == "H. perforatum"
        
        bot2 = Botanical(latin_binomial="Single")
        assert bot2.short_name == "Single"
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        bot = Botanical(
            id=1,
            latin_binomial="Matricaria recutita",
            common_names=["Chamomile"],
            family="Asteraceae"
        )
        d = bot.to_dict()
        assert d["latin_binomial"] == "Matricaria recutita"
        assert d["short_name"] == "M. recutita"


class TestBotanicalIndicationLink:
    """Test BotanicalIndicationLink dataclass."""
    
    def test_evidence_score_calculation(self):
        """Test evidence score calculation."""
        link = BotanicalIndicationLink(
            weight=2.0,
            evidence_level="clinical_trial"
        )
        # clinical_trial multiplier is 2.5
        assert link.evidence_score == 2.5
        assert link.total_score == 5.0  # 2.0 * 2.5
    
    def test_unknown_evidence_level(self):
        """Test handling of unknown evidence level."""
        link = BotanicalIndicationLink(
            weight=1.0,
            evidence_level="unknown"
        )
        assert link.evidence_score == 1.0
        assert link.total_score == 1.0


class TestSafetyProfile:
    """Test SafetyProfile dataclass."""
    
    def test_no_warnings(self):
        """Test profile with no warnings."""
        bot = Botanical(latin_binomial="Test bot")
        profile = SafetyProfile(
            botanical=bot,
            contraindications=[],
            drug_interactions=[]
        )
        assert not profile.has_critical_warnings
    
    def test_absolute_contraindication(self):
        """Test profile with absolute contraindication."""
        bot = Botanical(latin_binomial="Test bot")
        contra = Contraindication(
            contraindication="Pregnancy",
            severity="absolute"
        )
        profile = SafetyProfile(
            botanical=bot,
            contraindications=[contra]
        )
        assert profile.has_critical_warnings


class TestRepertorizationResult:
    """Test RepertorizationResult dataclass."""
    
    def test_basic_creation(self):
        """Test basic creation."""
        bot = Botanical(latin_binomial="Matricaria recutita")
        result = RepertorizationResult(
            botanical=bot,
            total_score=45.5,
            rank=1
        )
        assert result.rank == 1
        assert result.total_score == 45.5
