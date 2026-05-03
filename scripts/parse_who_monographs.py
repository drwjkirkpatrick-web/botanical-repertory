#!/usr/bin/env python3
"""
Parse WHO Monographs on Selected Medicinal Plants (Volumes 1-4)
and ingest into the Botanical Repertory SQLite database.

Extracts:
- Latin binomials
- Indications (with evidence levels)
- Contraindications
- Warnings / Precautions / Adverse reactions
"""

import re
import json
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class ParsedMonograph:
    title: str                          # e.g. "Bulbus Allii Cepae"
    latin_binomial: Optional[str] = None       # e.g. "Allium cepa L."
    plant_part: Optional[str] = None           # e.g. "bulbs"
    family: Optional[str] = None               # e.g. "Liliaceae"
    synonyms: List[str] = field(default_factory=list)
    vernacular_names: List[str] = field(default_factory=list)
    indications_clinical: List[str] = field(default_factory=list)
    indications_traditional: List[str] = field(default_factory=list)
    indications_folk: List[str] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    precautions: List[str] = field(default_factory=list)
    adverse_reactions: List[str] = field(default_factory=list)
    drug_interactions: List[str] = field(default_factory=list)
    posology: Optional[str] = None
    source_volume: int = 1


def extract_latin_binomial(definition_text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract latin binomial, plant part, and family from Definition section."""
    # Find the last "of Genus species" pattern — that's the actual plant name
    matches = list(re.finditer(
        r'\bof\s+([A-Z][a-z]+\s+[a-z]+(?:\s+(?:L\.|\(L\.\)\s+[A-Za-z]+\.?|J\.S\.\s+Presl\.|\(Fisch\.\)\s+Bunge|\(L\.\)\s+Rauschert|\(L\.\)\s+Urb\.))?)',
        definition_text
    ))
    latin = matches[-1].group(1) if matches else None
    
    # Find family
    fam_match = re.search(r'\(([A-Za-z]+aceae)\)', definition_text)
    family = fam_match.group(1) if fam_match else None
    
    return latin, None, family


def parse_monograph(text: str, volume: int) -> Optional[ParsedMonograph]:
    """Parse a single monograph text block."""
    # Normalize Unicode fi ligature
    text = text.replace('\ufb01', 'fi')
    
    lines = text.strip().split('\n')
    if not lines:
        return None
    
    title = lines[0].strip()
    if not title or len(title) < 3:
        return None
    
    mono = ParsedMonograph(title=title, source_volume=volume)
    
    # Extract Definition
    def_match = re.search(r'Definition\n(.*?)(?=\nSynonyms|\nDescription|\nMedicinal uses|\nPharmacology|\Z)',
                          text, re.DOTALL)
    if def_match:
        definition = def_match.group(1).strip()
        latin, part, family = extract_latin_binomial(definition)
        mono.latin_binomial = latin
        mono.plant_part = part
        mono.family = family
    
    # Extract Synonyms
    syn_match = re.search(r'Synonyms\n(.*?)(?=\nSelected vernacular names|\nDescription|\nMedicinal uses|\Z)',
                          text, re.DOTALL)
    if syn_match:
        syn_text = syn_match.group(1).strip()
        mono.synonyms = [s.strip() for s in re.split(r'[,;]|\(\d+\)', syn_text) if s.strip() and len(s.strip()) > 2]
    
    # Extract Vernacular names
    vern_match = re.search(r'Selected vernacular names\n(.*?)(?=\nDescription|\nMedicinal uses|\Z)',
                           text, re.DOTALL)
    if vern_match:
        vern_text = vern_match.group(1).strip()
        mono.vernacular_names = [v.strip() for v in re.split(r'[,;]', vern_text) if v.strip() and len(v.strip()) > 1]
    
    # Extract Medicinal uses
    med_match = re.search(r'Medicinal uses\n(.*?)(?=\nPharmacology|\nClinical pharmacology|\nContraindications|\nWarnings|\nPrecautions|\nAdverse reactions|\nPosology|\Z)',
                          text, re.DOTALL)
    if med_match:
        med_text = med_match.group(1).strip()
        
        # Clinical data
        clin_match = re.search(r'Uses supported by clinical data\s+(.*?)(?=Uses described in pharmacopoeias|Uses described in folk medicine|\nUses supported by clinical data|\Z)',
                               med_text, re.DOTALL)
        if clin_match:
            mono.indications_clinical = _split_indications(clin_match.group(1).strip())
        
        # Traditional
        trad_match = re.search(r'Uses described in pharmacopoeias and[\s\S]*?in traditional systems of[\s\S]*?medicine\s+(.*?)(?=Uses described in folk medicine|Uses supported by clinical data|\Z)',
                               med_text, re.DOTALL)
        if trad_match:
            mono.indications_traditional = _split_indications(trad_match.group(1).strip())
        
        # Folk
        folk_match = re.search(r'Uses described in folk medicine, not supported by[\s\S]*?clinical data\s+(.*?)(?=Uses described in pharmacopoeias|Uses supported by clinical data|\nClinical pharmacology|\Z)',
                               med_text, re.DOTALL)
        if folk_match:
            mono.indications_folk = _split_indications(folk_match.group(1).strip())
    
    # Extract Contraindications
    contr_match = re.search(r'Contraindications\n(.*?)(?=\nWarnings|\nPrecautions|\nAdverse reactions|\nPosology|\Z)',
                            text, re.DOTALL)
    if contr_match:
        mono.contraindications = _split_indications(contr_match.group(1).strip())
    
    # Extract Warnings
    warn_match = re.search(r'Warnings\n(.*?)(?=\nPrecautions|\nAdverse reactions|\nPosology|\Z)',
                           text, re.DOTALL)
    if warn_match:
        mono.warnings = _split_indications(warn_match.group(1).strip())
    
    # Extract Precautions (includes drug interactions)
    prec_match = re.search(r'Precautions\n(.*?)(?=\nAdverse reactions|\nPosology|\Z)',
                           text, re.DOTALL)
    if prec_match:
        prec_text = prec_match.group(1).strip()
        mono.precautions = _split_indications(prec_text)
        # Look for drug interactions within precautions
        if 'interaction' in prec_text.lower():
            lines = prec_text.split('\n')
            for line in lines:
                if 'interaction' in line.lower():
                    mono.drug_interactions.append(line.strip())
    
    # Extract Adverse reactions
    adv_match = re.search(r'Adverse reactions\n(.*?)(?=\nPosology|\Z)',
                          text, re.DOTALL)
    if adv_match:
        mono.adverse_reactions = _split_indications(adv_match.group(1).strip())
    
    # Extract Posology
    pos_match = re.search(r'Posology\n(.*?)(?=\Z)', text, re.DOTALL)
    if pos_match:
        mono.posology = pos_match.group(1).strip()[:500]  # Limit length
    
    return mono


def _split_indications(text: str) -> List[str]:
    """Split indication text into individual items."""
    text = re.sub(r'\(\d+[–\-]?\d*\)', '', text)  # Remove citations
    text = re.sub(r'\n+', ' ', text)  # Normalize newlines
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]


def split_volume_into_monographs(text: str) -> List[str]:
    """Split a volume text into individual monographs."""
    # Replace form feeds with newlines to normalize page breaks
    text = text.replace('\f', '\n')
    # Normalize Unicode fi ligature to regular "fi"
    text = text.replace('\ufb01', 'fi')
    
    # Find the start of first monograph
    intro_end = re.search(r'Introduction\n.*?\n\d+\n', text, re.DOTALL)
    if intro_end:
        text = text[intro_end.end():]
    
    # Split by monograph headers: title on its own line followed by Definition
    pattern = r'\n([A-Z][a-zA-Z\s]+(?:[A-Z][a-z]+)?)\n\nDefinition\n'
    matches = list(re.finditer(pattern, text))
    
    monographs = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        mono_text = text[start:end].strip()
        monographs.append(mono_text)
    
    return monographs


def ingest_monographs(db_path: str, docs_dir: Path):
    """Parse all WHO volumes and insert into database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {'botanicals': 0, 'indications': 0, 'edges': 0, 'contraindications': 0, 'drug_interactions': 0}
    
    for vol_file in sorted(docs_dir.glob("WHO_Vol*.txt")):
        volume = int(re.search(r'Vol(\d+)', vol_file.name).group(1))
        print(f"Processing {vol_file.name}...")
        
        text = vol_file.read_text()
        monographs = split_volume_into_monographs(text)
        print(f"  Found {len(monographs)} monographs")
        
        for mono_text in monographs:
            mono = parse_monograph(mono_text, volume)
            if not mono or not mono.latin_binomial:
                continue
            
            # Insert botanical
            cursor.execute('''
                INSERT OR IGNORE INTO botanicals 
                (latin_binomial, common_names, family, parts_used)
                VALUES (?, ?, ?, ?)
            ''', (
                mono.latin_binomial,
                ', '.join(mono.vernacular_names[:10]),
                mono.family,
                mono.title,
            ))
            cursor.execute('SELECT id FROM botanicals WHERE latin_binomial = ?', (mono.latin_binomial,))
            botanical_id = cursor.fetchone()[0]
            stats['botanicals'] += 1
            
            # Insert indications
            indication_map = [
                (mono.indications_clinical, 'clinical_trial'),
                (mono.indications_traditional, 'traditional'),
                (mono.indications_folk, 'ethnobotanical'),
            ]
            
            for indications, evidence_level in indication_map:
                for indication_text in indications:
                    cursor.execute('''
                        INSERT OR IGNORE INTO indications (indication_text, normalized_text, category)
                        VALUES (?, ?, ?)
                    ''', (indication_text, indication_text.lower().strip(), 'therapeutic'))
                    
                    cursor.execute('SELECT id FROM indications WHERE indication_text = ?', (indication_text,))
                    indication_id = cursor.fetchone()[0]
                    stats['indications'] += 1
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO indication_botanical_edges 
                        (botanical_id, indication_id, evidence_level, source_ref)
                        VALUES (?, ?, ?, ?)
                    ''', (botanical_id, indication_id, evidence_level, f'WHO Monographs Vol{volume}'))
                    stats['edges'] += 1
            
            # Insert contraindications
            for contraindication in mono.contraindications:
                cursor.execute('''
                    INSERT OR IGNORE INTO contraindications (botanical_id, contraindication, severity, source_ref)
                    VALUES (?, ?, ?, ?)
                ''', (botanical_id, contraindication, 'moderate', f'WHO Monographs Vol{volume}'))
                stats['contraindications'] += 1
            
            # Insert drug interactions
            for interaction in mono.drug_interactions:
                cursor.execute('''
                    INSERT OR IGNORE INTO drug_interactions (botanical_id, specific_drugs, mechanism, interaction_severity)
                    VALUES (?, ?, ?, ?)
                ''', (botanical_id, interaction, 'unknown', 'moderate'))
                stats['drug_interactions'] += 1
        
        conn.commit()
    
    conn.close()
    return stats


if __name__ == '__main__':
    db_path = '/home/walker/.hermes/projects/botanical_repertory/data/botanical.sqlite'
    docs_dir = Path('/home/walker/.hermes/projects/botanical_repertory/docs/who_monographs')
    
    stats = ingest_monographs(db_path, docs_dir)
    print(f"\n✅ Ingestion complete!")
    print(f"   Botanicals: {stats['botanicals']}")
    print(f"   Indications: {stats['indications']}")
    print(f"   Edges: {stats['edges']}")
    print(f"   Contraindications: {stats['contraindications']}")
    print(f"   Drug interactions: {stats['drug_interactions']}")
