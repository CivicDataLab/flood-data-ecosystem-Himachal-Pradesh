# Assam SEC / SDRF minutes — extraction & analysis pipeline

A pipeline that turns scanned State Executive Committee (SEC) /
SDRF meeting-minute PDFs into tables, with additional analysis pipelines.

---

## Nature of the Source Documents:

1. **They are image-only.** Every "PDF" in the set is actually a ZIP archive of
   per-page JPEGs + empty `.txt` files. There is **no text layer**, so every
   page must go through OCR or a vision model. 

2. **The format drifts a lot over ~17 years (2009 → 2026):**
   - *Early* (e.g. 1st, 2009): scanned typed policy minutes — narrative +
     qualitative two-column tables, departments named inside "Action:" lines,
     attendees in *Annexure I*.
   - *Mid* (e.g. 27th, 2016): scanned **financial tables**
     `Sl | District | Name of Scheme | Amount (Rs. In Lakh)`; the department is
     in the agenda heading ("SDRF proposals of Water Resource Department").
   - *Recent* (e.g. 55th, 2026): digital eOffice docs, hierarchical
     numbering (55.1, 55.2), departments are mentioned inline.

3. **Financial Units Derivation:** table headers say "Rs. In Lakh"; narratives
   state totals ("approved 29 proposals amounting to Rs.4402.93 Lakh"). The
   normaliser reads the unit and converts everything to a single base (INR float).

---

Because the pages are scanned and the tables are dense, a **vision-capable model
reading the page image** is dramatically more reliable than OCR + regex for:
exact amount cells, keeping columns aligned, carrying the department from the
heading, and reading the rich scheme text used for classification.

- Recommended: OpenAI `gpt-4o-mini` (cheap, vision) or `gpt-4o` for the messiest
  scans. Set `OPENAI_API_KEY`.
- A free **offline `tesseract` backend** is included so the pipeline runs with no
  API key, but on financial tables it is best-effort only (it visibly mis-splits
  rows in testing — see caveat 3). Use it for narrative/attendee pages or a dry run.

The same classification rubric (`config.py`) is given to *both* backends, so an
LLM run and an offline run produce comparable labels.

## Date-range scoping (e.g. 2019–2026)

The meeting date is **not** in most filenames (files are named by meeting
number), and OCR'd minutes are full of distractor dates (the previous meeting
being confirmed, scheme years like "2016-17"). So scoping by year needs real
date resolution, done cheaply *before* full extraction by `scope.py`:

```bash
python run.py --input ./pdfs --out ./output --backend openai \
              --from-year 2019 --to-year 2026
```

This writes `output/selection.csv` (every file, its resolved date, how the date
was derived, in/out of range, and any note) and then extracts + analyses only
the in-range files. Date precedence per file:

1. **filename** date if present (e.g. `..._10_12_2022` -> 2022-12-10) — most reliable;
2. **header** date anchored to the title's "held on ..." phrase (cheap 1-page OCR),
   junk-tolerant (handles `30 November 2018`, `8" October, 2018`, wrapped lines);
3. **inferred** by interpolation between meeting-number anchors (numbers are
   monotonic in time), flagged as such.

A **monotonicity guard** quarantines any header date that breaks meeting-number
order (one bad OCR year can't poison its neighbours' interpolation). Undated
boundary files are kept for review rather than silently dropped.

## Rate limits & resilience (OpenAI 429s)

The vision backend paces itself and recovers from rate limits automatically, so
a `429 ... tokens per min (TPM)` no longer drops pages:

- **Client-side pacer** keeps you under your tier *before* sending — a sliding
  60-second window bounded by `--rpm` (requests/min) and `--tpm` (token budget).
  Defaults (400 RPM, 160 000 TPM) sit just under a 200 000-TPM tier.
- **Automatic backoff**: each page retries on 429/5xx up to `--max-retries`
  (default 8), honouring the API's own "try again in 369 ms" hint, with
  exponential fallback otherwise. The SDK client is also created with matching
  `max_retries`.
- **Image downscaling** (`--image-max-dim`, default 1568 px long edge) cuts the
  tokens per page. Set it lower (e.g. `--image-max-dim 1024`) to roughly halve
  cost/throughput pressure at a small accuracy cost on dense tables.
- **Nothing is silently lost**: a page that still fails after all retries is
  written to `output/failed_pages.csv` and is **not** cached — so re-running the
  exact same command retries only those pages (cached ones are skipped).

Match the flags to your account tier (shown at
platform.openai.com/account/rate-limits). For a 30 000-TPM tier, for example:

```bash
python run.py --input ./pdfs --out ./output --from-year 2019 --to-year 2026 \
              --tpm 24000 --rpm 60 --image-max-dim 1024
```

You can also set them via env vars (`SDRF_OPENAI_TPM`, `SDRF_OPENAI_RPM`,
`SDRF_OPENAI_MAX_RETRIES`, `SDRF_IMAGE_MAX_DIM`).

---

## Cleaning: summary rows, unit correction, district snapping

Raw extraction over-counts and mis-units in three systematic ways; the cleaner
(`clean.py`, also folded into aggregation) addresses each and **keeps every row**
with explanatory columns rather than deleting anything:

1. **Summary / total / header rows** that duplicate the detail beneath them
   (`TOTAL`, a bare department name, `"166 schemes"`, `"SDRF proposals of X
   Department for the year"`). Tagged in `row_kind`
   (`summary_total` / `summary_dept` / `summary_aggregate` / `header_orphan`);
   only `row_kind == line_item` rows feed allocation sums (`allocation_inr`).
2. **Mis-detected table units.** A bare count ≥ `COUNT_AS_RUPEES_THRESHOLD`
   that was multiplied as lakh/crore (e.g. `96500` → ₹965 cr for one footbridge)
   is re-read as rupees; correctly rupee-denominated tables are left untouched.
   Any single line item above `PER_ITEM_CEILING_INR` (₹100 cr) gets
   `amount_outlier=True` for review (this also surfaces genuine large NDRF /
   programme approvals, which are real but worth separating).
3. **District snapping.** `district_canon` resolves OCR spelling variants
   (`Sibsagar`→`SIVASAGAR`) and known towns (`Bilasipara`→`DHUBRI`) to the 35
   Assam districts **spelled exactly as in the standard GeoJSON**
   (`KAMRUP METRO`, `SOUTH SALMARA MANCACHAR`, `CHARAIDEO`, …) so the table joins
   to it directly; `district_level` buckets `state_wide` (all-districts/agency)
   and `unmapped` (a place we won't guess).
4. **Re-classification.** Work type, disaster phase and a new **disaster type**
   are re-derived from each row's text with the current rubric. Disaster phases
   are labelled *Long-term Preparedness / Mitigation / Repair and Restoration*.
   Disaster type follows the SDRF/NDRF notified-disaster list plus Assam's
   locally-notified hazards (storm/Bordoisila, river erosion, lightning).
5. **Department override.** A row whose text names a school (LPS, MES, JBS, MEM,
   H.S., vidyalaya, madrassa, college, …) is re-assigned to **Education** even
   when the agenda context wrongly carried a different department; the original
   is preserved in `department_orig` and the decision in `department_source`.

Clean an existing CSV directly:

```bash
python clean.py line_items.csv line_items_clean.csv
```

Or regenerate clean tables from the cache (also recomputes amounts):

```bash
python run.py --reclassify --out ./output
```

On the full corpus this brought the captured total from ₹47,807 cr (raw, with
double-counting and unit inflation) down to ≈₹11,900 cr of genuine line-item
allocations, with per-year figures in a believable SDRF/SDMF/NDRF range.

---

## Meeting dates in the output tables

Each line item is dated by resolving one ISO date per source document, in order:
filename date (`..._10.12.2022`) → a header/title/narrative phrase parsed with
the junk- and ordinal-tolerant parser (`held on 27th November 2019`,
`January 28, 2026`, clean ISO) → linear interpolation between the meeting
numbers of dated neighbours. Interpolated dates are placeholders (`YYYY-07-01`)
and marked `date_inferred=True` in `meetings.csv` / `line_items.csv` so you can
exclude them from year-by-year analysis.

This resolution runs in aggregation, so if dates look wrong or missing you can
**fix them without re-extracting** — just rebuild from the cache:

```bash
python run.py --analyze-only --out ./output
```

(If many dates still come back inferred, your cache is missing the header text
fields — `meeting_date_text` / `meeting_title` / narrative — and those sources
need re-extraction to recover a real date.)

---

## Amount normalisation (how `amount_inr` is decided)

Amounts are messy: explicit `Cr.`/`lakh` suffixes, `Rs.` prefixes, `/-` endings,
and Indian digit grouping (`17,00,000` = ₹17 lakh). `normalize.parse_amount`
applies one ordered rule and records the decision in `amount_basis`:

1. **explicit unit in the cell** (`178.79 Cr.`, `Rs. 6.00 Cr.`) → the number is a
   *count* in that unit; multiply, and **ignore the page default unit** so the
   multiplier is never applied twice. → `explicit_unit`
2. **comma-grouped value** (`17,00,000`, `Rs.7,15,000/-`) → an *absolute rupee*
   figure; strip separators, **no unit multiplier**. → `comma_grouped_absolute`
3. **bare number with ≥6 integer digits** (`470695.48`) → almost certainly rupees,
   not a lakh count; read as rupees and set `amount_flag=ambiguous_unit_check_source`.
   → `bare_long_assumed_rupees`
4. **small bare number** (`206.10`) → a *count* in the column's unit
   (header/default lakh or crore); multiply. → `count_in_unit`

`line_items.csv` now carries `amount_raw`, `amount_basis` and `amount_flag`.
Filter `amount_flag` to review the genuinely ambiguous cells against the source
PDF (e.g. tables whose header might be "Rs." rather than "Rs. in Lakh").

**To fix amounts in an existing run without re-extracting**, just:

```bash
python run.py --reclassify --out ./output
```

This recomputes `amount_inr`/`amount_lakh` from the cached `amount_raw` using the
rules above — no API calls. (The same `parse_amount` logic should be used wherever
amounts are computed if you have split the pipeline into your own scripts.)

---

## Architecture

```
run.py        CLI orchestrator (resumable; per-page JSON cache)
 ├ scope.py     resolve each file's date & filter to a year range (cheap, 1-page)
 ├ ingest.py    open each zip-archive / real PDF -> page images (+ any text)
 ├ extract.py   page image -> structured JSON  (openai vision | tesseract)
 │               · propagates meeting/department context across pages
 │               · normalises money + classifies each row on the way in
 ├ normalize.py amount→INR, lakh/crore units, district & dept aliases, dates→FY
 ├ classify.py  work_type + disaster_phase (rule-based, confidence-scored)
 ├ aggregate.py per-page records -> line_items / meetings / attendees (+SQLite)
 └ analyze.py   the six analyses -> REPORT.md + CSVs + charts
```

**Grain:** one row per allocation in `line_items.csv` — every downstream number
is a `groupby` on that. `sdrf.sqlite` holds all three tables for ad-hoc SQL.

---

## Usage

```bash
pip install -r requirements.txt          # plus system 'tesseract' for offline mode
export OPENAI_API_KEY=sk-...              # for the recommended vision backend

# full run (vision)
python run.py --input ./pdfs --out ./output --backend openai

# offline dry run, first 5 files only
python run.py --input ./pdfs --out ./output --backend tesseract --limit 5

# re-run only the analyses from the cache (no re-extraction, no API cost)
python run.py --analyze-only --out ./output

# re-apply classification/normalisation after editing config.py rules or the
# fund list, then rebuild tables + report — still no extraction, no API cost
python run.py --reclassify --out ./output
```

### Re-running without re-extracting

Extraction (the API calls) is the expensive step; its per-page output is cached
under `output/cache/`. Two ways to regenerate downstream results for free:

- `--analyze-only` — rebuild `line_items`/`meetings`/`attendees` and the report
  straight from the cache. Fast, but uses the labels **frozen at extraction time**.
- `--reclassify` — re-apply `normalize` + `classify` over the cached raw fields
  using the **current** `config.py` (work-type rules, phase rules, district /
  department aliases, units), rewrite the cache, then rebuild. Use this whenever
  you change the rubric or vocabularies and want those edits reflected. You can
  also run the stage directly: `python reclassify.py ./output/cache`.

Neither touches the network. (Note: the page-level `fund` tag is set during
extraction, so changing `FUND_KEYWORDS` alone is picked up only on re-extraction
or if you extend the reclassify pass to derive fund from `work_text`.)

Outputs in `./output/`: `REPORT.md`, `line_items.csv`, `meetings.csv`,
`attendees.csv`, `sdrf.sqlite`, numbered summary CSVs, and `charts/*.png`.
Per-page extractions are cached in `output/cache/<doc>/<page>.json`; delete a
file there (or pass `--no-cache`) to force re-extraction of just that page.

---

## Recommended workflow for trustworthy numbers

1. Run with the vision backend.
2. Open `line_items.csv`, filter `classify_confidence == 'low'` and any rows
   where `district`/`amount_lakh` look wrong, and correct the cache or a review
   sheet. (Totals/subtotals sneaking in as rows is the classic error — spot them
   as values far larger than neighbours.)
3. Re-run `--analyze-only`. The report regenerates from the corrected cache.

Treat the auto-generated report as a **first pass over OCR'd government scans**,
not an audited financial statement.
___

Assisted-by: Claude: Claude Opus 4.8 
Signed-off-by Saurabh Levin
