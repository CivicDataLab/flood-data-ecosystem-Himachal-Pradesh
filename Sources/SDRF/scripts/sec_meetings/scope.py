"""
Date-scoped file selection.

The meeting date is NOT in the filename for most files, and OCR'd text contains
many distractor dates, so we resolve each file's date by precedence:

  1. date embedded in the filename            (e.g. ..._6_12_2022)      -> 'filename'
  2. date anchored to 'held on ...' on page 1  (cheap 1-page OCR)        -> 'header'
  3. interpolation from meeting-number anchors (monotonic in time)       -> 'inferred'

Only page 1 (occasionally page 2) is OCR'd here, so selection is cheap and
runs before the expensive full extraction. Files whose date can't be pinned and
that sit on the range boundary are marked 'uncertain' and INCLUDED by default
(better to over-include and let full extraction confirm than to silently drop).
"""
from __future__ import annotations
import os
import re
import bisect
from dataclasses import dataclass
from typing import List, Optional

import ingest
import normalize as N


@dataclass
class Selected:
    path: str
    meeting_number: Optional[int]
    date: Optional[str]      # ISO
    year: Optional[int]
    source: str              # how the date was derived
    in_range: bool
    note: str = ""


def _meeting_number(name: str) -> Optional[int]:
    m = re.match(r"(\d+)", os.path.basename(name))
    return int(m.group(1)) if m else None


def _page1_date(path: str, workdir: str) -> Optional[str]:
    try:
        pages = ingest.load_pages(path, workdir)
    except Exception:
        return None
    import pytesseract
    from PIL import Image
    for p in pages[:2]:
        txt = p.text.strip() or pytesseract.image_to_string(
            Image.open(p.image_path), config="--psm 4")
        d = N.parse_meeting_date(txt)
        if d:
            return d
    return None


def resolve_dates(input_dir: str, workdir: str) -> List[Selected]:
    paths = ingest.discover_inputs(input_dir)
    prelim = []
    # pass A: filename + header dates
    for path in paths:
        name = os.path.basename(path)
        mno = _meeting_number(name)
        d = N.date_from_filename(name)
        src = "filename" if d else None
        if not d:
            d = _page1_date(path, workdir)
            src = "header" if d else None
        prelim.append(Selected(path, mno, d, int(d[:4]) if d else None, src or "",
                               False))

    # pass B: interpolate undated files from meeting-number anchors.
    # First quarantine anchors whose date breaks meeting-number monotonicity
    # (meeting numbers increase with time), so one bad OCR date can't poison
    # the interpolation for its neighbours.
    cand = sorted(((s.meeting_number, s.date, s) for s in prelim
                   if s.meeting_number and s.date), key=lambda x: x[0])
    trusted, last_year = [], None
    for mno, d, s in cand:
        y = int(d[:4])
        if last_year is not None and y < last_year:       # non-decreasing by year
            s.note = (s.note + f"; date {d} breaks chronological order "
                      f"-> quarantined, review").strip("; ")
            continue
        trusted.append((mno, d))
        last_year = max(last_year or y, y)
    anchors = trusted
    anums = [a for a, _ in anchors]
    for s in prelim:
        if s.date or not s.meeting_number or not anchors:
            continue
        i = bisect.bisect_left(anums, s.meeting_number)
        lo = anchors[i - 1] if i > 0 else None
        hi = anchors[i] if i < len(anchors) else None
        # infer a year from the nearest bounding anchors
        if lo and hi:
            y = (int(lo[1][:4]) + int(hi[1][:4])) // 2
        elif lo:
            y = int(lo[1][:4])
        elif hi:
            y = int(hi[1][:4])
        else:
            y = None
        s.year = y
        s.source = "inferred"
        s.note = (f"between mtg {lo[0]}({lo[1][:4]}) and "
                  f"{hi[0]}({hi[1][:4]})") if lo and hi else "open-ended bound"
    return prelim


def select_range(input_dir: str, workdir: str, year_from: int, year_to: int
                 ) -> List[Selected]:
    items = resolve_dates(input_dir, workdir)
    for s in items:
        if s.year is None:
            s.in_range = False
            s.note = (s.note + "; no date -> excluded, review manually").strip("; ")
        else:
            s.in_range = year_from <= s.year <= year_to
            # widen the net: an inferred year on the boundary is kept for review
            if not s.in_range and s.source == "inferred" and \
               (year_from - 1 <= s.year <= year_to + 1):
                s.in_range = True
                s.note = (s.note + "; boundary-inferred, included for review").strip("; ")
    return items
