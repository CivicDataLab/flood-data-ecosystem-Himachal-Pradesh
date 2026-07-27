#!/usr/bin/env python3
"""
Clean a line_items.csv produced by the pipeline:

  (a) tag summary / total / department-header rows so they are excluded from
      allocation sums (they duplicate the detail rows beneath them);
  (b) correct amounts whose table unit was mis-detected (a bare "count" >= the
      rupees threshold that was multiplied as lakh/crore is re-read as rupees),
      and flag any single line item above the per-item ceiling;
  (c) snap the district to a canonical Assam district (fuzzy spelling fixes +
      known town->district), and bucket state-wide / unresolved places.

Originals are preserved; new columns are added:
  row_kind, is_line_item, amount_inr_clean, amount_lakh_clean, amount_unit_basis,
  amount_outlier, allocation_inr (clean amount for line items only, else blank),
  district_canon, district_level

Usage:  python clean.py line_items.csv [line_items_clean.csv]
"""
from __future__ import annotations
import re
import sys
import pandas as pd

import config
import normalize as N
import classify as C

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _bare_numeric(raw):
    """Numeric value of an amount cell, ignoring currency/units/commas."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = N._CURRENCY_RE.sub(" ", str(raw))
    s = N._UNIT_WORD_RE.sub(" ", s).replace("/-", " ")
    m = _NUM.search(s)
    if not m:
        return None
    try:
        return float(m.group(0).rstrip(".").replace(",", ""))
    except ValueError:
        return None


def _snap_ratio(r):
    """Snap an observed multiplier to the nearest known unit factor."""
    for f in (1, 1e3, 1e5, 1e7):
        if r and 0.95 * f <= r <= 1.05 * f:
            return f
    return None


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # (a) row kind
    df["row_kind"] = [
        N.classify_row_kind(w, s, d)
        for w, s, d in zip(df.get("work_text"), df.get("sl_no"), df.get("district"))
    ]
    df["is_line_item"] = df["row_kind"] == "line_item"

    # (b) amount correction (preserve correct rupee tables; fix mis-multiplied ones)
    clean, basis, outlier = [], [], []
    for _, r in df.iterrows():
        orig = r.get("amount_inr")
        num = _bare_numeric(r.get("amount_raw"))
        b = "kept"
        val = orig
        if num is not None and pd.notna(orig) and num > 0:
            ratio = _snap_ratio(orig / num)
            # a count multiplied as lakh/crore but implausibly large -> rupees
            if ratio and ratio >= 1e5 and num >= config.COUNT_AS_RUPEES_THRESHOLD:
                val = num
                b = "unit_corrected_to_rupees"
        elif num is not None and pd.isna(orig):
            val = N.to_inr(r.get("amount_raw"))
            b = "recomputed"
        clean.append(val)
        basis.append(b)
        is_li = r["row_kind"] == "line_item"
        outlier.append(bool(is_li and pd.notna(val) and val > config.PER_ITEM_CEILING_INR))
    df["amount_inr_clean"] = clean
    df["amount_lakh_clean"] = [None if pd.isna(v) else round(v / 1e5, 4) for v in clean]
    df["amount_unit_basis"] = basis
    df["amount_outlier"] = outlier

    # allocation = clean amount, but only for genuine line items
    df["allocation_inr"] = df["amount_inr_clean"].where(df["is_line_item"])

    # (c) district snapping
    snapped = [N.snap_district(d) for d in df.get("district")]
    df["district_canon"] = [s[0] for s in snapped]
    df["district_level"] = [s[1] for s in snapped]

    # (d) re-classify from work_text with current rules: refreshes work_type
    # (incl. schools), relabelled disaster_phase, adds disaster_type, and
    # overrides a wrongly-carried department when the text names a school.
    wt, ph, dt, conf, dept, dept_src = [], [], [], [], [], []
    for w, d0 in zip(df.get("work_text"), df.get("department")):
        c = C.classify(w)
        wt.append(c["work_type"]); ph.append(c["disaster_phase"])
        dt.append(c["disaster_type"]); conf.append(c["classify_confidence"])
        inferred = C.infer_department(w)
        if inferred:
            dept.append(inferred); dept_src.append("text_override")
        else:
            dept.append(d0); dept_src.append("extracted")
    df["work_type"] = wt
    df["disaster_phase"] = ph
    df["disaster_type"] = dt
    df["classify_confidence"] = conf
    df["department_orig"] = df["department"]
    df["department"] = dept
    df["department_source"] = dept_src
    return df


def _cr(x):
    return round((x or 0) / 1e7, 2)


def summarise(before: pd.DataFrame, after: pd.DataFrame):
    print("=== row kinds ===")
    print(after["row_kind"].value_counts().to_string())
    print(f"\nrows total {len(after)} | line items {int(after['is_line_item'].sum())} "
          f"| summary/header excluded {int((~after['is_line_item']).sum())}")
    print("\n=== allocation total (Rs crore) ===")
    print(f"  raw amount_inr (all rows, as uploaded): {_cr(before['amount_inr'].sum())}")
    print(f"  clean, line-items only:                 {_cr(after['allocation_inr'].sum())}")
    corr = (after['amount_unit_basis'] == 'unit_corrected_to_rupees').sum()
    print(f"\nunit-corrected rows: {corr} | per-item outliers (> Rs100cr) flagged: "
          f"{int(after['amount_outlier'].sum())}")
    print("\n=== district levels ===")
    print(after["district_level"].value_counts(dropna=False).to_string())
    res = (after["district_level"] == "district").sum()
    print(f"resolved to a real district: {res}/{len(after)}; distinct districts: "
          f"{after.loc[after['district_level']=='district','district_canon'].nunique()}")
    print("\n=== clean allocation by year (line items, Rs crore) ===")
    li = after[after["is_line_item"]]
    print((li.groupby("year")["allocation_inr"].sum() / 1e7).round(1).to_string())


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else src.replace(".csv", "_clean.csv")
    df = pd.read_csv(src)
    cleaned = clean_dataframe(df)
    cleaned.to_csv(out, index=False)
    summarise(df, cleaned)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
