"""
Aggregate all per-page records (in memory or from the JSON cache) into three
tidy tables and persist them as CSV + a SQLite database:

  line_items : one row per allocation (the analytical grain)
  meetings   : one row per source document (number, date, fund, totals)
  attendees  : one row per (meeting, person)
"""
from __future__ import annotations
import os
import glob
import json
import re
import sqlite3
from typing import List

import pandas as pd
import normalize as N
import config


def _iter_cached(cache_dir: str):
    for path in sorted(glob.glob(os.path.join(cache_dir, "*", "*.json"))):
        with open(path) as f:
            yield json.load(f)


def _norm_date(text):
    """A date phrase OR a clean date string -> ISO, else None."""
    if not text:
        return None
    s = str(text).strip()
    iso_m = re.match(r"(\d{4})-(\d{2})-(\d{2})\b", s)   # already ISO -> keep as-is
    if iso_m:
        return iso_m.group(0)
    iso = N.parse_meeting_date(s)   # 'held on', ordinals, d/m/Y (day-first), OCR junk
    if iso:
        return iso
    dt = pd.to_datetime(s, errors="coerce")   # last resort, no dayfirst (don't flip ISO)
    return None if pd.isna(dt) else dt.date().isoformat()


def _resolve_source_dates(meeting_meta):
    """Fill meta['meeting_date'] (ISO) per source using, in order: a date in the
    filename, a parseable header/title/narrative phrase, then interpolation
    between sources whose meeting numbers bracket this one. Mutates in place."""
    import bisect
    for m in meeting_meta.values():
        iso = N.date_from_filename(m["source"])
        if not iso:
            for t in m.get("_date_texts", []):
                iso = _norm_date(t)
                if iso:
                    break
        m["meeting_date"] = iso
    # monotonic interpolation from numbered, dated anchors
    anchors = sorted((m["meeting_number"], m["meeting_date"])
                     for m in meeting_meta.values()
                     if m.get("meeting_number") and m.get("meeting_date"))
    if not anchors:
        return
    anums = [a for a, _ in anchors]
    for m in meeting_meta.values():
        if m.get("meeting_date") or not m.get("meeting_number"):
            continue
        i = bisect.bisect_left(anums, m["meeting_number"])
        lo = anchors[i - 1] if i > 0 else None
        hi = anchors[i] if i < len(anchors) else None
        if lo and hi:
            # linear interpolation by meeting number between bracketing anchors
            frac = (m["meeting_number"] - lo[0]) / (hi[0] - lo[0]) if hi[0] != lo[0] else 0
            y = round(int(lo[1][:4]) + frac * (int(hi[1][:4]) - int(lo[1][:4])))
        elif lo:
            y = int(lo[1][:4])
        elif hi:
            y = int(hi[1][:4])
        else:
            continue
        m["meeting_date"] = f"{y}-07-01"        # mid-year placeholder
        m["date_inferred"] = True


def build_tables(records: List[dict]):
    line_rows, att_rows = [], []
    meeting_meta = {}

    for rec in records:
        src = rec.get("_source")
        meta = meeting_meta.setdefault(src, {
            "source": src, "meeting_number": None, "meeting_date": None,
            "fund": None, "title": None, "date_inferred": False,
            "_date_texts": []})
        if rec.get("meeting_number") and not meta["meeting_number"]:
            meta["meeting_number"] = rec["meeting_number"]
        for k in ("meeting_date_text", "meeting_title", "narrative"):
            v = rec.get(k)
            if v:
                meta["_date_texts"].append(str(v))
        if rec.get("fund") and not meta["fund"]:
            meta["fund"] = rec["fund"]
        if rec.get("meeting_title") and not meta["title"]:
            meta["title"] = rec["meeting_title"]

        for it in rec.get("line_items", []):
            dist_canon, dist_level = N.snap_district(it.get("district") or "")
            kind = N.classify_row_kind(it.get("work_text"), it.get("sl_no"),
                                       it.get("district"))
            is_li = kind == "line_item"
            amt = it.get("amount_inr")
            line_rows.append({
                "source": src, "page": rec.get("_page"),
                "sl_no": it.get("sl_no"),
                "district": dist_canon or it.get("district"),
                "district_level": dist_level,
                "department": it.get("department_canon") or it.get("department"),
                "work_text": it.get("work_text"),
                "work_type": it.get("work_type"),
                "disaster_phase": it.get("disaster_phase"),
                "disaster_type": it.get("disaster_type"),
                "classify_confidence": it.get("classify_confidence"),
                "row_kind": kind,
                "is_line_item": is_li,
                "amount_inr": amt,
                "amount_lakh": it.get("amount_lakh"),
                "allocation_inr": amt if is_li else None,
                "amount_outlier": bool(is_li and amt is not None
                                       and amt > config.PER_ITEM_CEILING_INR),
                "amount_raw": it.get("amount_raw"),
                "amount_basis": it.get("amount_basis"),
                "amount_flag": it.get("amount_flag"),
                "fund": rec.get("fund"),
            })
        for a in rec.get("attendees", []):
            att_rows.append({
                "source": src, "name": a.get("name"),
                "designation": a.get("designation"),
                "department": N.canon_department(a.get("department") or "")
                              or a.get("department"),
            })

    LINE_COLS = ["source", "page", "sl_no", "district", "district_level",
                 "department", "work_text", "work_type", "disaster_phase",
                 "disaster_type", "classify_confidence", "row_kind", "is_line_item",
                 "amount_inr", "amount_lakh", "allocation_inr", "amount_outlier",
                 "amount_raw", "amount_basis", "amount_flag", "fund"]
    MEET_COLS = ["source", "meeting_number", "meeting_date", "fund", "title",
                 "date_inferred"]
    ATT_COLS = ["source", "name", "designation", "department"]

    # Resolve one authoritative ISO date per source: filename date -> header
    # text (junk/ordinal tolerant) -> monotonic interpolation by meeting number.
    _resolve_source_dates(meeting_meta)

    meetings = pd.DataFrame(
        [{k: v for k, v in m.items() if k != "_date_texts"}
         for m in meeting_meta.values()], columns=MEET_COLS) \
        if meeting_meta else pd.DataFrame(columns=MEET_COLS)
    if not meetings.empty:
        meetings["meeting_date"] = pd.to_datetime(meetings["meeting_date"],
                                                  errors="coerce")
        meetings["fiscal_year"] = meetings["meeting_date"].dt.date.astype("string").map(
            lambda d: N.fiscal_year(d) if pd.notna(d) else None)
        meetings["year"] = meetings["meeting_date"].dt.year

    line_items = pd.DataFrame(line_rows, columns=None if line_rows else LINE_COLS)
    if not line_items.empty:
        # attach meeting date / FY / year onto every line item
        mm = meetings[["source", "meeting_date", "fiscal_year", "year",
                       "meeting_number", "date_inferred"]] if not meetings.empty else None
        if mm is not None:
            line_items = line_items.merge(mm, on="source", how="left")
    attendees = pd.DataFrame(att_rows, columns=None if att_rows else ATT_COLS)
    return line_items, meetings, attendees


def persist(line_items, meetings, attendees, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    line_items.to_csv(os.path.join(out_dir, "line_items.csv"), index=False)
    meetings.to_csv(os.path.join(out_dir, "meetings.csv"), index=False)
    attendees.to_csv(os.path.join(out_dir, "attendees.csv"), index=False)
    db = os.path.join(out_dir, "sdrf.sqlite")
    with sqlite3.connect(db) as con:
        line_items.to_sql("line_items", con, if_exists="replace", index=False)
        meetings.to_sql("meetings", con, if_exists="replace", index=False)
        attendees.to_sql("attendees", con, if_exists="replace", index=False)
    return db


def from_cache(cache_dir: str):
    return build_tables(list(_iter_cached(cache_dir)))
