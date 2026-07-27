"""
Deterministic normalisation helpers. No network, fully unit-testable.
"""
from __future__ import annotations
import re
import datetime as _dt
from typing import Optional
import config


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------
_UNIT_WORD_RE = re.compile(r"\b(crores?|cr|lakhs?|lacs?|thousand)\b\.?", re.I)
_CURRENCY_RE = re.compile(r"(rs\.?|inr|₹)", re.I)
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _unit_mult(word: str) -> float:
    w = (word or "").lower().strip(" .")
    for key, m in config.UNIT_MULTIPLIERS.items():
        if key and key in w:
            return m
    return 1.0


def parse_amount(raw, unit_hint: str = "") -> dict:
    """Parse one amount cell into rupees with an explicit decision basis.

    Returns {'inr': float|None, 'basis': str, 'flag': str|None}.

    Decision rule (order matters):
      1. raw carries an explicit unit word (Cr/crore/lakh/...) -> the number is a
         COUNT in that unit; multiply. The page default unit is IGNORED so the
         multiplier can't be applied twice.
      2. raw uses comma grouping (e.g. 17,00,000 or Rs.7,15,000/-) -> it is an
         ABSOLUTE rupee figure; strip separators, NO unit multiplier. (Indian and
         western grouping both collapse to the same integer once commas go.)
      3. bare number with >= 6 integer digits and no unit -> almost certainly
         already rupees, not a lakh/crore count; treat as rupees and FLAG for
         source verification.
      4. otherwise (small bare number like 206.10) -> a COUNT in the column's
         unit (unit_hint or the configured default); multiply.
    """
    if raw is None:
        return {"inr": None, "basis": "empty", "flag": None}
    s = str(raw)

    explicit = _UNIT_WORD_RE.search(s)
    # remove currency tokens and unit words BEFORE pulling out the number, so a
    # 'Rs.' period or a 'Cr' can never leak into the numeric token.
    cleaned = _CURRENCY_RE.sub(" ", s)
    cleaned = _UNIT_WORD_RE.sub(" ", cleaned).replace("/-", " ")
    m = _NUM_RE.search(cleaned)
    if not m:
        return {"inr": None, "basis": "no_number", "flag": None}
    num = m.group(0).rstrip(".")
    digits = num.replace(",", "")
    if digits in ("", "."):
        return {"inr": None, "basis": "no_number", "flag": None}
    try:
        value = float(digits)
    except ValueError:
        return {"inr": None, "basis": "no_number", "flag": None}

    int_digits = digits.split(".")[0].lstrip("0") or "0"

    if explicit:
        return {"inr": value * _unit_mult(explicit.group(0)),
                "basis": "explicit_unit", "flag": None}
    if "," in num:
        flag = "small_value_check" if value < 1000 else None
        return {"inr": value, "basis": "comma_grouped_absolute", "flag": flag}
    if len(int_digits) >= 6:
        return {"inr": value, "basis": "bare_long_assumed_rupees",
                "flag": "ambiguous_unit_check_source"}
    # bare count in the column's unit -- but a "count" this large in lakh/crore
    # is implausible for one item and almost always a mis-detected rupee figure.
    if value >= config.COUNT_AS_RUPEES_THRESHOLD:
        return {"inr": value, "basis": "count_too_large_assumed_rupees",
                "flag": "unit_corrected_check_source"}
    return {"inr": value * _unit_mult(unit_hint or config.DEFAULT_UNIT),
            "basis": "count_in_unit", "flag": None}


def to_inr(raw, unit_hint: str = "") -> Optional[float]:
    """Backward-compatible thin wrapper returning just the rupee value."""
    return parse_amount(raw, unit_hint)["inr"]


def to_lakh(raw, unit_hint: str = "") -> Optional[float]:
    """Convenience: rupees expressed back in lakh (for human-readable tables)."""
    inr = to_inr(raw, unit_hint)
    return None if inr is None else inr / 1e5


# ---------------------------------------------------------------------------
# Controlled-vocab snapping
# ---------------------------------------------------------------------------
def _snap(value: str, alias_map: dict) -> Optional[str]:
    if not value:
        return None
    key = re.sub(r"\s+", " ", str(value).strip().lower())
    key = key.strip(" .:-")
    if key in alias_map:
        return alias_map[key]
    # substring / containment match (handles "kamrup (m) district" etc.)
    best = None
    for alias, canon in alias_map.items():
        if alias and alias in key:
            if best is None or len(alias) > len(best[0]):
                best = (alias, canon)
    return best[1] if best else None


def canon_district(value: str) -> Optional[str]:
    return _snap(value, config.DISTRICT_ALIASES)


def canon_department(value: str) -> Optional[str]:
    return _snap(value, config.DEPARTMENT_ALIASES)


def snap_district(value: str) -> tuple:
    """Map a raw 'district' cell to (GEOJSON_LABEL, level).

    Returns the district spelled EXACTLY as in the standard GeoJSON so cleaned
    output joins to it directly. level is one of:
      'district'   -> resolved to a GeoJSON district (incl. fuzzy spelling fixes
                      and known town/sub-district -> parent mappings)
      'state_wide' -> all-districts / multi-district / agency scope
      'unmapped'   -> a place we can't safely resolve (kept verbatim)
      None         -> empty
    """
    import difflib
    if not value or not str(value).strip():
        return (None, None)
    raw = re.sub(r"\s+", " ", str(value).strip())
    key = raw.lower().strip(" .,:-()")
    # 1) state-wide / agency scope
    for p in config.STATEWIDE_PATTERNS:
        if p in key:
            return ("STATE-WIDE / MULTIPLE", "state_wide")
    if key in ("assam", "state"):
        return ("STATE-WIDE / MULTIPLE", "state_wide")
    # 2) explicit alias -> GeoJSON label (metro, salmara, renames, spellings)
    for alias, label in config.GEOJSON_DISTRICT_ALIASES.items():
        if alias in key:
            return (label, "district")
    # 3) curated sub-district / town -> parent district, then to GeoJSON label
    for town, dist in config.SUBDISTRICT_TO_DISTRICT.items():
        if key.startswith(town):
            return (_to_geojson(dist), "district")
    # 4) exact / fuzzy match against the GeoJSON district names
    base = re.split(r"[(,]", key)[0].strip()
    norm = {re.sub(r"[^a-z]", "", d.lower()): d for d in config.GEOJSON_DISTRICTS}
    bkey = re.sub(r"[^a-z]", "", base)
    if bkey in norm:
        return (norm[bkey], "district")
    cand = difflib.get_close_matches(bkey, list(norm.keys()), n=1, cutoff=0.86)
    if cand:
        return (norm[cand[0]], "district")
    # 5) give up: keep original, mark unresolved
    return (raw, "unmapped")


def _to_geojson(name: str) -> str:
    """Map a title-case district name to its exact GeoJSON label."""
    k = re.sub(r"[^a-z]", "", name.lower())
    for d in config.GEOJSON_DISTRICTS:
        if re.sub(r"[^a-z]", "", d.lower()) == k:
            return d
    return name.upper()


def classify_row_kind(work_text, sl_no=None, district=None) -> str:
    """Distinguish a real allocation line item from a summary/total/header row.

    Returns 'line_item' | 'summary_total' | 'summary_dept' | 'header_orphan'
    | 'blank'. Summary rows duplicate the detail rows beneath them and must be
    excluded from allocation sums.
    """
    t = ("" if work_text is None else str(work_text)).strip()
    if not t:
        return "blank"
    if re.match(r"(?i)^\s*(grand\s+|sub[\s-]?)?total\b", t):
        return "summary_total"
    low = t.lower()
    words = re.findall(r"[a-z]+", low)
    has_action = any(w in config.ACTION_WORDS for w in words)
    no_sl = sl_no is None or str(sl_no).strip() in ("", "nan")
    no_dist = district is None or str(district).strip() in ("", "nan")
    # aggregate subtotal lines, e.g. "75 schemes", "166 nos. schemes"
    if not has_action and re.search(r"\b\d{1,4}\s+(nos?\.?\s+)?schemes?\b", low) \
            and len(words) <= 6:
        return "summary_aggregate"
    # agenda-section headers captured with a total, e.g.
    # "SDRF proposals of Irrigation Department for the year ..."
    if re.search(r"\bproposals?\s+of\b.*\bdepartment\b", low) or \
       re.search(r"\bproposals?\s+of\b.*\bfor\s+the\s+(year|period)\b", low):
        return "summary_aggregate"
    # a row that is essentially just a department name, with no serial/district
    if (not has_action and len(words) <= 6 and canon_department(t)
            and (no_sl or no_dist)):
        return "summary_dept"
    # an amount with no serial, no district, short label and no action verb
    if no_sl and no_dist and not has_action and len(t) < 35:
        return "header_orphan"
    return "line_item"


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
_MONTHS = ("january february march april may june july august september "
           "october november december").split()
_MON_RE = "|".join(_MONTHS + [m[:3] for m in _MONTHS])

_DATE_PATTERNS = [
    # 28 January 2026 / 2nd April, 2009 / 8" October, 2018 (junk-tolerant)
    re.compile(rf"(\d{{1,2}})\s*(?:st|nd|rd|th)?[^\w]{{0,4}}\s*({_MON_RE})[a-z]*[^\w]{{0,4}}\s*(\d{{4}})",
               re.I),
    # January 28, 2026
    re.compile(rf"({_MON_RE})[a-z]*\s+(\d{{1,2}})\s*(?:st|nd|rd|th)?[^\w]{{0,3}}\s*(\d{{4}})",
               re.I),
    # 06/10/2016 or 06-10-2016
    re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
]


def _clean_ocr(s: str) -> str:
    """Collapse newlines and strip the superscript/ordinal junk OCR leaves
    between a day and its month (e.g. '30™ November', '8\" October')."""
    s = s.replace("\n", " ")
    s = re.sub(r"[\"'`^~™”“’°]+", " ", s)
    return re.sub(r"\s+", " ", s)


def parse_meeting_date(text: str) -> Optional[str]:
    """Best-effort ISO date (YYYY-MM-DD) from minute header text.

    Prefers a date anchored to the title phrase 'held on ...', because minutes
    routinely cite OTHER dates (the previous meeting being confirmed, scheme
    years like '2016-17', action-taken-report periods). Only if no anchored
    date is found does it fall back to the first date anywhere in the text.
    """
    if not text:
        return None
    t = _clean_ocr(text)
    # 1) anchored: look only in the window right after "held on"
    m = re.search(r"held\s+on\s+(.{0,80})", t, re.I)
    if m:
        d = _first_date(m.group(1))
        if d:
            return d
    # 2) fallback: first parseable date anywhere (less reliable)
    return _first_date(t)


def _first_date(t: str) -> Optional[str]:
    for pat in _DATE_PATTERNS:
        m = pat.search(t)
        if not m:
            continue
        g = m.groups()
        try:
            if pat is _DATE_PATTERNS[2]:           # numeric d/m/Y
                d, mo, y = int(g[0]), int(g[1]), int(g[2])
            elif pat is _DATE_PATTERNS[1]:         # Month d, Y
                mo = _month_num(g[0]); d = int(g[1]); y = int(g[2])
            else:                                  # d Month Y
                d = int(g[0]); mo = _month_num(g[1]); y = int(g[2])
            if 2000 <= y <= 2035 and 1 <= mo <= 12 and 1 <= d <= 31:
                return _dt.date(y, mo, d).isoformat()
        except (ValueError, TypeError):
            continue
    return None


# dates embedded in filenames, e.g. 46th_sec_meeting_6_12_2022 or ..._10.12.2022
_FNAME_DATE = re.compile(r"(\d{1,2})[._\-](\d{1,2})[._\-](20\d{2})")


def date_from_filename(name: str) -> Optional[str]:
    m = _FNAME_DATE.search(name)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return _dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def _month_num(s: str) -> int:
    s = s.lower()[:3]
    for i, m in enumerate(_MONTHS, start=1):
        if m.startswith(s):
            return i
    raise ValueError(s)


def fiscal_year(iso_date: str) -> Optional[str]:
    """Indian FY label, e.g. 2016-04..2017-03 -> '2016-17'."""
    if not iso_date:
        return None
    try:
        d = _dt.date.fromisoformat(iso_date)
    except ValueError:
        return None
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"
