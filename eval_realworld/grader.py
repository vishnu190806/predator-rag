"""Deterministic answer-grading and retrieval-coverage metrics for the
real-world evaluation.

EVALUATION-ONLY MODULE. It deliberately imports nothing from the production
pipeline (answer / retrieve / ingest / extractors / app), so auditing the
metrics can never change or depend on shipping behaviour. No new dependencies:
only `re` and the standard library.

--------------------------------------------------------------------------
Why this module exists (metrics audit, Oct 2026)
--------------------------------------------------------------------------
`eval_realworld.eval_realworld.check_answer` matched every expected keyword by
plain case-insensitive SUBSTRING. That produced two opposite classes of error
on the real corpus:

  FALSE NEGATIVES (correct answer marked wrong)
      expected "125124989", model wrote "125,124,989"  -> wb1
      expected "66628000",  model wrote "66,628,000"   -> wb2
      expected "83160871",  model wrote "83,160,871"   -> wb3
    Pure formatting; the value is identical.

  FALSE POSITIVES (wrong answer marked right)
      expected "13",  answer "... was 130 km"         -> substring "13" hits
      expected "500", answer "1,500 dollars"          -> substring "500" hits
    These were latent in every prior reported score, in the optimistic
    direction, and are now closed.

--------------------------------------------------------------------------
Permitted normalization rules (exhaustive and deliberately narrow)
--------------------------------------------------------------------------
R1. A purely NUMERIC expected keyword (optional sign, optional thousands
    separators, optional decimal part) is matched by NUMERIC VALUE: the answer
    must contain a number token whose value equals the expectation.
R2. Matching strips thousands separators ONLY. It never rescales between
    percent and fraction, never converts units, never rounds.
R3. Agreement is checked at the precision the expected value declares. Trailing
    zeros are harmless (76.98 == 76.980) while real precision differences are
    rejected (73.0 != 73.038). Six expected values in this benchmark are
    author-rounded copies of longer source numbers, so exact equality would
    itself create false negatives; see `numeric_value_matches`.
R4. Sign is significant: -3.276 matches only -3.276..., never +3.276.
R5. Because a number must appear as a COMPLETE token, a value that merely
    contains the expected digits no longer matches (fixes R3 of the false
    positives above).
R6. NON-numeric keywords keep the original exact case-insensitive substring
    behaviour, so ratios ("4.5:1"), versions ("0.7.1"), ranges ("72-135"),
    identifiers ("us6000m0xl") and document names are completely unaffected.
R7. Abstain and absent-answer handling is byte-for-byte the original logic.
R8. No question id, filename or corpus value is special-cased. The rules are
    uniform; `test_eval_grader.py` asserts no id appears in this file.

`check_answer_legacy` reproduces the original scorer verbatim so historical
scores stay reproducible and comparable side by side.
"""
import re
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# numeric recognition
# ---------------------------------------------------------------------------
# A "numeric literal" is a number written the way a human writes a value:
#   [+-]?  ( 1234 | 1,234 | 1,234,567 )  ( . 12 )?
# Deliberately excludes: colons (ratios 4.5:1), multiple dots (versions
# 0.7.1, IPs), currency symbols, units, ranges with dashes and letters.
_NUMERIC_LITERAL = re.compile(
    r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$")

# A number token inside free text: same shape, separators allowed internally.
# The fractional part requires a digit after the dot so a sentence-final period
# ("... in 1818.") is not swallowed into the value.
_NUMBER_TOKEN = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def is_numeric_literal(value):
    """True if `value` is a bare number a human would write (see R1)."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    return bool(_NUMERIC_LITERAL.match(v))


def numbers_in_text(text):
    """Return every numeric token in `text` as a separator-free string.

    Sign is preserved, so callers can compare values exactly.
    """
    out = []
    for m in _NUMBER_TOKEN.finditer(text or ""):
        tok = m.group(0).replace(",", "")
        try:
            Decimal(tok)
        except (InvalidOperation, ValueError):
            continue
        out.append(tok)
    return out


def numeric_value_matches(expected, text):
    """True if any number in `text` agrees with `expected` (R1-R5).

    Agreement is evaluated at the PRECISION THE EXPECTED VALUE DECLARES.
    This matters because the benchmark's expected numbers are themselves
    author-rounded copies of longer source values -- independently verified
    against the corpus by `verify_expected_values.py`, six of them are not
    verbatim, e.g. expected "6.067" for the source value 6.06704239487995 and
    expected "2.339" for 2.3390000000000004. Requiring bit-exact equality
    would therefore manufacture false negatives for those six.

    So a candidate matches when it is equal to the expected value once both
    are quantized to the expected value's own decimal places. Consequences,
    all intended:
        expected "125124989" vs "125,124,980" -> 0 dp, differ      -> reject
        expected "13"         vs "130"          -> 0 dp, differ      -> reject
        expected "500"        vs "-500"         -> 0 dp, sign differs-> reject
        expected "73.038"     vs "73.0"         -> 3 dp, differ      -> reject
        expected "76.98"      vs "76.980"       -> 2 dp, equal       -> accept
        expected "6.07"       vs "6.0670423948" -> 2 dp, equal       -> accept
    """
    raw = expected.strip().replace(",", "")
    try:
        want = Decimal(raw)
    except (InvalidOperation, ValueError):
        return False
    dp = -Decimal(raw).as_tuple().exponent
    quantum = Decimal(1).scaleb(-dp) if dp > 0 else Decimal(1)
    for tok in numbers_in_text(text):
        try:
            cand = Decimal(tok)
        except (InvalidOperation, ValueError):
            continue
        if cand == want:
            return True
        try:
            if cand.quantize(quantum) == want:
                return True
        except (InvalidOperation, ValueError):
            continue
    return False


def keyword_matches(expected, text):
    """Match one expected keyword against an answer.

    Numeric expected -> numeric value comparison (R1-R5).
    Anything else    -> exact case-insensitive substring (R6, unchanged).
    """
    low = (text or "").lower()
    if is_numeric_literal(expected):
        return numeric_value_matches(expected, low)
    return expected.lower() in low


# ---------------------------------------------------------------------------
# answer scoring
# ---------------------------------------------------------------------------
def check_answer_legacy(item, text):
    """The ORIGINAL scorer, reproduced verbatim for comparability."""
    t = text.lower()
    if item.get("abstain"):
        return ("don't have enough information" in t or
                "not able to answer" in t or
                "cannot answer" in t), ["refusal"]
    if "absent" in item and any(a.lower() in t for a in item["absent"]):
        return False, ["ABSENT-VIOLATION"]
    if "multi" in item:
        hits = [k for k in item["multi"] if k.lower() in t]
        return (len(hits) >= item.get("multi_n", 2)), hits
    pool = item.get("keywords", []) + item.get("any_keywords", [])
    hits = [k for k in pool if k.lower() in t]
    return (len(hits) >= 1), hits


def check_answer_corrected(item, text):
    """Corrected scorer: numeric-aware matching, otherwise identical to legacy.

    Returns (passed, matched_keywords).
    """
    t = text.lower()
    # R7: abstain / absent handling is deliberately unchanged.
    if item.get("abstain"):
        return ("don't have enough information" in t or
                "not able to answer" in t or
                "cannot answer" in t), ["refusal"]
    if "absent" in item and any(a.lower() in t for a in item["absent"]):
        return False, ["ABSENT-VIOLATION"]
    if "multi" in item:
        hits = [k for k in item["multi"] if keyword_matches(k, t)]
        return (len(hits) >= item.get("multi_n", 2)), hits
    pool = item.get("keywords", []) + item.get("any_keywords", [])
    hits = [k for k in pool if keyword_matches(k, t)]
    return (len(hits) >= 1), hits


# ---------------------------------------------------------------------------
# retrieval / source-coverage metrics
# ---------------------------------------------------------------------------
def required_sources(item):
    """The source files a question legitimately needs.

    * `files_all`  -> every one of these must be retrieved (cross-document)
    * `file`       -> a single required source
    * abstain/absent -> none: these questions have no correct source
    """
    if item.get("files_all"):
        return list(item["files_all"])
    if item.get("file"):
        return [item["file"]]
    return []


def source_coverage(item, files3, files6):
    """Source-level coverage of a question at both retrieval depths.

    A cross-document question is FULLY retrieved only when EVERY required
    source is present. `any_required_at*` answers the weaker question ("was
    at least one of them retrieved?") and is reported separately so the two
    are never conflated.

    Returns a dict; values are None when the question has no expected source.
    """
    need = required_sources(item)
    set3 = set(files3 or [])
    set6 = set(files6 or [])
    if not need:
        return {"has_expected_source": False, "n_required": 0,
                "covered_at3": None, "covered_at6": None,
                "any_required_at3": None, "any_required_at6": None,
                "all_required_at3": None, "all_required_at6": None,
                "missing_at3": [], "missing_at6": []}
    c3 = [f for f in need if f in set3]
    c6 = [f for f in need if f in set6]
    return {"has_expected_source": True, "n_required": len(need),
            "covered_at3": len(c3), "covered_at6": len(c6),
            "any_required_at3": len(c3) > 0, "any_required_at6": len(c6) > 0,
            "all_required_at3": len(c3) == len(need),
            "all_required_at6": len(c6) == len(need),
            "missing_at3": [f for f in need if f not in set3],
            "missing_at6": [f for f in need if f not in set6]}
