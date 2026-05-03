"""
Data models for Botanical Medicine Repertory
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class Botanical:
    """Represents a botanical remedy (herb, plant)."""
    id: Optional[int] = None
    latin_binomial: str = ""
    common_names: List[str] = field(default_factory=list)
    family: str = ""
    genus: str = ""
    species: str = ""
    parts_used: List[str] = field(default_factory=list)
    energetics: Dict[str, str] = field(default_factory=dict)
    traditional_systems: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def short_name(self) -> str:
        """Return abbreviated Latin name (e.g., 'H. perforatum')."""
        parts = self.latin_binomial.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}. {parts[1]}"
        return self.latin_binomial
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "latin_binomial": self.latin_binomial,
            "short_name": self.short_name,
            "common_names": self.common_names,
            "family": self.family,
            "genus": self.genus,
            "species": self.species,
            "parts_used": self.parts_used,
            "energetics": self.energetics,
            "traditional_systems": self.traditional_systems,
        }


@dataclass
class Indication:
    """Represents a symptom, condition, or use case (like a homeopathic rubric)."""
    id: Optional[int] = None
    indication_text: str = ""
    normalized_text: str = ""
    category: Optional[str] = None
    subcategory: Optional[str] = None
    body_system: Optional[str] = None
    botanicals: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "indication_text": self.indication_text,
            "normalized_text": self.normalized_text,
            "category": self.category,
            "subcategory": self.subcategory,
            "body_system": self.body_system,
            "botanical_count": len(self.botanicals),
        }


@dataclass
class BotanicalIndicationLink:
    """Links a botanical to an indication with evidence and weighting."""
    id: Optional[int] = None
    indication_id: int = 0
    botanical_id: int = 0
    botanical: Optional[Botanical] = None
    indication: Optional[Indication] = None
    weight: float = 1.0
    evidence_level: str = "traditional"
    source_ref: str = ""
    preparation: str = ""
    dosage_notes: str = ""
    
    @property
    def evidence_score(self) -> float:
        """Calculate evidence multiplier based on evidence level."""
        evidence_multipliers = {
            "systematic_review": 3.0,
            "clinical_trial": 2.5,
            "clinical_observation": 2.0,
            "traditional": 1.0,
            "in_vitro": 0.8,
            "ethnobotanical": 0.7,
            "theoretical": 0.5,
        }
        return evidence_multipliers.get(self.evidence_level, 1.0)
    
    @property
    def total_score(self) -> float:
        """Calculate total weighted score."""
        return self.weight * self.evidence_score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "indication_id": self.indication_id,
            "botanical_id": self.botanical_id,
            "botanical": self.botanical.to_dict() if self.botanical else None,
            "weight": self.weight,
            "evidence_level": self.evidence_level,
            "evidence_score": self.evidence_score,
            "total_score": self.total_score,
            "source_ref": self.source_ref,
            "preparation": self.preparation,
            "dosage_notes": self.dosage_notes,
        }


@dataclass
class Contraindication:
    """Safety contraindication for a botanical."""
    id: Optional[int] = None
    botanical_id: int = 0
    contraindication: str = ""
    severity: str = "moderate"  # mild, moderate, severe, absolute
    population: str = "all"  # pregnancy, children, elderly, all
    mechanism: str = ""
    source_ref: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contraindication": self.contraindication,
            "severity": self.severity,
            "population": self.population,
            "mechanism": self.mechanism,
        }


@dataclass
class DrugInteraction:
    """Drug interaction warning for a botanical."""
    id: Optional[int] = None
    botanical_id: int = 0
    drug_class: str = ""
    specific_drugs: List[str] = field(default_factory=list)
    interaction_severity: str = "moderate"
    mechanism: str = ""
    recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "drug_class": self.drug_class,
            "specific_drugs": self.specific_drugs,
            "severity": self.interaction_severity,
            "mechanism": self.mechanism,
            "recommendation": self.recommendation,
        }


@dataclass
class SafetyProfile:
    """Complete safety information for a botanical."""
    botanical: Botanical
    contraindications: List[Contraindication] = field(default_factory=list)
    drug_interactions: List[DrugInteraction] = field(default_factory=list)
    
    @property
    def has_critical_warnings(self) -> bool:
        """Check if any absolute contraindications or severe interactions."""
        has_absolute = any(
            c.severity == "absolute" for c in self.contraindications
        )
        has_severe = any(
            i.interaction_severity == "severe" for i in self.drug_interactions
        )
        return has_absolute or has_severe
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "botanical": self.botanical.to_dict(),
            "contraindications": [c.to_dict() for c in self.contraindications],
            "drug_interactions": [i.to_dict() for i in self.drug_interactions],
            "has_critical_warnings": self.has_critical_warnings,
        }


@dataclass
class SearchResult:
    """Result from searching indications or botanicals."""
    item: Any  # Botanical or Indication
    score: float
    match_type: str  # 'exact', 'prefix', 'fuzzy', 'vector'
    matched_text: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "item": self.item.to_dict() if hasattr(self.item, 'to_dict') else self.item,
            "score": self.score,
            "match_type": self.match_type,
            "matched_text": self.matched_text,
        }


@dataclass
class RepertorizationResult:
    """Result from multi-symptom repertorization."""
    botanical: Botanical
    total_score: float
    matches: List[Dict[str, Any]] = field(default_factory=list)
    safety_profile: Optional[SafetyProfile] = None
    rank: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "botanical": self.botanical.to_dict(),
            "total_score": self.total_score,
            "matches": self.matches,
            "safety_profile": self.safety_profile.to_dict() if self.safety_profile else None,
        }


@dataclass
class Document:
    """Source document for corpus-based extraction."""
    id: Optional[int] = None
    filename: str = ""
    filepath: str = ""
    content: str = ""
    source: str = ""
    doc_type: str = ""
    author: str = ""
    year: Optional[int] = None
    ingested_at: Optional[datetime] = None
    processed: bool = False


@dataclass
class Chunk:
    """Text chunk from a document."""
    id: Optional[int] = None
    doc_id: int = 0
    chunk_text: str = ""
    start_pos: int = 0
    end_pos: int = 0
    chunk_index: int = 0
    has_indications: bool = False
    vector: Optional[List[float]] = None