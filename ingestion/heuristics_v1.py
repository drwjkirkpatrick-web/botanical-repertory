"""
Heuristics for extracting botanical information from text.

This module contains pattern matching and extraction rules for:
- Latin binomial identification
- Indication extraction and normalization
- Evidence level detection
- Category classification
- Safety signal detection
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Result of a heuristic extraction."""
    value: str
    confidence: float  # 0.0 - 1.0
    source: str  # Which pattern/heuristic matched
    context: Optional[str] = None


class LatinBinomialExtractor:
    """Extract Latin binomials (Genus species) from text."""
    
    # Pattern: Capitalized genus + lowercase species
    # Optional: var./subsp. + variety/subspecies
    PATTERNS = [
        # Standard binomial: "Hypericum perforatum"
        r'\b([A-Z][a-z]+\s+[a-z]+)\b',
        # With abbreviation: "H. perforatum" 
        r'\b([A-Z]\.\s+[a-z]+)\b',
        # With variety: "Hypericum perforatum var. angustifolium"
        r'\b([A-Z][a-z]+\s+[a-z]+(?:\s+(?:var\.|subsp\.)\s+[a-z]+))\b',
    ]
    
    # Common words that look like binomials but aren't
    FALSE_POSITIVES = {
        'et al', 'fig', 'see', 'use', 'the', 'and', 'for', 'this',
        'Table', 'Figure', 'Appendix', 'Section', 'Chapter',
        'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    }
    
    def extract(self, text: str) -> List[ExtractionResult]:
        """
        Extract all Latin binomials from text.
        
        Returns list of ExtractionResult with confidence scores.
        """
        results = []
        seen = set()
        
        for pattern in self.PATTERNS:
            for match in re.finditer(pattern, text):
                name = match.group(1)
                
                # Skip false positives
                if name in self.FALSE_POSITIVES:
                    continue
                
                # Skip if already seen
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                
                # Calculate confidence based on pattern specificity
                if 'var.' in name or 'subsp.' in name:
                    confidence = 0.95
                elif '.' in name.split()[0]:  # Abbreviated genus
                    confidence = 0.80
                else:
                    confidence = 0.90
                
                # Extract context (surrounding text)
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]
                
                results.append(ExtractionResult(
                    value=name,
                    confidence=confidence,
                    source='latin_binomial_pattern',
                    context=context
                ))
        
        return results
    
    def extract_primary(self, text: str) -> Optional[ExtractionResult]:
        """Extract the primary (most likely) binomial from text."""
        results = self.extract(text)
        if not results:
            return None
        
        # Return highest confidence result
        return max(results, key=lambda x: x.confidence)
    
    def normalize(self, binomial: str) -> str:
        """
        Normalize a binomial name.
        
        - Expands abbreviated genus if possible
        - Standardizes spacing
        - Lowercases species
        """
        parts = binomial.split()
        if len(parts) < 2:
            return binomial
        
        # Standard format: "Genus species"
        genus = parts[0].rstrip('.')
        species = parts[1].lower()
        
        # Handle variety/subspecies
        if len(parts) >= 4 and parts[2] in ('var.', 'subsp.'):
            return f"{genus} {species} {parts[2]} {parts[3].lower()}"
        
        return f"{genus} {species}"


class IndicationExtractor:
    """Extract and normalize indications (symptoms/uses) from text."""
    
    # Patterns that indicate an indication follows
    INDICATION_PATTERNS = [
        # "Used for..."
        r'(?:used|employed|utilized)\s+(?:for|in|to)\s+([^\.\n]+)',
        # "Indicated for..."
        r'indicated\s+(?:for|in)\s+([^\.\n]+)',
        # "Helpful for..."
        r'helpful\s+(?:for|in)\s+([^\.\n]+)',
        # "Treats..."
        r'treats?\s+([^\.\n]+)',
        # "Beneficial for..."
        r'beneficial\s+(?:for|in)\s+([^\.\n]+)',
        # "Traditional use: ..."
        r'traditional(?:ly)?\s+(?:use|used|employed)\s*:?\s*([^\.\n]+)',
    ]
    
    # Common indication starters (bullet points)
    BULLET_PATTERNS = [
        r'^[\s]*[-\*\+•‣]\s+(.+)$',
        r'^[\s]*\d+[\.\)]\s+(.+)$',
    ]
    
    # Normalization mappings
    NORMALIZATION_MAP = {
        # Sleep
        r'\b(insomnia|sleeplessness|difficulty\s+sleeping)\b': 'insomnia',
        r'\b(sedative|sleep\s+aid|promotes\s+sleep)\b': 'sedative',
        
        # Pain
        r'\b(headache|head\s+pain)\b': 'headache',
        r'\b(migraine|migraines)\b': 'migraine',
        r'\b(nerve\s+pain|neuralgia|neuropathic\s+pain)\b': 'nerve pain',
        r'\b(muscle\s+pain|myalgia|muscular\s+pain)\b': 'muscle pain',
        r'\b(joint\s+pain|arthralgia)\b': 'joint pain',
        r'\b(inflammation|inflammatory)\b': 'inflammation',
        
        # Mental/Emotional
        r'\b(anxiety|anxious|nervousness)\b': 'anxiety',
        r'\b(depression|depressed|low\s+mood)\b': 'depression',
        r'\b(stress|stressed)\b': 'stress',
        r'\b(irritability|irritable)\b': 'irritability',
        
        # Digestive
        r'\b(dyspepsia|indigestion|upset\s+stomach)\b': 'indigestion',
        r'\b(nausea|nauseated)\b': 'nausea',
        r'\b(constipation)\b': 'constipation',
        r'\b(diarrhea|loose\s+stools)\b': 'diarrhea',
        r'\b(bloating|flatulence|gas)\b': 'flatulence',
        r'\b(heartburn|reflux|gerd)\b': 'heartburn',
        r'\b(poor\s+appetite|anorexia)\b': 'anorexia',
        
        # Respiratory
        r'\b(cough|coughing)\b': 'cough',
        r'\b(congestion|congested)\b': 'congestion',
        r'\b(sore\s+throat|pharyngitis)\b': 'sore throat',
        r'\b(bronchitis)\b': 'bronchitis',
        r'\b(asthma)\b': 'asthma',
        
        # Cardiovascular
        r'\b(hypertension|high\s+blood\s+pressure)\b': 'hypertension',
        r'\b(poor\s+circulation)\b': 'poor circulation',
        
        # General
        r'\b(fatigue|tiredness|exhaustion)\b': 'fatigue',
        r'\b(weakness|debility)\b': 'weakness',
        r'\b(fever|febrile|pyrexia)\b': 'fever',
        r'\b(immune\s+support|boosts?\s+immunity)\b': 'immune support',
        
        # Skin
        r'\b(wound\s+healing|wounds)\b': 'wound healing',
        r'\b(skin\s+rashes?|dermatitis|eczema)\b': 'skin rash',
        r'\b(itching|pruritus)\b': 'itching',
    }
    
    def extract(self, text: str, context: str = "") -> List[ExtractionResult]:
        """Extract indications from text."""
        results = []
        seen = set()
        
        # Try pattern matching
        for pattern in self.INDICATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                indication = match.group(1).strip()
                indication = self._clean_indication(indication)
                
                if not indication or indication.lower() in seen:
                    continue
                seen.add(indication.lower())
                
                # Normalize
                normalized = self.normalize(indication)
                
                results.append(ExtractionResult(
                    value=normalized,
                    confidence=0.75,
                    source='indication_pattern',
                    context=context or indication
                ))
        
        return results
    
    def extract_from_bullets(self, text: str) -> List[ExtractionResult]:
        """Extract indications from bullet-pointed lists."""
        results = []
        seen = set()
        
        for pattern in self.BULLET_PATTERNS:
            for match in re.finditer(pattern, text, re.MULTILINE):
                indication = match.group(1).strip()
                indication = self._clean_indication(indication)
                
                if not indication or len(indication) < 5:
                    continue
                if indication.lower() in seen:
                    continue
                seen.add(indication.lower())
                
                normalized = self.normalize(indication)
                
                results.append(ExtractionResult(
                    value=normalized,
                    confidence=0.70,
                    source='bullet_pattern',
                    context=indication
                ))
        
        return results
    
    def normalize(self, indication: str) -> str:
        """Normalize an indication to standard terminology."""
        indication_lower = indication.lower()
        
        # Try pattern normalization
        for pattern, normalized in self.NORMALIZATION_MAP.items():
            if re.search(pattern, indication_lower):
                return normalized
        
        # Return cleaned original if no pattern matches
        return self._clean_indication(indication)
    
    def _clean_indication(self, text: str) -> str:
        """Clean up indication text."""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove leading bullets/numbers
        text = re.sub(r'^[-\*\+•‣\d\.)\]]+\s*', '', text)
        
        # Remove trailing punctuation
        text = text.rstrip('.;,')
        
        # Limit length
        if len(text) > 200:
            text = text[:200]
        
        return text.strip()
    
    def categorize(self, indication: str) -> Optional[str]:
        """Categorize an indication by body system."""
        indication_lower = indication.lower()
        
        categories = {
            'sleep': ['insomnia', 'sedative', 'sleep', 'somnolence'],
            'pain': ['pain', 'headache', 'migraine', 'neuralgia', 'myalgia', 'arthralgia'],
            'mental': ['anxiety', 'depression', 'stress', 'mood', 'nervous'],
            'digestive': ['digest', 'stomach', 'nausea', 'constipation', 'diarrhea', 'indigestion'],
            'respiratory': ['cough', 'cold', 'flu', 'bronchitis', 'asthma', 'congestion'],
            'cardiovascular': ['heart', 'blood pressure', 'circulation', 'hypertension'],
            'immune': ['immune', 'infection', 'antibacterial', 'antiviral', 'fever'],
            'skin': ['skin', 'wound', 'rash', 'eczema', 'acne', 'itch'],
            'urinary': ['urinary', 'kidney', 'bladder', 'diuretic'],
            'hormonal': ['hormone', 'menstrual', 'thyroid', 'menopause'],
        }
        
        for category, keywords in categories.items():
            if any(kw in indication_lower for kw in keywords):
                return category
        
        return None


class EvidenceLevelDetector:
    """Detect evidence level of botanical claims."""
    
    EVIDENCE_PATTERNS = {
        'systematic_review': [
            r'\b(systematic review|meta-analysis|metaanalysis)\b',
            r'\bCochrane review\b',
        ],
        'clinical_trial': [
            r'\b(randomized controlled trial|rct|clinical trial)\b',
            r'\bdouble-blind|placebo-controlled\b',
            r'\bin vivo\s+study\b',
        ],
        'clinical_observation': [
            r'\b(clinical observation|case series|case report)\b',
            r'\bpractitioner experience\b',
            r'\bclinical practice\b',
        ],
        'traditional': [
            r'\btraditional\s+(?:use|medicine|knowledge)\b',
            r'\b(TCM|Ayurveda|Traditional Chinese Medicine)\b',
            r'\bfolk medicine|ethnobotanical|historical use\b',
            r'\b(EC|Eclectic|physio-medical)\b',
        ],
        'in_vitro': [
            r'\bin vitro\b',
            r'\blaboratory study|cell culture\b',
            r'\bmechanism of action\b',
        ],
        'ethnobotanical': [
            r'\bethnobotanical|ethnopharmacological\b',
            r'\bindigenous use|native use\b',
        ],
    }
    
    def detect(self, text: str) -> Tuple[str, float]:
        """
        Detect evidence level from text context.
        
        Returns:
            Tuple of (evidence_level, confidence)
        """
        text_lower = text.lower()
        
        # Check each evidence level
        for level, patterns in self.EVIDENCE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return level, 0.85
        
        # Default to traditional if botanical context
        return 'traditional', 0.50
    
    def get_multiplier(self, evidence_level: str) -> float:
        """Get weight multiplier for evidence level."""
        multipliers = {
            'systematic_review': 3.0,
            'clinical_trial': 2.5,
            'clinical_observation': 2.0,
            'traditional': 1.0,
            'in_vitro': 0.8,
            'ethnobotanical': 0.7,
            'theoretical': 0.5,
        }
        return multipliers.get(evidence_level, 1.0)


class SafetySignalDetector:
    """Detect safety signals and contraindications in text."""
    
    CONTRAINDICATION_PATTERNS = [
        r'\bcontraindicated\s+(?:in|for)\s+([^\.\n]+)',
        r'\bshould\s+not\s+be\s+(?:used|taken)\s+(?:by|in)\s+([^\.\n]+)',
        r'\bavoid\s+(?:in|during)\s+([^\.\n]+)',
        r'\bnot\s+recommended\s+(?:for|in)\s+([^\.\n]+)',
    ]
    
    INTERACTION_PATTERNS = [
        r'\binteracts?\s+with\s+([^\.\n]+)',
        r'\bmay\s+(?:potentiate|interfere|interact)\s+([^\.\n]+)',
        r'\buse\s+caution\s+with\s+([^\.\n]+)',
    ]
    
    SEVERITY_KEYWORDS = {
        'absolute': ['absolute contraindication', 'never use', 'fatal', 'death'],
        'severe': ['severe', 'serious', 'dangerous', 'avoid', 'do not use'],
        'moderate': ['caution', 'careful', 'moderate', 'may cause'],
        'mild': ['mild', 'minor', 'slight', 'rare'],
    }
    
    def extract_contraindications(self, text: str) -> List[ExtractionResult]:
        """Extract contraindications from text."""
        results = []
        
        for pattern in self.CONTRAINDICATION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                contra = match.group(1).strip()
                severity = self._detect_severity(match.group(0) + ' ' + contra)
                
                results.append(ExtractionResult(
                    value=contra,
                    confidence=0.80,
                    source='contraindication_pattern',
                    context=f"severity:{severity}"
                ))
        
        return results
    
    def extract_interactions(self, text: str) -> List[ExtractionResult]:
        """Extract drug interactions from text."""
        results = []
        
        for pattern in self.INTERACTION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                interaction = match.group(1).strip()
                
                results.append(ExtractionResult(
                    value=interaction,
                    confidence=0.75,
                    source='interaction_pattern',
                    context=None
                ))
        
        return results
    
    def _detect_severity(self, text: str) -> str:
        """Detect severity level from text."""
        text_lower = text.lower()
        
        for severity, keywords in self.SEVERITY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                return severity
        
        return 'moderate'  # Default


class TextChunker:
    """Chunk text for vector indexing with overlap."""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str) -> List[Dict]:
        """
        Split text into overlapping chunks.
        
        Returns list of dicts with:
        - text: chunk content
        - start: start position in original
        - end: end position in original
        - index: chunk sequence number
        """
        chunks = []
        start = 0
        index = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending within 100 chars of target
                search_start = max(start + self.chunk_size - 100, start)
                match = re.search(r'[.!?]\s+', text[search_start:end+100])
                if match:
                    end = search_start + match.end()
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    'text': chunk_text,
                    'start': start,
                    'end': end,
                    'index': index
                })
                index += 1
            
            # Move start with overlap
            start = end - self.overlap
            if start >= end:
                break  # Prevent infinite loop
        
        return chunks


def main():
    """CLI for testing heuristics."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test extraction heuristics")
    parser.add_argument("text", help="Text to analyze")
    parser.add_argument("--type", choices=['binomial', 'indication', 'evidence', 'safety'],
                       default='indication', help="Extraction type")
    
    args = parser.parse_args()
    
    if args.type == 'binomial':
        extractor = LatinBinomialExtractor()
        results = extractor.extract(args.text)
    elif args.type == 'indication':
        extractor = IndicationExtractor()
        results = extractor.extract(args.text)
    elif args.type == 'evidence':
        detector = EvidenceLevelDetector()
        level, conf = detector.detect(args.text)
        print(f"Evidence: {level} (confidence: {conf})")
        return
    elif args.type == 'safety':
        detector = SafetySignalDetector()
        results = detector.extract_contraindications(args.text)
    
    for r in results:
        print(f"[{r.confidence:.2f}] {r.value}")
        if r.context:
            print(f"  Context: {r.context[:100]}...")


if __name__ == "__main__":
    main()