"""Ingredient name matching — spec v0.2.0 §6.1 (GEN-1, GEN-2)."""

import pytest

from app.services.matching import matched_terms, normalize_name, term_matches


def test_gen1_normalize_name() -> None:
    assert normalize_name("  Peanut   Butter ") == "peanut butter"


@pytest.mark.parametrize(
    ("term", "ingredient"),
    [
        ("peanut", "peanut butter"),
        ("peanut", "Roasted Peanuts"),
        ("egg", "eggs"),
        ("tomato", "cherry tomatoes"),
        ("peanut butter", "smooth  peanut butter"),
        ("Shrimp ", "shrimp"),
    ],
)
def test_gen2_term_matches_whole_words_and_plurals(term: str, ingredient: str) -> None:
    assert term_matches(term, ingredient)


@pytest.mark.parametrize(
    ("term", "ingredient"),
    [
        ("egg", "eggplant"),
        ("nut", "peanut"),
        ("pea", "chickpeas"),
        ("prawn", "shrimp"),  # no synonyms (documented limitation)
        ("", "anything"),
    ],
)
def test_gen2_term_does_not_match(term: str, ingredient: str) -> None:
    assert not term_matches(term, ingredient)


def test_gen2_term_with_regex_characters_is_literal() -> None:
    assert term_matches("c++", "c++ sauce")
    assert not term_matches("a.c", "abc")


def test_matched_terms_keeps_term_order() -> None:
    assert matched_terms(["milk", "egg", "soy"], ["eggs", "whole milk"]) == ["milk", "egg"]
