"""
Document parsers for botanical medicine texts.

Supports:
- Markdown (.md) - structured documents with headings
- Plain text (.txt) - unstructured text
- PDF (.pdf) - via external tools (optional)

Extracts:
- Latin binomials ("Genus species")
- Indications from structured sections
- Preparation methods
- Safety information
"""

import re
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Iterator
from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """Result of parsing a document."""
    filename: str
    doc_type: str  # 'markdown', 'text', 'pdf'
    title: str = ""
    botanicals: List[Dict] = field(default_factory=list)
    indications: List[Dict] = field(default_factory=list)
    safety_info: List[Dict] = field(default_factory=list)
    raw_text: str = ""
    sections: Dict[str, str] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract base class for document parsers."""
    
    @abstractmethod
    def parse(self, filepath: Path) -> ParsedDocument:
        """Parse a document and return structured data."""
        pass
    
    @abstractmethod
    def can_parse(self, filepath: Path) -> bool:
        """Check if this parser can handle the file."""
        pass


class MarkdownParser(BaseParser):
    """
    Parser for markdown botanical monographs.
    
    Expects structure like:
    # Botanical Name (Latin Binomial)
    
    ## Indications
    - Symptom 1
    - Symptom 2
    
    ## Contraindications
    - Pregnancy
    
    ## Preparations
    - Tincture
    """
    
    # Latin binomial pattern: Genus species (optional var. variety)
    LATIN_BINOMIAL_RE = re.compile(
        r'\b([A-Z][a-z]+\s+[a-z]+(?:\s+var\.\s+[a-z]+)?)\b'
    )
    
    # Section headers we're interested in
    INDICATION_HEADERS = [
        'indications', 'uses', 'actions', 'therapeutic uses',
        'clinical uses', 'traditional uses'
    ]
    
    CONTRAINDICATION_HEADERS = [
        'contraindications', 'contra-indications', 'precautions',
        'safety', 'warnings', 'cautions'
    ]
    
    PREPARATION_HEADERS = [
        'preparations', 'preparation', 'dosage', 'dosing',
        'administration', 'forms'
    ]
    
    def can_parse(self, filepath: Path) -> bool:
        return filepath.suffix.lower() in ['.md', '.markdown']
    
    def parse(self, filepath: Path) -> ParsedDocument:
        """Parse a markdown file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = ParsedDocument(
            filename=filepath.name,
            doc_type='markdown',
            raw_text=content
        )
        
        # Extract title (first h1)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            result.title = title_match.group(1).strip()
        
        # Find Latin binomials
        result.botanicals = self._extract_botanicals(content)
        
        # Parse sections
        sections = self._split_sections(content)
        result.sections = sections
        
        # Extract indications
        result.indications = self._extract_indications(sections)
        
        # Extract safety info
        result.safety_info = self._extract_safety(sections)
        
        return result
    
    def _extract_botanicals(self, content: str) -> List[Dict]:
        """Extract Latin binomials from text."""
        botanicals = []
        seen = set()
        
        for match in self.LATIN_BINOMIAL_RE.finditer(content):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                parts = name.split()
                botanicals.append({
                    'latin_binomial': name,
                    'genus': parts[0] if len(parts) > 0 else '',
                    'species': parts[1] if len(parts) > 1 else '',
                    'variety': parts[3] if len(parts) > 3 else None
                })
        
        return botanicals
    
    def _split_sections(self, content: str) -> Dict[str, str]:
        """Split markdown into sections by heading."""
        sections = {}
        current_section = '_header'
        current_content = []
        
        for line in content.split('\n'):
            # Check for heading
            if line.startswith('#'):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Extract section name
                level = len(line) - len(line.lstrip('#'))
                section_name = line.lstrip('#').strip().lower()
                current_section = section_name
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def _extract_indications(self, sections: Dict[str, str]) -> List[Dict]:
        """Extract indications from indication sections."""
        indications = []
        
        for section_name, content in sections.items():
            # Check if this is an indications section
            is_indication_section = any(
                h in section_name for h in self.INDICATION_HEADERS
            )
            
            if is_indication_section:
                # Extract bullet points
                for line in content.split('\n'):
                    line = line.strip()
                    # Match bullet points
                    if line.startswith(('-', '*', '+')) or re.match(r'^\d+\.', line):
                        indication = line.lstrip('-*+0123456789. ').strip()
                        if len(indication) > 3:
                            indications.append({
                                'text': indication,
                                'source_section': section_name,
                                'category': self._categorize_indication(indication)
                            })
        
        return indications
    
    def _extract_safety(self, sections: Dict[str, str]) -> List[Dict]:
        """Extract safety information."""
        safety_info = []
        
        for section_name, content in sections.items():
            is_safety_section = any(
                h in section_name for h in self.CONTRAINDICATION_HEADERS
            )
            
            if is_safety_section:
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith(('-', '*', '+')):
                        info = line.lstrip('-*+ ').strip()
                        if len(info) > 3:
                            # Try to determine severity
                            severity = self._detect_severity(info)
                            safety_info.append({
                                'type': 'contraindication',
                                'description': info,
                                'severity': severity
                            })
        
        return safety_info
    
    def _categorize_indication(self, text: str) -> Optional[str]:
        """Categorize an indication by body system."""
        text_lower = text.lower()
        
        categories = {
            'pain': ['pain', 'ache', 'headache', 'migraine', 'neuralgia'],
            'digestive': ['digest', 'stomach', 'nausea', 'constipation', 'diarrhea'],
            'respiratory': ['cough', 'cold', 'flu', 'breath', 'lung', 'sinus'],
            'sleep': ['sleep', 'insomnia', 'sedative', 'calm'],
            'mental': ['anxiety', 'depression', 'stress', 'mood', 'nervous'],
            'skin': ['skin', 'rash', 'wound', 'eczema', 'acne'],
            'immune': ['immune', 'infection', 'antibacterial', 'antiviral'],
            'cardiovascular': ['heart', 'blood pressure', 'circulation'],
            'hormonal': ['hormone', 'menstrual', 'thyroid', 'adrenal'],
            'urinary': ['urinary', 'kidney', 'bladder', 'diuretic'],
        }
        
        for category, keywords in categories.items():
            if any(kw in text_lower for kw in keywords):
                return category
        
        return None
    
    def _detect_severity(self, text: str) -> str:
        """Detect severity level from contraindication text."""
        text_lower = text.lower()
        
        if any(w in text_lower for w in ['absolute', 'never', 'fatal', 'death']):
            return 'absolute'
        elif any(w in text_lower for w in ['severe', 'serious', 'dangerous', 'avoid']):
            return 'severe'
        elif any(w in text_lower for w in ['moderate', 'caution', 'careful']):
            return 'moderate'
        else:
            return 'mild'


class TextParser(BaseParser):
    """
    Parser for plain text files.
    
    Uses heuristics to find structure in unstructured text.
    """
    
    LATIN_BINOMIAL_RE = re.compile(
        r'\b([A-Z][a-z]+\s+[a-z]+(?:\s+var\.\s+[a-z]+)?)\b'
    )
    
    def can_parse(self, filepath: Path) -> bool:
        return filepath.suffix.lower() == '.txt'
    
    def parse(self, filepath: Path) -> ParsedDocument:
        """Parse a plain text file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = ParsedDocument(
            filename=filepath.name,
            doc_type='text',
            raw_text=content
        )
        
        # Try to extract title (first line or first sentence)
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        if lines:
            result.title = lines[0][:100]
        
        # Extract botanicals
        result.botanicals = self._extract_botanicals(content)
        
        # Extract indications (lines with keywords)
        result.indications = self._extract_indications_heuristic(content)
        
        return result
    
    def _extract_botanicals(self, content: str) -> List[Dict]:
        """Extract Latin binomials."""
        botanicals = []
        seen = set()
        
        for match in self.LATIN_BINOMIAL_RE.finditer(content):
            name = match.group(1)
            if name not in seen:
                seen.add(name)
                parts = name.split()
                botanicals.append({
                    'latin_binomial': name,
                    'genus': parts[0],
                    'species': parts[1],
                    'variety': parts[3] if len(parts) > 3 else None
                })
        
        return botanicals
    
    def _extract_indications_heuristic(self, content: str) -> List[Dict]:
        """Extract potential indications using heuristics."""
        indications = []
        
        # Keywords that suggest a line contains an indication
        indication_markers = [
            'used for', 'indicated', 'treats', 'helpful for',
            'beneficial', 'traditional use', 'employed'
        ]
        
        for line in content.split('\n'):
            line_lower = line.lower()
            
            if any(marker in line_lower for marker in indication_markers):
                # Clean up the line
                indication = line.strip()
                # Remove common prefixes
                for prefix in ['-', '*', '•', '‣']:
                    if indication.startswith(prefix):
                        indication = indication[1:].strip()
                
                if len(indication) > 10 and len(indication) < 200:
                    indications.append({
                        'text': indication,
                        'source_section': 'heuristic_extraction',
                        'category': None
                    })
        
        return indications


class DocumentParser:
    """
    Unified document parser that dispatches to appropriate parser.
    """
    
    def __init__(self):
        self.parsers = [
            MarkdownParser(),
            TextParser(),
        ]
    
    def parse(self, filepath: str | Path) -> ParsedDocument:
        """
        Parse a document using the appropriate parser.
        
        Args:
            filepath: Path to document
        
        Returns:
            ParsedDocument with extracted data
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        for parser in self.parsers:
            if parser.can_parse(filepath):
                return parser.parse(filepath)
        
        raise ValueError(f"No parser available for file type: {filepath.suffix}")
    
    def parse_directory(
        self,
        directory: str | Path,
        extensions: Optional[List[str]] = None
    ) -> Iterator[ParsedDocument]:
        """
        Parse all documents in a directory.
        
        Args:
            directory: Directory to scan
            extensions: File extensions to include (default: .md, .txt)
        
        Yields:
            ParsedDocument for each file
        """
        directory = Path(directory)
        
        if extensions is None:
            extensions = ['.md', '.txt']
        
        for ext in extensions:
            for filepath in directory.glob(f"*{ext}"):
                try:
                    yield self.parse(filepath)
                except Exception as e:
                    print(f"Error parsing {filepath}: {e}")


def main():
    """CLI for testing document parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Parse botanical documents")
    parser.add_argument("file", help="Document to parse")
    parser.add_argument("--output", "-o", help="Output JSON file")
    
    args = parser.parse_args()
    
    doc_parser = DocumentParser()
    result = doc_parser.parse(args.file)
    
    # Convert to dict for JSON serialization
    output = {
        "filename": result.filename,
        "doc_type": result.doc_type,
        "title": result.title,
        "botanicals_found": len(result.botanicals),
        "botanicals": result.botanicals,
        "indications_found": len(result.indications),
        "indications": result.indications[:10],  # Limit output
        "safety_info": result.safety_info,
        "sections": list(result.sections.keys()) if result.sections else []
    }
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Saved to {args.output}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()