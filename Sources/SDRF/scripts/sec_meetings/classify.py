"""
Classification of a free-text work/scheme description into:
  - work_type      (what kind of work)
  - disaster_phase (preparedness / mitigation / response-repair-restoration)

Rule-based and deterministic. The same rubric (config.py) is also handed to
the LLM extractor, so an LLM run and an offline run produce comparable labels.
A confidence flag is returned so ambiguous items can be reviewed.
"""
from __future__ import annotations
import re
from typing import Tuple
import config

# School / education-institution signals. Word-bounded so acronyms like MES do
# NOT match inside words such as "scheMES". Used both to set the work type and
# to override a wrongly-carried department (these are Education, not WRD/Power).
SCHOOL_RE = re.compile(
    r"\b(L\.?P\.?S|LPS|M\.?E\.?S|MES|M\.?E\.?\s?school|J\.?B\.?S|JBS|MEM|"
    r"H\.?S\.?S|HSS|HS|G\.?P\.?S|GPS|M\.?V\.?\s?school|"
    r"school|schools|vidyalaya|vidyapith|pathsala|pathshala|"
    r"madrassa|madrasa|college)\b", re.I)

SCHOOL_WORK_TYPE = "Schools / Education infrastructure"


def _s(text) -> str:
    """Coerce to a safe string ('' for None/NaN/float)."""
    if text is None or not isinstance(text, str):
        return "" if text is None or text != text else str(text)  # text!=text => NaN
    return text


def infer_department(text):
    """Strong content signal that overrides a mis-carried agenda department.
    Currently: anything naming a school/education institution -> Education."""
    t = _s(text)
    if t and SCHOOL_RE.search(t):
        return "Education"
    return None


def classify_disaster_type(text) -> str:
    label, _ = _match(_s(text), config.DISASTER_TYPE_RULES)
    return label or config.DISASTER_TYPE_DEFAULT


def _match(text: str, rules) -> Tuple[str, int]:
    """Return (label, num_keyword_hits) for the first rule with any hit."""
    low = _s(text).lower()
    for label, keywords in rules:
        hits = sum(1 for k in keywords if k in low)
        if hits:
            return label, hits
    return None, 0


def classify_work_type(text) -> str:
    t = _s(text)
    if t and SCHOOL_RE.search(t):           # schools win over generic rules
        return SCHOOL_WORK_TYPE
    label, _ = _match(t, config.WORK_TYPE_RULES)
    return label or config.WORK_TYPE_DEFAULT


def classify_phase(text) -> str:
    label, _ = _match(_s(text), config.PHASE_RULES)
    return label or config.PHASE_DEFAULT


def classify(text) -> dict:
    """Full classification with a crude confidence signal.

    confidence = 'low' when nothing matched, 'medium' for a single weak hit,
    'high' when both work-type and phase matched. Lets you filter the long
    tail of ambiguous descriptions for manual / LLM review.
    """
    wt = classify_work_type(text)
    ph, ph_hits = _match(text, config.PHASE_RULES)
    wt_known = wt != config.WORK_TYPE_DEFAULT
    if wt_known and ph:
        conf = "high"
    elif wt_known or ph:
        conf = "medium"
    else:
        conf = "low"
    return {
        "work_type": wt,
        "disaster_phase": ph or config.PHASE_DEFAULT,
        "disaster_type": classify_disaster_type(text),
        "classify_confidence": conf,
    }
