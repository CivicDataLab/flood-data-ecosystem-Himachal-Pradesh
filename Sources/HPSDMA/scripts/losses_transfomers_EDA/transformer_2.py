# save as transform_flood_losses.py
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


# ── CONFIG ──────────────────────────────────────────────────────────────────────

ROOT = Path.cwd()

FLOOD_LOSS_FOLDER = ROOT / r"Sources\HPSDMA\data\losses-and-damages\Loss Data\flood_losses"
OUTPUT_FOLDER     = ROOT / r"Sources\HPSDMA\data\variables\losses-and-damages"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# Map each file prefix to the indicators we want from that file
COLUMNS_MAP: Dict[str, List[str]] = {
    "municipal": ["internalwatersupply", "electricwires", "Electricpoles", "Roadlength", "streetlights"],
    "health":    ["health_centres_lost", "health_amount"],
    "cattle":    ["total_livestock_loss"],
    "human":     ["person_dead", "person_major_injury", "person_missing"],
    "education": ["schools_damaged", "economic_loss"],
    "structure": ["structure_lost"],
    "economic":  ["economic_loss", "amount"],
}

# Heuristic: values in [0, LAKH_THRESHOLD] are assumed to be in lakh and will be scaled to rupees
LAKH_THRESHOLD = 10_000

DATE_COL = "incidentdate"
ID_COL_OLD = "tehsil_best_object_id"
ID_COL = "object_id"


# ── LOGGING ─────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ── HELPERS ─────────────────────────────────────────────────────────────────────

def discover_input_files(folder: Path) -> List[Path]:
    files = sorted(folder.glob("*_flood_geocoded*.csv"))
    logger.info("Found %d files in %s", len(files), folder)
    return files


def parse_prefix(path: Path) -> str:
    """
    Determine the loss-type prefix from the filename.
    Expected pattern: <prefix>_flood_geocoded*.csv
    """
    return path.stem.split("_")[0].lower()


def normalize_financials(df: pd.DataFrame, cols: List[str]) -> None:
    """
    Convert financial columns from lakh to rupees when values look like lakh.
    Operates in place.
    """
    for col in cols:
        if col not in df.columns:
            continue
        if col in {"amount", "economic_loss"}:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            mask = df[col].between(0, LAKH_THRESHOLD)
            df.loc[mask, col] *= 100_000  # lakh → rupees


def _clean_date_column(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """
    Standardize and parse date column in-place:
      - strip whitespace
      - treat ''/nan/None as missing
      - parse with flexible parser (accepts YYYY-MM-DD, DD-MM-YYYY, etc.)
      - drop rows where date is missing or unparsable
    """
    # Ensure string and strip
    df[date_col] = df[date_col].astype(str).str.strip()

    # Normalize common empties to NA
    empties = {"", "nan", "NaN", "None", "NULL", "NaT"}
    df.loc[df[date_col].isin(empties), date_col] = pd.NA

    # Drop missing prior to parsing
    before_drop_na = len(df)
    df = df.dropna(subset=[date_col])
    dropped_missing = before_drop_na - len(df)

    # Flexible parsing; dayfirst=True safely handles DD-MM-YYYY and
    # still parses ISO YYYY-MM-DD correctly
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)

    before_drop_nat = len(df)
    df = df.dropna(subset=[date_col])
    dropped_unparsable = before_drop_nat - len(df)

    return df, dropped_missing, dropped_unparsable


def load_and_prepare_file(path: Path, indicators: List[str]) -> Optional[pd.DataFrame]:
    """
    Read a single CSV, clean, filter, parse date, normalize, and aggregate
    by (object_id, timeperiod). Returns None if nothing usable.
    """
    try:
        df = pd.read_csv(path)
    except Exception as e:
        logger.warning("Failed to read %s: %s", path.name, e)
        return None

    # Standardize ID column
    if ID_COL not in df.columns and ID_COL_OLD in df.columns:
        df = df.rename(columns={ID_COL_OLD: ID_COL})

    # Require ID and date columns
    if ID_COL not in df.columns or DATE_COL not in df.columns:
        logger.warning("%s missing required columns; skipping.", path.name)
        return None

    # Select only the available indicators from this file
    present_inds = [c for c in indicators if c in df.columns]
    if not present_inds:
        logger.warning("%s none of the expected indicators are present; skipping.", path.name)
        return None

    # Keep only relevant columns
    keep = [ID_COL, DATE_COL] + present_inds
    df = df.loc[:, keep].copy()

    # Clean/parse date column (skip rows with missing/unparsable dates)
    df, dropped_missing, dropped_unparsable = _clean_date_column(df, DATE_COL)
    if len(df) == 0:
        logger.warning(
            "%s has no rows with a valid %s (dropped %d missing, %d unparsable); skipping.",
            path.name, DATE_COL, dropped_missing, dropped_unparsable
        )
        return None

    # Build timeperiod (YYYY_MM)
    df["timeperiod"] = df[DATE_COL].dt.strftime("%Y_%m")

    # Ensure numeric for all indicators we’ll aggregate
    for col in present_inds:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Normalize financial columns
    normalize_financials(df, present_inds)

    # Aggregate
    agg = (
        df.groupby([ID_COL, "timeperiod"], as_index=False)[present_inds]
          .sum(min_count=1)  # keep NaN if all are NaN in a group
    )

    if len(agg) == 0:
        return None

    return agg


def write_indicator_monthly(indicator: str, chunks: List[pd.DataFrame], output_root: Path) -> int:
    """
    Concatenate chunks for a single indicator, then write one CSV per timeperiod.
    Returns the number of files written.
    """
    if not chunks:
        return 0

    df_all = pd.concat(chunks, ignore_index=True)

    if indicator not in df_all.columns:
        return 0

    ind_folder = output_root / indicator
    ind_folder.mkdir(parents=True, exist_ok=True)

    files_written = 0
    for tp, grp in df_all.groupby("timeperiod"):
        out_path = ind_folder / f"{indicator}_{tp}.csv"
        out = grp[[ID_COL, indicator]].copy()
        out.to_csv(out_path, index=False)
        files_written += 1

    return files_written


# ── MAIN ────────────────────────────────────────────────────────────────────────

def main() -> None:
    files = discover_input_files(FLOOD_LOSS_FOLDER)
    if not files:
        logger.error("No files found. Check the folder path or filename pattern.")
        return

    # Collect all distinct indicators from the mapping
    all_indicators = set().union(*COLUMNS_MAP.values())
    indicator_buckets: Dict[str, List[pd.DataFrame]] = {ind: [] for ind in all_indicators}

    total_files = 0
    usable_files = 0

    for path in files:
        total_files += 1
        prefix = parse_prefix(path)

        if prefix not in COLUMNS_MAP:
            logger.info("Skipping file with unknown prefix '%s': %s", prefix, path.name)
            continue

        indicators = COLUMNS_MAP[prefix]
        logger.info("Processing %s → indicators: %s", path.name, indicators)

        agg = load_and_prepare_file(path, indicators)
        if agg is None:
            continue

        usable_files += 1
        # Stash per-indicator slices
        for col in indicators:
            if col in agg.columns:
                indicator_buckets[col].append(agg[[ID_COL, "timeperiod", col]].copy())

    logger.info("Processed %d files (%d usable).", total_files, usable_files)

    # Write out monthly CSVs per indicator
    written_total = 0
    for ind, chunks in indicator_buckets.items():
        n = write_indicator_monthly(ind, chunks, OUTPUT_FOLDER)
        if n > 0:
            logger.info("Wrote %d files for indicator '%s'.", n, ind)
            written_total += n

    if written_total == 0:
        logger.warning("No indicator files were written. Check input data and mappings.")
    else:
        logger.info("Completed. Total files written: %d", written_total)


if __name__ == "__main__":
    main()
