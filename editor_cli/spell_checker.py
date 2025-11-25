from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict


class SpellCheckerAdapter(ABC):
    @abstractmethod
    def check(self, text: str) -> List[Tuple[str, str]]:
        """
        Check text for spelling errors.
        Returns a list of (wrong_word, suggestion).
        """
        pass


class MockSpellChecker(SpellCheckerAdapter):
    def __init__(self) -> None:
        # Simple mock dictionary: wrong -> right
        self.corrections: Dict[str, str] = {
            "recieve": "receive",
            "occured": "occurred",
            "Itallian": "Italian",
            "Rowlling": "Rowling",
            "teh": "the",
            "adn": "and",
            "eidtor": "editor"
        }

    def check(self, text: str) -> List[Tuple[str, str]]:
        results = []
        # Simple tokenization by splitting on whitespace and stripping punctuation
        import re
        tokens = re.split(r'(\W+)', text)
        
        for token in tokens:
            clean_token = token.strip()
            if not clean_token:
                continue
            
            if clean_token in self.corrections:
                results.append((clean_token, self.corrections[clean_token]))
                
        return results


class RealSpellChecker(SpellCheckerAdapter):
    def __init__(self) -> None:
        try:
            from spellchecker import SpellChecker
            self.spell = SpellChecker()
            self.available = True
        except ImportError:
            self.available = False

    def check(self, text: str) -> List[Tuple[str, str]]:
        if not self.available:
            return []
            
        import re
        # Find words
        tokens = re.findall(r'\b\w+\b', text)
        if not tokens:
            return []
            
        misspelled = self.spell.unknown(tokens)
        results = []
        for word in misspelled:
            correction = self.spell.correction(word)
            if correction and correction != word:
                results.append((word, correction))
        return results
