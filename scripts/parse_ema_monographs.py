#!/usr/bin/env python3
"""
Parse EMA HMPC herbal monograph PDFs into structured data for the botanical repertory.

EMA monographs use strict two-column tables (Well-established use | Traditional use).
This parser uses pdfplumber table extraction with position-aware section matching.
"""

import re
import sys
import json
import sqlite3
import pdfplumber
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class EMAMonograph:
    latin_name: str = ""
    common_names: List[str] = field(default_factory=list)
    parts_used: List[str] = field(default_factory=list)
    well_established_indications: List[str] = field(default_factory=list)
    traditional_indications: List[str] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    interactions: List[str] = field(default_factory=list)
    pregnancy_lactation: List[str] = field(default_factory=list)
    doc_ref: str = ""
    revision_date: str = ""
    source_url: str = ""

    def to_dict(self) -> Dict:
        return {
            "latin_name": self.latin_name,
            "common_names": self.common_names,
            "parts_used": self.parts_used,
            "well_established_indications": self.well_established_indications,
            "traditional_indications": self.traditional_indications,
            "contraindications": self.contraindications,
            "warnings": self.warnings,
            "interactions": self.interactions,
            "pregnancy_lactation": self.pregnancy_lactation,
            "doc_ref": self.doc_ref,
            "revision_date": self.revision_date,
            "source_url": self.source_url,
        }


def parse_latin_name(text: str) -> str:
    match = re.search(
        r'European Union herbal monograph on\s+(.+?)(?:\n|$)',
        text, re.IGNORECASE
    )
    if match:
        name = match.group(1).strip()
        name = re.sub(r'\s+Final\s*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+Initial assessment.*', '', name, flags=re.DOTALL)
        return name
    return ""


def parse_doc_ref(text: str) -> str:
    match = re.search(r'(EMA/HMPC/\d+/\d+(?:,\s*Corr\.\s*\d+)?)', text)
    if match:
        return match.group(1)
    return ""


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\f', ' ', text)
    return text.strip()


def split_indications(text: str) -> List[str]:
    if not text:
        return []
    text = re.sub(
        r'The product is a traditional herbal medicinal product for use in the specified indication exclusively based upon long-standing use\.',
        '', text, flags=re.IGNORECASE
    )
    text = clean_text(text)
    if not text or len(text) < 10:
        return []
    items = []
    for sentence in re.split(r'(?<=\.)\s+(?=[A-Z])', text):
        sentence = sentence.strip()
        if sentence and len(sentence) > 10:
            items.append(sentence)
    if not items:
        items.append(text)
    return items


def find_section_headers(page) -> Dict[str, float]:
    """Find section headers and their y-positions on a page."""
    words = page.extract_words()
    header_positions = {}
    
    j = 0
    while j < len(words):
        w = words[j]
        line_words = [w]
        line_top = w['top']
        
        k = j + 1
        while k < len(words) and abs(float(words[k]['top']) - float(line_top)) < 3:
            line_words.append(words[k])
            k += 1
        
        line_text = ' '.join([lw['text'] for lw in line_words])
        
        if re.match(r'4\.1\.\s*Therapeutic indications', line_text):
            header_positions["indications"] = float(line_top)
        elif re.match(r'4\.2\.\s*Posology', line_text):
            header_positions["posology"] = float(line_top)
        elif re.match(r'4\.3\.\s*Contraindications', line_text):
            header_positions["contraindications"] = float(line_top)
        elif re.match(r'4\.4\.\s*Special warnings', line_text):
            header_positions["warnings"] = float(line_top)
        elif re.match(r'4\.5\.\s*Interactions', line_text):
            header_positions["interactions"] = float(line_top)
        elif re.match(r'4\.6\.\s*Fertility, pregnancy', line_text):
            header_positions["pregnancy"] = float(line_top)
        elif re.match(r'4\.7\.\s*Effects on ability', line_text):
            header_positions["driving"] = float(line_top)
        
        j = k if k > j else j + 1
    
    return header_positions


def match_table_to_section(table, header_positions: Dict[str, float]) -> str:
    """Match a table to the section header immediately above it."""
    table_top = table.bbox[1]
    sorted_headers = sorted(header_positions.items(), key=lambda x: x[1])
    
    matched_section = None
    for section, header_y in sorted_headers:
        if table_top > header_y + 5:
            matched_section = section
    
    return matched_section


def parse_ema_monograph(pdf_path: str, source_url: str = "") -> EMAMonograph:
    monograph = EMAMonograph()
    monograph.source_url = source_url
    full_text = ""
    last_section = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            full_text += "\n" + page_text
            
            header_positions = find_section_headers(page)
            tables = page.find_tables()
            
            for table in tables:
                data = table.extract()
                if not data or len(data) < 2:
                    continue
                
                header = [clean_text(str(cell)) for cell in data[0]]
                if len(header) < 2 or "well-established" not in header[0].lower() or "traditional" not in header[1].lower():
                    continue
                
                section = match_table_to_section(table, header_positions)
                
                # Continuation table at top of page with no header match
                if section is None and table.bbox[1] < 100 and last_section:
                    section = last_section
                
                if section is None:
                    continue
                
                # Update last_section for continuation tracking
                last_section = section
                
                well_text = clean_text(data[1][0]) if len(data[1]) > 0 else ""
                trad_text = clean_text(data[1][1]) if len(data[1]) > 1 else ""
                
                if not well_text and not trad_text:
                    continue
                
                # Skip posology/driving sections - we only want indications and safety
                if section == "posology" or section == "driving":
                    continue
                
                if section == "indications":
                    monograph.well_established_indications.extend(split_indications(well_text))
                    monograph.traditional_indications.extend(split_indications(trad_text))
                elif section == "contraindications":
                    if well_text and len(well_text) > 5:
                        monograph.contraindications.append(well_text)
                    if trad_text and len(trad_text) > 5:
                        monograph.contraindications.append(trad_text)
                elif section == "warnings":
                    if well_text and len(well_text) > 10:
                        monograph.warnings.append(well_text)
                    if trad_text and len(trad_text) > 10:
                        monograph.warnings.append(trad_text)
                elif section == "interactions":
                    if well_text and len(well_text) > 10:
                        monograph.interactions.append(well_text)
                    if trad_text and len(trad_text) > 10:
                        monograph.interactions.append(trad_text)
                elif section == "pregnancy":
                    if well_text and len(well_text) > 10:
                        monograph.pregnancy_lactation.append(well_text)
                    if trad_text and len(trad_text) > 10:
                        monograph.pregnancy_lactation.append(trad_text)
    
    monograph.latin_name = parse_latin_name(full_text)
    monograph.doc_ref = parse_doc_ref(full_text)
    
    # Extract common names from keywords
    kw_match = re.search(r'Keywords\s*(.*?)(?=\n\s*\n|\f)', full_text, re.DOTALL)
    if kw_match:
        kw_text = kw_match.group(1)
        names_match = re.search(re.escape(monograph.latin_name) + r'.*?;\s*([^;\n]+)', kw_text)
        if names_match:
            monograph.common_names = [n.strip() for n in names_match.group(1).split(',') if n.strip()]
    
    # Extract revision date
    date_match = re.search(r'Adoption by HMPC\s*\n\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', full_text)
    if date_match:
        monograph.revision_date = date_match.group(1)
    
    # Deduplicate
    monograph.well_established_indications = list(dict.fromkeys(monograph.well_established_indications))
    monograph.traditional_indications = list(dict.fromkeys(monograph.traditional_indications))
    monograph.contraindications = list(dict.fromkeys(monograph.contraindications))
    monograph.warnings = list(dict.fromkeys(monograph.warnings))
    monograph.interactions = list(dict.fromkeys(monograph.interactions))
    monograph.pregnancy_lactation = list(dict.fromkeys(monograph.pregnancy_lactation))
    
    return monograph


def insert_into_database(monograph: EMAMonograph, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert botanical
    cursor.execute('''
        INSERT OR IGNORE INTO botanicals (latin_binomial, common_names, parts_used)
        VALUES (?, ?, ?)
    ''', (monograph.latin_name, json.dumps(monograph.common_names), json.dumps(monograph.parts_used)))
    
    cursor.execute('SELECT id FROM botanicals WHERE latin_binomial = ?', (monograph.latin_name,))
    botanical_id = cursor.fetchone()[0]
    
    # Insert well-established indications
    for indication_text in monograph.well_established_indications:
        cursor.execute('''
            INSERT OR IGNORE INTO indications (indication_text, normalized_text, category)
            VALUES (?, ?, ?)
        ''', (indication_text, indication_text.lower().strip(), 'therapeutic'))
        
        cursor.execute('SELECT id FROM indications WHERE indication_text = ?', (indication_text,))
        indication_id = cursor.fetchone()[0]
        
        cursor.execute('''
            INSERT OR IGNORE INTO indication_botanical_edges 
            (botanical_id, indication_id, evidence_level, source_ref)
            VALUES (?, ?, ?, ?)
        ''', (botanical_id, indication_id, 'clinical_trial', f"EMA HMPC {monograph.doc_ref}"))
    
    # Insert traditional indications
    for indication_text in monograph.traditional_indications:
        cursor.execute('''
            INSERT OR IGNORE INTO indications (indication_text, normalized_text, category)
            VALUES (?, ?, ?)
        ''', (indication_text, indication_text.lower().strip(), 'therapeutic'))
        
        cursor.execute('SELECT id FROM indications WHERE indication_text = ?', (indication_text,))
        indication_id = cursor.fetchone()[0]
        
        cursor.execute('''
            INSERT OR IGNORE INTO indication_botanical_edges 
            (botanical_id, indication_id, evidence_level, source_ref)
            VALUES (?, ?, ?, ?)
        ''', (botanical_id, indication_id, 'traditional', f"EMA HMPC {monograph.doc_ref}"))
    
    # Insert contraindications
    for contra_text in monograph.contraindications:
        cursor.execute('''
            INSERT OR IGNORE INTO contraindications (botanical_id, contraindication, severity, source_ref)
            VALUES (?, ?, ?, ?)
        ''', (botanical_id, contra_text, 'moderate', f"EMA HMPC {monograph.doc_ref}"))
    
    conn.commit()
    conn.close()
    
    print(f"Inserted: {monograph.latin_name}")
    print(f"  Well-established: {len(monograph.well_established_indications)}")
    print(f"  Traditional: {len(monograph.traditional_indications)}")
    print(f"  Contraindications: {len(monograph.contraindications)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_ema_monographs.py <pdf_path> [db_path]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else "data/botanical.sqlite"
    
    monograph = parse_ema_monograph(pdf_path)
    print(json.dumps(monograph.to_dict(), indent=2))
    
    if len(sys.argv) > 2:
        insert_into_database(monograph, db_path)
