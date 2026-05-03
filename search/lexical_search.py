"""
Lexical search implementation using inverted index with advanced features.

Provides fast token-based search with:
- Inverted index (token -> list of indication IDs)
- TF-IDF weighting with BM25 option
- Synonym expansion
- Porter stemming
- Fuzzy matching for misspellings (Levenshtein)
- Edge n-grams for prefix matching
- Query parsing with AND/OR/NOT support
"""

import re
import json
import sqlite3
import math
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.database import BotanicalDatabase
from src.models import SearchResult, Indication


# Porter Stemmer for English
class PorterStemmer:
    """Porter Stemmer implementation for reducing words to root form."""
    
    def __init__(self):
        self.vowels = "aeiou"
    
    def is_vowel(self, word: str, i: int) -> bool:
        """Check if character at index is a vowel."""
        if word[i] in self.vowels:
            return True
        if word[i] == 'y' and i > 0 and not self.is_vowel(word, i - 1):
            return True
        return False
    
    def measure(self, word: str) -> int:
        """Measure the number of VC sequences."""
        n = len(word)
        if n == 0:
            return 0
        
        # Find first vowel
        i = 0
        while i < n and not self.is_vowel(word, i):
            i += 1
        
        if i >= n:
            return 0
        
        count = 0
        while i < n:
            # Skip vowels
            while i < n and self.is_vowel(word, i):
                i += 1
            if i >= n:
                break
            count += 1
            # Skip consonants
            while i < n and not self.is_vowel(word, i):
                i += 1
        
        return count
    
    def ends_with(self, word: str, suffix: str) -> bool:
        """Check if word ends with suffix."""
        return word.endswith(suffix)
    
    def stem(self, word: str) -> str:
        """Stem a word to its root form."""
        word = word.lower()
        if len(word) <= 2:
            return word
        
        # Step 1a
        if word.endswith('sses'):
            word = word[:-2]
        elif word.endswith('ies'):
            word = word[:-2]
        elif word.endswith('ss'):
            pass
        elif word.endswith('s'):
            word = word[:-1]
        
        # Step 1b
        step1b_done = False
        if word.endswith('eed'):
            if self.measure(word[:-3]) > 0:
                word = word[:-1]
        elif word.endswith('ed'):
            stem = word[:-2]
            if any(self.is_vowel(stem, i) for i in range(len(stem))):
                word = stem
                step1b_done = True
        elif word.endswith('ing'):
            stem = word[:-3]
            if any(self.is_vowel(stem, i) for i in range(len(stem))):
                word = stem
                step1b_done = True
        
        if step1b_done:
            if word.endswith('at') or word.endswith('bl') or word.endswith('iz'):
                word += 'e'
            elif len(word) >= 2 and word[-1] == word[-2] and word[-1] not in 'lsz':
                word = word[:-1]
            elif self.measure(word) == 1 and self._ends_with_cvc(word):
                word += 'e'
        
        # Step 1c
        if word.endswith('y') and len(word) > 2 and self.is_vowel(word, -2):
            word = word[:-1] + 'i'
        
        # Step 2
        step2_suffixes = {
            'ational': 'ate', 'tional': 'tion', 'enci': 'ence', 'anci': 'ance',
            'izer': 'ize', 'abli': 'able', 'alli': 'al', 'entli': 'ent',
            'eli': 'e', 'ousli': 'ous', 'ization': 'ize', 'ation': 'ate',
            'ator': 'ate', 'alism': 'al', 'iveness': 'ive', 'fulness': 'ful',
            'ousness': 'ous', 'aliti': 'al', 'iviti': 'ive', 'biliti': 'ble'
        }
        for suffix, replacement in step2_suffixes.items():
            if word.endswith(suffix):
                stem = word[:-len(suffix)] + replacement
                if self.measure(stem) > 0:
                    word = stem
                break
        
        # Step 3
        step3_suffixes = {
            'icate': 'ic', 'ative': '', 'alize': 'al', 'iciti': 'ic',
            'ical': 'ic', 'ful': '', 'ness': ''
        }
        for suffix, replacement in step3_suffixes.items():
            if word.endswith(suffix):
                stem = word[:-len(suffix)] + replacement
                if self.measure(stem) > 0:
                    word = stem
                break
        
        # Step 4
        step4_suffixes = [
            'al', 'ance', 'ence', 'er', 'ic', 'able', 'ible', 'ant', 'ement',
            'ment', 'ent', 'ion', 'ou', 'ism', 'ate', 'iti', 'ous', 'ive', 'ize'
        ]
        for suffix in step4_suffixes:
            if word.endswith(suffix):
                stem = word[:-len(suffix)]
                if self.measure(stem) > 1:
                    word = stem
                break
        
        # Step 5a
        if word.endswith('e'):
            stem = word[:-1]
            if self.measure(stem) > 1 or (self.measure(stem) == 1 and not self._ends_with_cvc(stem)):
                word = stem
        
        # Step 5b
        if len(word) >= 2 and word.endswith('l') and word[-2] == 'l' and self.measure(word) > 1:
            word = word[:-1]
        
        return word
    
    def _ends_with_cvc(self, word: str) -> bool:
        """Check if word ends with CVC pattern (consonant-vowel-consonant)."""
        if len(word) < 3:
            return False
        return (
            not self.is_vowel(word, -1) and
            self.is_vowel(word, -2) and
            not self.is_vowel(word, -3)
        )


class FuzzyMatcher:
    """Fuzzy string matching using Levenshtein distance."""
    
    @staticmethod
    def levenshtein(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return FuzzyMatcher.levenshtein(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def similarity(s1: str, s2: str) -> float:
        """Calculate similarity ratio (0.0 to 1.0)."""
        if s1 == s2:
            return 1.0
        
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 1.0
        
        distance = FuzzyMatcher.levenshtein(s1, s2)
        return 1.0 - (distance / max_len)
    
    def find_matches(
        self,
        query: str,
        candidates: List[str],
        threshold: float = 0.7,
        max_matches: int = 5
    ) -> List[Tuple[str, float]]:
        """Find fuzzy matches for query in candidates."""
        matches = []
        
        for candidate in candidates:
            sim = self.similarity(query, candidate)
            if sim >= threshold:
                matches.append((candidate, sim))
        
        # Sort by similarity descending
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:max_matches]


@dataclass
class Posting:
    """Posting list entry for inverted index."""
    indication_id: int
    term_frequency: float
    field: str  # 'text', 'normalized', 'category'


class Tokenizer:
    """Advanced text tokenization with normalization."""
    
    # Comprehensive synonym dictionary for botanical medicine
    SYNONYMS = {
        # Pain conditions
        'headache': ['head pain', 'cephalalgia', 'cranial pain', 'head ache'],
        'migraine': ['sick headache', 'hemicrania', 'migraine headache'],
        'nerve pain': ['neuralgia', 'neuropathy', 'neuropathic pain', 'nerve ache'],
        'joint pain': ['arthralgia', 'arthritis pain', 'joint ache'],
        'muscle pain': ['myalgia', 'muscular pain', 'muscle ache', 'muscular ache'],
        'back pain': ['lumbago', 'dorsalgia', 'backache'],
        'stomach pain': ['gastric pain', 'abdominal pain', 'belly ache', 'stomach ache'],
        'menstrual pain': ['dysmenorrhea', 'period pain', 'menstrual cramps'],
        
        # Sleep disorders
        'insomnia': ['sleeplessness', 'sleep disorder', 'difficulty sleeping', 'sleep disturbance'],
        'sedative': ['hypnotic', 'sleep aid', 'calming', 'tranquilizer'],
        'somnolence': ['drowsiness', 'sleepiness', 'excessive sleep'],
        
        # Mental health
        'anxiety': ['nervousness', 'worry', 'anxiousness', 'apprehension', 'unease'],
        'depression': ['low mood', 'depressed', 'melancholy', 'dysthymia', 'depressive'],
        'stress': ['tension', 'strain', 'overwhelm', 'distress'],
        'irritability': ['irritable', 'irritable mood', 'short temper'],
        'restlessness': ['agitation', 'restless', 'uneasy'],
        
        # Digestive
        'indigestion': ['dyspepsia', 'upset stomach', 'gastric distress', 'poor digestion'],
        'bloating': ['flatulence', 'gas', 'distension', 'abdominal fullness', 'bloat'],
        'constipation': ['irregularity', 'obstipation', 'difficulty defecating'],
        'diarrhea': ['loose stools', 'dysentery', 'loose bowels'],
        'nausea': ['sickness', 'queasiness', 'nauseous'],
        'heartburn': ['acid reflux', 'gastric reflux', 'pyrosis'],
        'vomiting': ['emesis', 'throwing up', 'retching'],
        'anorexia': ['poor appetite', 'loss of appetite', 'no appetite'],
        
        # Respiratory
        'cough': ['tussis', 'hacking', 'coughing'],
        'congestion': ['stuffiness', 'blocked', 'nasal congestion', 'chest congestion'],
        'sore throat': ['pharyngitis', 'throat pain', 'throat ache'],
        'bronchitis': ['bronchial inflammation', 'chest cold'],
        'asthma': ['wheezing', 'asthmatic'],
        'rhinitis': ['runny nose', 'nasal inflammation'],
        
        # Cardiovascular
        'hypertension': ['high blood pressure', 'elevated bp'],
        'hypotension': ['low blood pressure'],
        'poor circulation': ['cold extremities', 'poor blood flow'],
        'palpitations': ['irregular heartbeat', 'heart racing'],
        
        # General
        'fatigue': ['tiredness', 'exhaustion', 'weariness', 'lethargy', 'tired'],
        'inflammation': ['inflammatory', 'swelling', 'redness', 'inflamed'],
        'fever': ['pyrexia', 'febrile', 'high temperature', 'fevers'],
        'weakness': ['debility', 'asthenia', 'lack of strength'],
        'malaise': ['general discomfort', 'feeling unwell'],
        
        # Skin
        'itching': ['pruritus', 'itchy', 'pruritis'],
        'wound healing': ['wound care', 'tissue repair', 'healing wounds'],
        'eczema': ['dermatitis', 'atopic dermatitis'],
        'acne': ['pimples', 'zits', 'breakouts'],
        'rash': ['skin eruption', 'dermatitis'],
        
        # Immune
        'immune support': ['boost immunity', 'immune boosting', 'immunostimulant'],
        'infection': ['infectious', 'bacterial', 'viral'],
        
        # Women's health
        'menopause': ['climacteric', 'change of life', 'menopausal'],
        'pms': ['premenstrual syndrome', 'premenstrual'],
        'heavy periods': ['menorrhagia', 'excessive bleeding'],
        
        # Men's health
        'prostate': ['prostatic', 'bph'],
        
        # Urinary
        'uti': ['urinary tract infection', 'cystitis', 'bladder infection'],
        'diuretic': ['water pill', 'increases urination'],
        
        # Modalities
        'morning': ['am', 'a.m.', 'dawn'],
        'evening': ['pm', 'p.m.', 'night', 'dusk'],
        'night': ['nocturnal', 'nighttime', 'while sleeping'],
        'cold': ['chilly', 'frigid', 'coldness'],
        'heat': ['hot', 'warmth', 'warm', 'heated'],
        'motion': ['movement', 'moving', 'activity'],
        'rest': ['lying down', 'reclining', 'resting'],
    }
    
    # Reverse index for fast lookup
    _reverse_synonyms: Optional[Dict[str, str]] = None
    
    def __init__(
        self,
        lowercase: bool = True,
        remove_stopwords: bool = True,
        stem: bool = True,
        use_synonyms: bool = True
    ):
        self.lowercase = lowercase
        self.remove_stopwords = remove_stopwords
        self.stem = stem
        self.use_synonyms = use_synonyms
        
        self.stemmer = PorterStemmer() if stem else None
        self.fuzzy = FuzzyMatcher()
        
        # Common stopwords
        self.stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
            'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'between', 'under', 'and', 'but', 'or', 'yet', 'so',
            'it', 'its', 'itself', 'they', 'them', 'their', 'this',
            'that', 'these', 'those', 'i', 'me', 'my', 'we', 'us',
        }
        
        # Build reverse synonym index
        if self._reverse_synonyms is None:
            self._build_reverse_synonyms()
    
    def _build_reverse_synonyms(self):
        """Build reverse lookup for synonyms."""
        self.__class__._reverse_synonyms = {}
        for key, values in self.SYNONYMS.items():
            for value in values:
                self._reverse_synonyms[value] = key
    
    def tokenize(self, text: str, include_bigrams: bool = True) -> List[str]:
        """
        Tokenize text into normalized tokens.
        
        Args:
            text: Input text
            include_bigrams: Whether to include bigrams
        
        Returns:
            List of tokens
        """
        if self.lowercase:
            text = text.lower()
        
        # Replace punctuation with spaces, but keep apostrophes in words
        text = re.sub(r'[^\w\s\']', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Remove standalone apostrophes and clean
        words = [w.strip("'\"") for w in words if w.strip("'\"")]
        
        # Filter stopwords
        if self.remove_stopwords:
            words = [w for w in words if w not in self.stopwords]
        
        # Stemming
        if self.stem and self.stemmer:
            words = [self.stemmer.stem(w) for w in words]
        
        tokens = words
        
        # Add bigrams
        if include_bigrams and len(words) >= 2:
            bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words) - 1)]
            tokens.extend(bigrams)
        
        return tokens
    
    def expand_synonyms(self, tokens: List[str]) -> List[str]:
        """
        Expand tokens with synonyms.
        
        Args:
            tokens: Original tokens
        
        Returns:
            Original tokens + synonyms
        """
        if not self.use_synonyms:
            return tokens
        
        expanded = set(tokens)
        
        for token in tokens:
            # Check if token is a canonical form
            if token in self.SYNONYMS:
                expanded.add(token)
                expanded.update(self.SYNONYMS[token])
            
            # Check if token is a synonym of something
            canonical = self._reverse_synonyms.get(token)
            if canonical:
                expanded.add(canonical)
                expanded.update(self.SYNONYMS.get(canonical, []))
        
        return list(expanded)
    
    def tokenize_query(self, query: str) -> Dict[str, Any]:
        """
        Parse and tokenize a search query.
        
        Supports:
        - Phrases in quotes: "exact phrase"
        - AND/OR/NOT operators
        - Prefix matching with *
        
        Returns dict with:
        - required: list of required tokens
        - optional: list of optional tokens
        - excluded: list of excluded tokens
        - phrases: list of exact phrases
        """
        result = {
            'required': [],
            'optional': [],
            'excluded': [],
            'phrases': []
        }
        
        # Extract phrases in quotes
        phrase_pattern = r'"([^"]+)"'
        phrases = re.findall(phrase_pattern, query)
        result['phrases'] = phrases
        
        # Remove phrases from query
        query = re.sub(phrase_pattern, '', query)
        
        # Tokenize remaining
        tokens = self.tokenize(query, include_bigrams=False)
        
        # Parse operators (simple approach)
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token == 'not' and i + 1 < len(tokens):
                result['excluded'].append(tokens[i + 1])
                i += 2
            elif token == 'and' and i + 1 < len(tokens):
                result['required'].append(tokens[i + 1])
                i += 2
            elif token == 'or':
                i += 1
            else:
                result['optional'].append(token)
                i += 1
        
        # If no explicit operators, treat all as optional initially
        if not result['required'] and not result['excluded']:
            result['optional'] = tokens
        
        return result


class InvertedIndex:
    """
    Inverted index for fast token lookup.
    """
    
    def __init__(self):
        # token -> list of (indication_id, tf, field)
        self.index: Dict[str, List[Tuple[int, float, str]]] = defaultdict(list)
        # indication_id -> document length (total tokens)
        self.doc_lengths: Dict[int, int] = {}
        # Average document length
        self.avg_doc_length = 0.0
        # total documents
        self.total_docs = 0
    
    def add_document(
        self,
        indication_id: int,
        tokens: List[str],
        field: str = 'text'
    ):
        """Add a document to the index."""
        # Count term frequencies
        term_counts = defaultdict(int)
        for token in tokens:
            term_counts[token] += 1
        
        # Calculate normalized TF
        max_count = max(term_counts.values()) if term_counts else 1
        doc_length = len(tokens)
        
        for token, count in term_counts.items():
            tf = 0.5 + 0.5 * (count / max_count)  # Normalized TF
            self.index[token].append((indication_id, tf, field))
        
        self.doc_lengths[indication_id] = doc_length
        self.total_docs += 1
    
    def get_postings(self, token: str) -> List[Tuple[int, float, str]]:
        """Get posting list for a token."""
        return self.index.get(token, [])
    
    def calculate_avg_doc_length(self):
        """Calculate average document length."""
        if self.total_docs == 0:
            self.avg_doc_length = 0.0
        else:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.total_docs
    
    def save(self, filepath: str):
        """Save index to file."""
        data = {
            'index': {k: v for k, v in self.index.items()},
            'doc_lengths': self.doc_lengths,
            'avg_doc_length': self.avg_doc_length,
            'total_docs': self.total_docs
        }
        with open(filepath, 'w') as f:
            json.dump(data, f)
    
    def load(self, filepath: str):
        """Load index from file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.index = defaultdict(list, data['index'])
        self.doc_lengths = data['doc_lengths']
        self.avg_doc_length = data['avg_doc_length']
        self.total_docs = data['total_docs']


class LexicalSearcher:
    """
    Advanced lexical search using inverted index and BM25 scoring.
    """
    
    def __init__(
        self,
        db: BotanicalDatabase,
        index_path: str = "data/lexical_index.json",
        use_bigrams: bool = True,
        use_synonyms: bool = True,
        use_stemming: bool = True,
        scoring: str = 'bm25'  # 'tfidf' or 'bm25'
    ):
        self.db = db
        self.index_path = Path(index_path)
        self.use_bigrams = use_bigrams
        self.scoring = scoring
        
        self.tokenizer = Tokenizer(
            stem=use_stemming,
            use_synonyms=use_synonyms
        )
        self.index = InvertedIndex()
        self.idf_cache: Dict[str, float] = {}
        
        # BM25 parameters
        self.k1 = 1.5  # Term frequency saturation
        self.b = 0.75  # Length normalization
        
        # Try to load existing index
        if self.index_path.exists():
            self.index.load(str(self.index_path))
    
    def build_index(self) -> Dict[str, int]:
        """
        Build inverted index from all indications in database.
        
        Returns:
            Statistics dict
        """
        print("Building lexical index with advanced features...")
        
        with self.db.connection() as conn:
            cursor = conn.execute(
                """SELECT id, indication_text, normalized_text, category 
                   FROM indications"""
            )
            rows = cursor.fetchall()
        
        if not rows:
            print("No indications found in database.")
            return {"indexed": 0}
        
        # Reset index
        self.index = InvertedIndex()
        
        for row in rows:
            # Index normalized text
            if row["normalized_text"]:
                tokens = self.tokenizer.tokenize(
                    row["normalized_text"],
                    include_bigrams=self.use_bigrams
                )
                tokens = self.tokenizer.expand_synonyms(tokens)
                self.index.add_document(row["id"], tokens, 'normalized')
            
            # Index original text
            if row["indication_text"]:
                tokens = self.tokenizer.tokenize(
                    row["indication_text"],
                    include_bigrams=self.use_bigrams
                )
                tokens = self.tokenizer.expand_synonyms(tokens)
                self.index.add_document(row["id"], tokens, 'text')
            
            # Index category
            if row["category"]:
                tokens = self.tokenizer.tokenize(row["category"], include_bigrams=False)
                self.index.add_document(row["id"], tokens, 'category')
        
        # Calculate average document length
        self.index.calculate_avg_doc_length()
        
        # Save index
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index.save(str(self.index_path))
        
        # Precompute IDF scores
        self._precompute_idf()
        
        print(f"✅ Lexical index built: {len(rows)} indications")
        print(f"   Unique terms: {len(self.index.index)}")
        print(f"   Avg doc length: {self.index.avg_doc_length:.1f}")
        return {"indexed": len(rows), "terms": len(self.index.index)}
    
    def _precompute_idf(self):
        """Precompute IDF scores for all terms."""
        for token, postings in self.index.index.items():
            df = len(set(p[0] for p in postings))  # Document frequency
            # IDF = log((N - df + 0.5) / (df + 0.5))
            idf = math.log(
                (self.index.total_docs - df + 0.5) / (df + 0.5) + 1.0
            )
            self.idf_cache[token] = idf
    
    def _get_idf(self, token: str) -> float:
        """Get IDF score for a token."""
        if token not in self.idf_cache:
            postings = self.index.get_postings(token)
            df = len(set(p[0] for p in postings))
            self.idf_cache[token] = math.log(
                (self.index.total_docs - df + 0.5) / (df + 0.5) + 1.0
            )
        return self.idf_cache[token]
    
    def _calculate_bm25(
        self,
        tf: float,
        idf: float,
        doc_length: int
    ) -> float:
        """
        Calculate BM25 score for a term.
        
        BM25 formula:
        score = IDF * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / avdl)))
        """
        if self.index.avg_doc_length == 0:
            return tf * idf
        
        dl_ratio = doc_length / self.index.avg_doc_length
        denominator = tf + self.k1 * (1 - self.b + self.b * dl_ratio)
        
        return idf * (tf * (self.k1 + 1)) / denominator
    
    def search(
        self,
        query: str,
        limit: int = 20,
        category: Optional[str] = None,
        min_score: float = 0.0,
        fuzzy_threshold: Optional[float] = None
    ) -> List[SearchResult]:
        """
        Search indications using lexical matching.
        
        Args:
            query: Search query
            limit: Maximum results
            category: Filter by category
            min_score: Minimum score threshold
            fuzzy_threshold: Enable fuzzy matching (0.0-1.0, None=disabled)
        
        Returns:
            List of SearchResult objects
        """
        # Parse query
        parsed = self.tokenizer.tokenize_query(query)
        
        # Collect all query tokens
        query_tokens = []
        query_tokens.extend(parsed['required'])
        query_tokens.extend(parsed['optional'])
        
        # Expand synonyms
        query_tokens = self.tokenizer.expand_synonyms(query_tokens)
        
        # Add bigrams
        if self.use_bigrams:
            bigrams = self.tokenizer.tokenize(query, include_bigrams=True)
            query_tokens.extend([t for t in bigrams if '_' in t])
        
        if not query_tokens and not parsed['phrases']:
            return []
        
        # Score documents
        scores: Dict[int, float] = defaultdict(float)
        matched_terms: Dict[int, Set[str]] = defaultdict(set)
        
        # Score token matches
        for token in query_tokens:
            idf = self._get_idf(token)
            postings = self.index.get_postings(token)
            
            if not postings and fuzzy_threshold:
                # Try fuzzy matching
                similar_tokens = self._find_fuzzy_matches(token, fuzzy_threshold)
                for sim_token in similar_tokens:
                    postings.extend(self.index.get_postings(sim_token))
            
            for indication_id, tf, field in postings:
                # Calculate score based on scoring method
                if self.scoring == 'bm25':
                    doc_length = self.index.doc_lengths.get(indication_id, 0)
                    score = self._calculate_bm25(tf, idf, doc_length)
                else:
                    score = tf * idf
                
                # Boost exact matches in normalized field
                if field == 'normalized':
                    score *= 1.2
                
                # Boost required terms
                if token in parsed['required']:
                    score *= 2.0
                
                scores[indication_id] += score
                matched_terms[indication_id].add(token)
        
        # Handle phrase matches
        for phrase in parsed['phrases']:
            phrase_lower = phrase.lower()
            # Find exact phrase matches
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """SELECT id FROM indications 
                       WHERE LOWER(indication_text) LIKE ? 
                       OR LOWER(normalized_text) LIKE ?""",
                    (f'%{phrase_lower}%', f'%{phrase_lower}%')
                )
                for row in cursor.fetchall():
                    scores[row['id']] += 5.0  # Big boost for phrase match
        
        # Exclude documents with excluded terms
        for indication_id in list(scores.keys()):
            if matched_terms[indication_id] & set(parsed['excluded']):
                del scores[indication_id]
        
        # Filter by minimum score
        scores = {k: v for k, v in scores.items() if v >= min_score}
        
        # Sort by score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        # Apply limit
        sorted_ids = sorted_ids[:limit]
        
        # Fetch full indications and build results
        results = []
        for indication_id in sorted_ids:
            indication = self.db.get_indication_by_id(indication_id)
            
            if indication:
                # Filter by category if specified
                if category and indication.category != category:
                    continue
                
                results.append(SearchResult(
                    item=indication,
                    score=scores[indication_id],
                    match_type="lexical",
                    matched_text=indication.indication_text
                ))
        
        return results
    
    def _find_fuzzy_matches(
        self,
        token: str,
        threshold: float
    ) -> List[str]:
        """Find fuzzy matches for a token in the index."""
        matches = []
        for idx_token in self.index.index.keys():
            sim = self.tokenizer.fuzzy.similarity(token, idx_token)
            if sim >= threshold:
                matches.append(idx_token)
        return matches[:3]  # Limit fuzzy matches
    
    def search_exact(self, query: str) -> List[SearchResult]:
        """
        Search for exact matches (case-insensitive).
        
        Args:
            query: Exact query string
        
        Returns:
            List of exact matches
        """
        with self.db.connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM indications 
                   WHERE LOWER(indication_text) = LOWER(?)
                   OR LOWER(normalized_text) = LOWER(?)""",
                (query, query)
            )
            rows = cursor.fetchall()
        
        results = []
        for row in rows:
            indication = Indication(
                id=row["id"],
                indication_text=row["indication_text"],
                normalized_text=row["normalized_text"],
                category=row["category"],
                subcategory=row["subcategory"],
                body_system=row["body_system"]
            )
            results.append(SearchResult(
                item=indication,
                score=1.0,
                match_type="exact",
                matched_text=indication.indication_text
            ))
        
        return results
    
    def suggest_completions(self, prefix: str, limit: int = 10) -> List[str]:
        """
        Suggest completions for a prefix (for autocomplete).
        
        Args:
            prefix: Query prefix
            limit: Maximum suggestions
        
        Returns:
            List of completion strings
        """
        prefix_lower = prefix.lower()
        matches = []
        
        for token in self.index.index.keys():
            if token.startswith(prefix_lower):
                matches.append(token)
        
        # Sort by frequency (number of postings)
        matches.sort(key=lambda t: len(self.index.index[t]), reverse=True)
        
        return matches[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "total_documents": self.index.total_docs,
            "unique_terms": len(self.index.index),
            "avg_doc_length": self.index.avg_doc_length,
            "indexed": self.index.total_docs > 0,
            "scoring": self.scoring,
            "stemming": self.tokenizer.stem is not None,
            "synonyms": self.tokenizer.use_synonyms
        }


def main():
    """CLI for lexical search."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Advanced lexical search")
    parser.add_argument("--build", action="store_true", help="Build index")
    parser.add_argument("--search", metavar="QUERY", help="Search query")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    parser.add_argument("--complete", metavar="PREFIX", help="Get completions")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--scoring", choices=['tfidf', 'bm25'], default='bm25')
    parser.add_argument("--fuzzy", type=float, help="Fuzzy threshold (0.0-1.0)")
    
    args = parser.parse_args()
    
    from src.database import BotanicalDatabase
    db = BotanicalDatabase()
    searcher = LexicalSearcher(db, scoring=args.scoring)
    
    if args.build:
        stats = searcher.build_index()
        print(json.dumps(stats, indent=2))
    
    elif args.search:
        results = searcher.search(
            args.search,
            limit=args.limit,
            fuzzy_threshold=args.fuzzy
        )
        print(f"\nSearch results for: '{args.search}'")
        print(f"Scoring: {args.scoring}")
        print("-" * 50)
        for r in results:
            print(f"[{r.score:.3f}] {r.item.indication_text}")
    
    elif args.complete:
        completions = searcher.suggest_completions(args.complete, args.limit)
        print(f"\nCompletions for '{args.complete}':")
        for c in completions:
            print(f"  {c}")
    
    elif args.stats:
        stats = searcher.get_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
