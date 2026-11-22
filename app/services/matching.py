"""Ingredient name matching (spec v0.2.0 §6.1), used for stop-lists and seasonal produce.

Pure functions, no I/O.
"""

import re
from collections.abc import Iterable
from functools import lru_cache

_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """GEN-1: trim, lowercase, collapse whitespace (``" Peanut  Butter"`` → ``"peanut butter"``)."""
    return _WHITESPACE.sub(" ", name.strip().lower())


@lru_cache(maxsize=4096)
def _term_pattern(term: str) -> re.Pattern[str]:
    """Whole-word regex for a normalised term, also accepting an ``s`` / ``es`` plural.

    Lookarounds instead of ``\\b`` so terms that start or end with punctuation
    (``c++``) still match at word edges.
    """
    return re.compile(rf"(?<!\w){re.escape(term)}(?:s|es)?(?!\w)")


def term_matches(term: str, ingredient_name: str) -> bool:
    """GEN-2: does ``term`` occur in ``ingredient_name`` as whole words?

    ``peanut`` matches ``peanut butter`` and ``roasted peanuts``; ``egg`` matches
    ``eggs`` but not ``eggplant``; ``nut`` does not match ``peanut``. Both sides are
    normalised first.
    """
    term = normalize_name(term)
    if not term:
        return False
    return _term_pattern(term).search(normalize_name(ingredient_name)) is not None


def matched_terms(terms: Iterable[str], ingredient_names: Iterable[str]) -> list[str]:
    """Return the terms (in their given order) that match at least one ingredient."""
    names = [normalize_name(n) for n in ingredient_names]
    return [t for t in terms if any(term_matches(t, n) for n in names)]
