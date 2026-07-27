"""
Per-page understanding: turn a page image into a structured record.

Two backends:
  * "openai"    -> a vision model reads the image and returns strict JSON.
                   Recommended for this corpus (scanned, no text layer, dense
                   financial tables that naive OCR scrambles).
  * "tesseract" -> offline fallback. Reliable on born-digital / clean pages,
                   best-effort on financial tables (documented in README).

Results are cached as JSON per page so re-runs are cheap and you never re-pay
for pages you've already processed. Meeting metadata and the current agenda
department are propagated across pages within a document, because a table that
continues onto the next page must inherit the department from its heading.
"""
from __future__ import annotations
import os
import re
import json
import base64
from typing import Optional

import config
import normalize as N
import classify as C
from ingest import Page


PAGE_SCHEMA_HINT = """
Return ONLY valid minified JSON (no markdown fence, no prose) with this shape:
{
 "page_kind": one of ["narrative","financial_table","attendee_list","annexure","mixed","other"],
 "meeting_number": integer or null,
 "meeting_date_text": the raw date phrase from the header if present, else null,
 "meeting_title": string or null,
 "fund": one of ["SDRF","SDMF","NDRF","NDMF","XV FC","CIDF","mixed","unknown"] or null,
 "default_amount_unit": "lakh" | "crore" | "rupees" | null,   // unit the amount column is in
 "agenda_department": canonical department these items belong to (from the agenda heading), or null,
 "line_items": [
   {"sl_no": int|null, "district": string|null, "work_text": full scheme/work description string,
    "amount_raw": the amount cell exactly as printed (keep the decimal), "department": string|null}
 ],
 "attendees": [ {"name": str, "designation": str|null, "department": str|null} ],
 "narrative": short plain-text summary of any non-table decisions on this page
}
Rules:
- Read the amount column EXACTLY; do not round or convert. Preserve the printed decimals.
- If the column header says the unit (e.g. "Amount (Rs. In Lakh)"), set default_amount_unit accordingly.
- If a table continues from a previous page with no header, still extract its rows.
- Put the department from the agenda heading (e.g. "SDRF proposals of Water Resource Department")
  into agenda_department AND into each row's "department".
- attendees: only fill on pages that are clearly a list of members/officers present.
"""


# ---------------------------------------------------------------------------
# OpenAI vision backend
# ---------------------------------------------------------------------------
def _b64_image(path: str) -> str:
    """Base64 JPEG, downscaled to IMAGE_MAX_DIM on the long edge to cut tokens."""
    try:
        from PIL import Image
        import io
        im = Image.open(path)
        w, h = im.size
        scale = config.IMAGE_MAX_DIM / max(w, h)
        if scale < 1.0:
            im = im.convert("RGB").resize((int(w * scale), int(h * scale)))
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


class _RateLimiter:
    """Sliding-60s-window limiter on both requests/min and tokens/min, so we
    pace ourselves *before* OpenAI returns 429 rather than reacting after."""
    def __init__(self, rpm: int, tpm: int):
        self.rpm, self.tpm = rpm, tpm
        self.events = []  # (timestamp, tokens)

    def acquire(self, est_tokens: int):
        import time
        while True:
            now = time.time()
            self.events = [(t, tok) for (t, tok) in self.events if now - t < 60]
            reqs = len(self.events)
            toks = sum(tok for _, tok in self.events)
            if reqs < self.rpm and toks + est_tokens <= self.tpm:
                self.events.append((now, est_tokens))
                return
            # sleep until the oldest event ages out of the window
            sleep = 60 - (now - self.events[0][0]) + 0.05 if self.events else 0.5
            time.sleep(max(sleep, 0.05))


_client = None
_limiter = None


def _get_client():
    global _client, _limiter
    if _client is None:
        from openai import OpenAI
        # max_retries makes the SDK retry 429/5xx with exponential backoff and
        # honour the Retry-After hint automatically.
        _client = OpenAI(api_key=config.OPENAI_API_KEY,
                         max_retries=config.OPENAI_MAX_RETRIES,
                         timeout=config.OPENAI_TIMEOUT)
        _limiter = _RateLimiter(config.OPENAI_RPM, config.OPENAI_TPM)
    return _client


def _extract_openai(page: Page, ctx: dict) -> dict:
    client = _get_client()
    ctx_note = (
        f"Context carried from earlier pages of this same document: "
        f"meeting_number={ctx.get('meeting_number')}, "
        f"meeting_date_text={ctx.get('meeting_date_text')!r}, "
        f"current agenda_department={ctx.get('agenda_department')!r}. "
        f"Use these if this page lacks its own header."
    )
    prompt = (
        "You are extracting structured data from a page of the Assam State "
        "Executive Committee (SEC) disaster-management / SDRF meeting minutes.\n"
        + ctx_note + "\n" + PAGE_SCHEMA_HINT
    )
    img = _b64_image(page.image_path)

    last_err = None
    for attempt in range(config.OPENAI_MAX_RETRIES + 1):
        _limiter.acquire(config.OPENAI_TOKENS_PER_PAGE)  # pace before sending
        try:
            resp = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/jpeg;base64,{img}",
                                       "detail": "high"}},
                    ],
                }],
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:  # 429s the SDK couldn't absorb, transient JSON, etc.
            last_err = e
            wait = _retry_after_seconds(e, attempt)
            if wait is None:
                raise
            import time
            time.sleep(wait)
    raise last_err


def _retry_after_seconds(exc, attempt):
    """Seconds to wait for a retryable error, else None (give up)."""
    import re as _re
    status = getattr(exc, "status_code", None)
    name = exc.__class__.__name__.lower()
    msg = str(exc)
    retryable = status in (429, 500, 502, 503, 504) or "rate_limit" in msg \
        or "ratelimit" in name or "timeout" in name
    if not retryable:
        return None
    # honour an explicit "try again in 369ms / 2.1s" hint if present
    m = _re.search(r"try again in ([\d.]+)\s*(ms|s)", msg)
    if m:
        v = float(m.group(1))
        hinted = v / 1000 if m.group(2) == "ms" else v
        return min(hinted + 0.2, 30)
    return min(2 ** attempt + 0.5, 30)  # exponential backoff, capped


# ---------------------------------------------------------------------------
# Tesseract fallback backend
# ---------------------------------------------------------------------------
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:[,\d]{0,12})?\.\d{1,2})\s*$")
_MEETNO_RE = re.compile(r"(\d{1,3})\s*(?:st|nd|rd|th)\s+.*?(?:SEC|State Executive Committee|meeting)",
                        re.I)


def _ocr(image_path: str, psm: int = 6) -> str:
    import pytesseract
    from PIL import Image
    return pytesseract.image_to_string(Image.open(image_path), config=f"--psm {psm}")


def _extract_tesseract(page: Page, ctx: dict) -> dict:
    text = page.text.strip() or _ocr(page.image_path)
    rec = {
        "page_kind": "other", "meeting_number": ctx.get("meeting_number"),
        "meeting_date_text": None, "meeting_title": None, "fund": None,
        "default_amount_unit": None, "agenda_department": ctx.get("agenda_department"),
        "line_items": [], "attendees": [], "narrative": "",
    }
    low = text.lower()
    # meeting number / title / date
    m = _MEETNO_RE.search(text)
    if m:
        rec["meeting_number"] = int(m.group(1))
        rec["meeting_title"] = m.group(0).strip()[:200]
    dt = N.parse_meeting_date(text)
    if dt:
        rec["meeting_date_text"] = dt
    # unit hint
    if "in lakh" in low or "rs. in lakh" in low or "(lakh" in low:
        rec["default_amount_unit"] = "lakh"
    elif "in crore" in low or "(crore" in low:
        rec["default_amount_unit"] = "crore"
    # fund
    for k in config.FUND_KEYWORDS:
        if k in low:
            rec["fund"] = k.upper().replace("XV FC", "XV FC")
            break
    # agenda department from a heading line
    for line in text.splitlines():
        ll = line.lower()
        if ("proposal" in ll or "agenda" in ll or "department" in ll):
            dep = N.canon_department(line)
            if dep:
                rec["agenda_department"] = dep
                break
    # best-effort table rows: a line ending in a decimal amount, with a district token
    rows = []
    for line in text.splitlines():
        am = _AMOUNT_RE.search(line.strip())
        if not am:
            continue
        dist = N.canon_district(line)
        sl = None
        ms = re.match(r"\s*(\d{1,3})\b", line)
        if ms:
            sl = int(ms.group(1))
        work = line.strip()
        rows.append({"sl_no": sl, "district": dist, "work_text": work,
                     "amount_raw": am.group(1), "department": rec["agenda_department"]})
    if rows:
        rec["page_kind"] = "financial_table"
        rec["line_items"] = rows
    elif "members present" in low or "officers present" in low or "annexure" in low and "name" in low:
        rec["page_kind"] = "attendee_list"
    else:
        rec["page_kind"] = "narrative"
        rec["narrative"] = text[:1500]
    return rec


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_page(page: Page, ctx: dict, backend: str, cache_dir: str,
                 use_cache: bool = True) -> dict:
    cdir = os.path.join(cache_dir, page.source)
    os.makedirs(cdir, exist_ok=True)
    cpath = os.path.join(cdir, f"{page.number:04d}.json")
    if use_cache and os.path.exists(cpath):
        with open(cpath) as f:
            return json.load(f)

    if backend == "openai":
        rec = _extract_openai(page, ctx)
    else:
        rec = _extract_tesseract(page, ctx)

    rec.setdefault("line_items", [])
    rec.setdefault("attendees", [])
    rec["_source"] = page.source
    rec["_page"] = page.number

    # enrich every line item: normalise money + classify (deterministic)
    unit = rec.get("default_amount_unit") or config.DEFAULT_UNIT
    for it in rec["line_items"]:
        amt = N.parse_amount(it.get("amount_raw"), it.get("amount_unit") or unit)
        it["amount_inr"] = amt["inr"]
        it["amount_lakh"] = (None if amt["inr"] is None
                             else round(amt["inr"] / 1e5, 4))
        it["amount_basis"] = amt["basis"]
        it["amount_flag"] = amt["flag"]
        it["district_canon"] = N.canon_district(it.get("district") or "")
        it["department_canon"] = N.canon_department(
            it.get("department") or rec.get("agenda_department") or "")
        it.update(C.classify(it.get("work_text", "")))

    with open(cpath, "w") as f:
        json.dump(rec, f, ensure_ascii=False)
    return rec


def update_context(ctx: dict, rec: dict) -> dict:
    """Carry forward sticky metadata to the next page of the same document."""
    for k in ("meeting_number", "meeting_date_text", "meeting_title", "fund"):
        if rec.get(k):
            ctx[k] = rec[k]
    if rec.get("agenda_department"):
        ctx["agenda_department"] = rec["agenda_department"]
    return ctx
