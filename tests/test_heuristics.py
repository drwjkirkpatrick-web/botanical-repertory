"""
Tests for heuristics and extraction.
"""

import pytest
from ingestion.heuristics_v1 import (
    LatinBinomialExtractor,
    IndicationExtractor,
    EvidenceLevelDetector,
    SafetySignalDetector,
    TextChunker
)


class TestLatinBinomialExtractor:
    """Test Latin binomial extraction."""
    
    def test_standard_binomial(self):
        """Test extracting standard binomial."""
        extractor = LatinBinomialExtractor()
        text = "Hypericum perforatum is used for depression."
        results = extractor.extract(text)
        
        assert len(results) == 1
        assert results[0].value == "Hypericum perforatum"
        assert results[0].confidence > 0.8
    
    def test_abbreviated_genus(self):
        """Test extracting abbreviated genus."""
        extractor = LatinBinomialExtractor()
        text = "H. perforatum is commonly known as St. John's Wort."
        results = extractor.extract(text)
        
        assert len(results) >= 1
        assert any("H. perforatum" == r.value for r in results)
    
    def test_with_variety(self):
        """Test extracting variety."""
        extractor = LatinBinomialExtractor()
        text = "Hypericum perforatum var. angustifolium"
        results = extractor.extract(text)
        
        assert len(results) == 1
        assert "var." in results[0].value
    
    def test_false_positives_filtered(self):
        """Test that false positives are filtered."""
        extractor = LatinBinomialExtractor()
        text = "See Figure 1 in the Appendix."
        results = extractor.extract(text)
        
        assert len(results) == 0


class TestIndicationExtractor:
    """Test indication extraction."""
    
    def test_normalize_insomnia(self):
        """Test insomnia normalization."""
        extractor = IndicationExtractor()
        
        variations = [
            "cannot sleep",
            "sleeplessness",
            "sleep disorder",
            "difficulty sleeping"
        ]
        
        for v in variations:
            normalized = extractor.normalize(v)
            assert normalized == "insomnia", f"Failed for '{v}': got '{normalized}'"
    
    def test_normalize_headache(self):
        """Test headache normalization."""
        extractor = IndicationExtractor()
        
        variations = [
            "head pain",
            "cephalalgia"
        ]
        
        for v in variations:
            normalized = extractor.normalize(v)
            assert normalized == "headache"
    
    def test_extract_from_text(self):
        """Test extracting indications from text."""
        extractor = IndicationExtractor()
        text = "Traditionally used for anxiety and depression."
        results = extractor.extract(text)
        
        assert len(results) >= 1
        normalized = [r.value for r in results]
        assert "anxiety" in normalized or "depression" in normalized
    
    def test_categorize_symptom(self):
        """Test symptom categorization."""
        extractor = IndicationExtractor()
        
        assert extractor.categorize("insomnia") == "sleep"
        assert extractor.categorize("anxiety") == "mental"
        assert extractor.categorize("stomach pain") == "digestive"


class TestEvidenceLevelDetector:
    """Test evidence level detection."""
    
    def test_clinical_trial_detection(self):
        """Test detecting clinical trial evidence."""
        detector = EvidenceLevelDetector()
        
        text = "Randomized controlled trial showed significant improvement."
        level, confidence = detector.detect(text)
        
        assert level == "clinical_trial"
        assert confidence > 0.5
    
    def test_traditional_use_detection(self):
        """Test detecting traditional use."""
        detector = EvidenceLevelDetector()
        
        text = "Traditional use in Ayurvedic medicine for centuries."
        level, confidence = detector.detect(text)
        
        assert level == "traditional"
    
    def test_multiplier_lookup(self):
        """Test evidence multiplier lookup."""
        detector = EvidenceLevelDetector()
        
        assert detector.get_multiplier("clinical_trial") == 2.5
        assert detector.get_multiplier("traditional") == 1.0
        assert detector.get_multiplier("unknown") == 1.0


class TestSafetySignalDetector:
    """Test safety signal detection."""
    
    def test_contraindication_extraction(self):
        """Test extracting contraindications."""
        detector = SafetySignalDetector()
        
        text = "Contraindicated in pregnancy and lactation."
        results = detector.extract_contraindications(text)
        
        assert len(results) >= 1
        assert any("pregnancy" in r.value.lower() for r in results)
    
    def test_severity_detection(self):
        """Test severity level detection."""
        detector = SafetySignalDetector()
        
        assert detector._detect_severity("Absolute contraindication") == "absolute"
        assert detector._detect_severity("May cause mild nausea") == "mild"


class TestTextChunker:
    """Test text chunking."""
    
    def test_basic_chunking(self):
        """Test basic text chunking."""
        chunker = TextChunker(chunk_size=50, overlap=10)
        
        text = "This is a test. " * 20
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) > 0
        assert all(len(c["text"]) <= 60 for c in chunks)  # Allow some flexibility
    
    def test_overlap(self):
        """Test that chunks have overlap."""
        chunker = TextChunker(chunk_size=100, overlap=20)
        
        text = "Word " * 50
        chunks = chunker.chunk_text(text)
        
        if len(chunks) > 1:
            # Check that positions overlap
            assert chunks[1]["start"] < chunks[0]["end"]
