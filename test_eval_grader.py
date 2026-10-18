"""Regression tests for the evaluation grader and retrieval metrics.

These lock the corrections made in the metrics audit (Oct 2026). They are
EVALUATION-only: nothing here imports or touches the production pipeline
(answer/retrieve/ingest/extractors/app are never modified for this work).

Grading rules under test:
  * a purely numeric expected keyword is matched by NUMERIC VALUE, so
    "125,124,989" satisfies an expectation of "125124989"
  * numeric matching is strictly stricter than substring: "130" must NOT
    satisfy an expectation of "13"
  * decimal precision and sign are significant: 73.0 != 73.038, -500 != 500
  * non-numeric keywords keep exact case-insensitive substring semantics,
    so ratios ("4.5:1"), versions ("0.7.1") and names are unaffected
  * abstain / absent-answer handling is unchanged

Run: python -m pytest test_eval_grader.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_realworld.grader import (  # noqa: E402
    check_answer_corrected,
    check_answer_legacy,
    is_numeric_literal,
    numbers_in_text,
    source_coverage,
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def q(**kw):
    base = {"id": "x", "q": "?", "keywords": [], "any_keywords": []}
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# 1. The three original false negatives must now pass
# --------------------------------------------------------------------------
@pytest.mark.parametrize("expected,answer", [
    ("125124989", "Japan's population in 2022 was 125,124,989.  [Source 1]"),
    ("66628000", "The United Kingdom's population in 2019 was 66,628,000."),
    ("83160871", "Germany's population in 2020 was **83,160,871**."),
    ("126633000", "126,633,000"),
    ("124516650", "fell to 124,516,650"),
])
def test_thousands_separator_false_negatives_are_fixed(expected, answer):
    item = q(keywords=[expected])
    legacy_ok, _ = check_answer_legacy(item, answer)
    new_ok, _ = check_answer_corrected(item, answer)
    assert legacy_ok is False, "precondition: legacy grader really did miss it"
    assert new_ok is True, f"corrected grader missed {expected} in {answer!r}"


# --------------------------------------------------------------------------
# 2. Nearby but DIFFERENT values must still fail
# --------------------------------------------------------------------------
@pytest.mark.parametrize("expected,answer", [
    ("125124989", "Japan's population in 2022 was 125,124,980."),   # wrong digit
    ("125124989", "125,124,980"),                                  # wrong digit
    ("125124989", "12512499"),                                     # dropped digit
    ("125124989", "1,251,249,890"),                                # 10x too big
    ("66628000", "66,628,001"),
    ("83160871", "83,160,872"),
    ("126633000", "no population data available"),                 # number absent
])
def test_numerically_different_values_still_fail(expected, answer):
    ok, _ = check_answer_corrected(q(keywords=[expected]), answer)
    assert ok is False, f"wrongly accepted {answer!r} for {expected}"


# --------------------------------------------------------------------------
# 3. Substring false positives the legacy grader accepted must now fail
# --------------------------------------------------------------------------
@pytest.mark.parametrize("expected,answer", [
    ("13", "The depth of earthquake us7000lsze was 130 km."),
    ("10", "Accident reports are due within 100 days."),
    ("500", "The repair cost threshold is 1,500 dollars."),
    ("3", "The lighting must be visible for 35 miles."),
])
def test_substring_false_positives_are_rejected(expected, answer):
    """Legacy substring matching accepted these WRONGLY."""
    legacy_ok, _ = check_answer_legacy(q(keywords=[expected]), answer)
    new_ok, _ = check_answer_corrected(q(keywords=[expected]), answer)
    assert legacy_ok is True, "precondition: legacy really did accept it"
    assert new_ok is False, f"wrongly accepted {answer!r} for {expected}"


# --------------------------------------------------------------------------
# 4. Precision and sign are meaningful
# --------------------------------------------------------------------------
def test_decimal_precision_is_significant():
    assert check_answer_corrected(q(keywords=["73.038"]), "life expectancy 73.038")[0]
    # rounding to one decimal is a DIFFERENT value
    assert not check_answer_corrected(q(keywords=["73.038"]), "about 73.0")[0]
    # trailing zeros do not change the value
    assert check_answer_corrected(q(keywords=["76.98"]), "76.980 years")[0]
    assert check_answer_corrected(q(keywords=["6.07"]), "6.070 percent")[0]


def test_sign_is_significant():
    assert not check_answer_corrected(q(keywords=["500"]), "-500 m")[0]
    assert check_answer_corrected(q(keywords=["500"]), "+500 m")[0]
    # negative expected needs a negative candidate at the declared precision
    assert check_answer_corrected(q(keywords=["-3.2768"]),
                                  "GDP growth was -3.2768")[0]
    assert not check_answer_corrected(q(keywords=["-3.2768"]),
                                      "GDP growth was 3.2768")[0]


def test_author_rounded_expectations_match_full_precision_answers():
    """Six expected values in this benchmark are author-rounded copies of
    longer source numbers (independently confirmed by
    eval_realworld/verify_expected_values.py). Those must still match."""
    assert check_answer_corrected(q(keywords=["6.07"]),
                                  "China's growth was 6.06704239487995%")[0]
    assert check_answer_corrected(q(keywords=["2.339"]),
                                  "China 2020 growth was 2.3390000000000004%")[0]
    assert check_answer_corrected(q(keywords=["607"]), "depth 607.0 km")[0]


def test_small_and_zero_values():
    assert check_answer_corrected(q(keywords=["0"]), "the value is 0 meters")[0]
    assert check_answer_corrected(q(keywords=["7"]), "magnitude 7.0")[0]


# --------------------------------------------------------------------------
# 5. Units and percentages: compared as written, never converted
# --------------------------------------------------------------------------
def test_units_are_ignored_but_not_converted():
    # unit suffix must not block a value match
    assert check_answer_corrected(q(keywords=["1013.25"]),
                                  "1013.25 hPa")[0]
    # a converted magnitude is a different value and must not be accepted
    assert not check_answer_corrected(q(keywords=["29.9"]),
                                      "the whale is 30 m long")[0]
    # percent is NOT re-scaled against a fraction
    assert check_answer_corrected(q(keywords=["2.339"]), "2.339%")[0]
    assert not check_answer_corrected(q(keywords=["0.02339"]), "2.339%")[0]


# --------------------------------------------------------------------------
# 6. Non-numeric keywords keep legacy semantics (no weakening)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("expected,answer,ok", [
    ("Agrippa", "he read Agrippa and Cornelius", True),
    ("Agrippa", "he read the alchemists", False),
    ("MIT", "distributed under the MIT license", True),
    ("MIT", "distributed under Apache", False),
    ("4.5:1", "the ratio is 4.5:1", True),      # colon => NOT numeric
    ("4.5:1", "the ratio is 4.5", False),
    ("0.7.1", "cookie is 0.7.1", True),        # version => NOT numeric
    ("0.7.1", "cookie is 0.7", False),
    ("18", "engines.node: >= 18", True),
    ("Command-line utilities", "listed under Command-line utilities", True),
])
def test_non_numeric_keywords_are_literal(expected, answer, ok):
    assert check_answer_corrected(q(keywords=[expected]), answer)[0] is ok


def test_documents_names_and_identifiers_still_exact():
    # an identifier must match exactly, not as a loose number
    assert not check_answer_corrected(q(keywords=["us6000m0xl"]),
                                      "id us6000m0xm was 5.1")[0]
    assert check_answer_corrected(q(keywords=["us6000m0xl"]),
                                  "id us6000m0xl was 7.5")[0]
    # earth-shaking numbers inside prose must not fabricate a hit
    assert not check_answer_corrected(q(keywords=["29.9"]),
                                      "the largest animal ever recorded")[0]


# --------------------------------------------------------------------------
# 7. is_numeric_literal / numbers_in_text behave as documented
# --------------------------------------------------------------------------
@pytest.mark.parametrize("s", ["13", "1013.25", "1,234", "1,234,567.89",
                               "-3.276", "+500", "0", "6.07"])
def test_numeric_literals_recognised(s):
    assert is_numeric_literal(s) is True


@pytest.mark.parametrize("s", ["4.5:1", "0.7.1", "$500", "17 km", "five",
                               "72–135", "190-200", "August", "us6000m0xl",
                               "24 by 24", "1-2-3", "", "..", "1.2.3.4",
                               "12,34", "1,2345"])
def test_non_numeric_literals_rejected(s):
    assert is_numeric_literal(s) is False


def test_numbers_in_text_strips_separators_and_keeps_sign():
    vals = numbers_in_text("GDP -3.2767587964736 and pop 125,124,989")
    assert "-3.2767587964736" in vals
    assert "125124989" in vals


# --------------------------------------------------------------------------
# 8. Abstain / absent-answer semantics unchanged
# --------------------------------------------------------------------------
def test_abstain_still_accepted_only_on_refusal():
    item = q(id="ab1", abstain=True)
    ok, _ = check_answer_corrected(
        item, "I don't have enough information in the provided sources.")
    assert ok is True
    ok2, _ = check_answer_corrected(item, "The capital is Canberra.")
    assert ok2 is False


def test_absent_violation_still_rejected():
    item = q(keywords=["1818"], absent=["canberra"])
    ok, tags = check_answer_corrected(item, "It was published in 1818 in Canberra.")
    assert ok is False
    assert "ABSENT-VIOLATION" in tags


def test_multi_n_of_semantics_preserved():
    item = q(multi=["ship strikes", "pollution", "ocean noise"],
             multi_n=2)
    ok, _ = check_answer_corrected(item, "ship strikes and pollution")
    assert ok is True
    ok2, _ = check_answer_corrected(item, "only ship strikes")
    assert ok2 is False


def test_multi_numeric_items_use_value_matching():
    item = q(multi=["126633000", "124516650"], multi_n=2)
    ok, _ = check_answer_corrected(
        item, "from 126,633,000 in 2019 to 124,516,650 in 2023")
    assert ok is True
    bad, _ = check_answer_corrected(item, "no data available")
    assert bad is False


def test_any_keywords_pool_behaviour_unchanged():
    item = q(any_keywords=["6.067", "6.07", "6.06"])
    assert check_answer_corrected(item, "growth was 6.067%")[0]
    assert check_answer_corrected(item, "growth was 6.07%")[0]
    assert not check_answer_corrected(item, "growth was 6.2%")[0]


# --------------------------------------------------------------------------
# 9. No per-question special casing
# --------------------------------------------------------------------------
def test_grader_has_no_hardcoded_question_ids():
    """No per-question branching may exist in EXECUTABLE code.

    Prose in the module docstring is allowed to name the questions that
    motivated the rules; the code itself must stay uniform.
    """
    import ast
    import eval_realworld.grader as g

    tree = ast.parse(open(g.__file__, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)

    literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                literals.append(node.value)
    blob = " ".join(literals)
    for bad in ("wb1", "wb2", "wb3", "eq1", "eq2", "js1", "cd1", "cd2",
                "fr1", "express", "worldbank", "usgs", "faa_"):
        assert bad not in blob, f"grader code special-cases {bad!r}"


# --------------------------------------------------------------------------
# 10. Cross-document source coverage
# --------------------------------------------------------------------------
def test_all_required_sources_in_top3():
    cov = source_coverage({"id": "cd1", "q": "?",
                           "files_all": ["a.pdf", "b.pdf"]},
                          ["a.pdf", "b.pdf", "a.pdf"],
                          ["a.pdf", "b.pdf", "a.pdf", "b.pdf"])
    assert cov["all_required_at3"] is True
    assert cov["all_required_at6"] is True
    assert cov["any_required_at3"] is True
    assert cov["n_required"] == 2
    assert cov["covered_at3"] == 2


def test_only_one_of_several_required_sources_is_a_miss():
    cov = source_coverage({"id": "cd3", "q": "?",
                           "files_all": ["a.pdf", "b.pdf", "c.pdf"]},
                          ["a.pdf", "x.pdf", "y.pdf"],
                          ["a.pdf", "x.pdf", "y.pdf", "z.pdf", "w.pdf",
                           "v.pdf"])
    assert cov["any_required_at3"] is True
    assert cov["all_required_at3"] is False, \
        "a cross-doc question is NOT fully retrieved with only 1 of 3 sources"
    assert cov["all_required_at6"] is False


def test_depth_matters_all6_true_but_all3_false():
    cov = source_coverage({"id": "cd4", "q": "?",
                           "files_all": ["a.pdf", "b.pdf"]},
                          ["a.pdf", "x.pdf", "y.pdf"],
                          ["a.pdf", "x.pdf", "y.pdf", "b.pdf", "z.pdf",
                           "w.pdf"])
    assert cov["all_required_at3"] is False
    assert cov["all_required_at6"] is True
    assert cov["covered_at3"] == 1
    assert cov["covered_at6"] == 2


def test_single_source_question_behaves_like_recall():
    cov = source_coverage({"id": "wx1", "q": "?", "file": "a.pdf"},
                          ["a.pdf", "b.pdf", "c.pdf"],
                          ["a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf",
                           "f.pdf"])
    assert cov["all_required_at3"] is True
    assert cov["all_required_at6"] is True
    assert cov["n_required"] == 1


def test_unsupported_question_has_no_expected_source():
    cov = source_coverage({"id": "ab1", "q": "?", "abstain": True},
                          ["a.pdf", "b.pdf", "c.pdf"],
                          ["a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf",
                           "f.pdf"])
    assert cov["n_required"] == 0
    assert cov["has_expected_source"] is False
    assert cov["all_required_at3"] is None
    assert cov["all_required_at6"] is None


def test_no_required_source_retrieved_is_not_full_recall():
    cov = source_coverage({"id": "cd5", "q": "?",
                           "files_all": ["a.pdf", "b.pdf"]},
                          ["x.pdf", "y.pdf", "z.pdf"],
                          ["x.pdf", "y.pdf", "z.pdf", "w.pdf", "v.pdf",
                           "u.pdf"])
    assert cov["any_required_at3"] is False
    assert cov["all_required_at3"] is False
    assert cov["covered_at3"] == 0
