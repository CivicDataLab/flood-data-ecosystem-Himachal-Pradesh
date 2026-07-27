"""
The six requested analyses. Everything is driven off the tidy `line_items`
table (grain = one allocation) plus `meetings` and `attendees`. Outputs a
markdown report, supporting CSVs and PNG charts. Defensive against empty data.

IMPORTANT semantic note (also in the report): these minutes record amounts
*approved / allocated* by the SEC, not audited *expenditure*. "Utilisation"
is only available where a meeting's Action-Taken-Report states financial
progress, which is sparse. The pipeline therefore reports ALLOCATION robustly
and flags utilisation as partial.
"""
from __future__ import annotations
import os
import textwrap
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _cr(x):
    """rupees -> crore, for readable tables."""
    return None if pd.isna(x) else round(x / 1e7, 3)


def _save_bar(series, title, xlabel, path, rotate=45):
    if series.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.5))
    series.plot(kind="bar", ax=ax, color="#3a6ea5")
    ax.set_title(title); ax.set_ylabel("₹ crore"); ax.set_xlabel(xlabel)
    plt.xticks(rotation=rotate, ha="right"); plt.tight_layout()
    fig.savefig(path, dpi=130); plt.close(fig)
    return path


def run(line_items: pd.DataFrame, meetings: pd.DataFrame, attendees: pd.DataFrame,
        out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    charts = os.path.join(out_dir, "charts"); os.makedirs(charts, exist_ok=True)
    md = ["# Assam SEC / SDRF minutes — analysis\n"]
    li = line_items.copy()
    n_summary = 0
    if "is_line_item" in li.columns and not li.empty:
        n_summary = int((~li["is_line_item"].fillna(True)).sum())
        li = li[li["is_line_item"].fillna(True)].copy()
    has_money = not li.empty and li["amount_inr"].notna().any()

    # ---- coverage / health -------------------------------------------------
    md.append("## 0. Corpus & data coverage\n")
    md.append(f"- Documents parsed: **{meetings['source'].nunique() if not meetings.empty else 0}**")
    if not meetings.empty:
        yr = meetings.dropna(subset=["year"])
        if not yr.empty:
            md.append(f"- Meeting date range: **{int(yr['year'].min())}–{int(yr['year'].max())}**")
        md.append(f"- Meetings with a parseable date: "
                  f"**{meetings['meeting_date'].notna().sum()}/{len(meetings)}**")
    md.append(f"- Allocation line-items extracted: **{len(li)}**")
    if n_summary:
        md.append(f"- Summary/total/header rows excluded from sums: **{n_summary}** "
                  f"(see `row_kind` in `line_items.csv`)")
    if has_money and "amount_outlier" in li.columns:
        nout = int(li["amount_outlier"].fillna(False).sum())
        if nout:
            md.append(f"- Line-items above the per-item ceiling flagged for review: "
                      f"**{nout}** (`amount_outlier=True`)")
    if has_money:
        md.append(f"- Total allocation captured: **₹{_cr(li['amount_inr'].sum())} crore**")
        low = (li['classify_confidence'] == 'low').mean() if 'classify_confidence' in li else 0
        md.append(f"- Line-items with low-confidence auto-classification: **{low:.0%}** "
                  f"(review these before quoting work-type/phase splits)")
        if 'amount_flag' in li:
            nflag = li['amount_flag'].notna().sum()
            if nflag:
                md.append(f"- Line-items with **amount_flag set: {nflag}** — these had "
                          f"an ambiguous unit (bare 6+ digit value, or a comma-grouped "
                          f"value < ₹1000) and were read as rupees; verify against the "
                          f"source PDF. Filter `amount_flag` in `line_items.csv`.")
    md.append("")

    # ---- 1. spending over the years ---------------------------------------
    md.append("## 1. Spending patterns over time\n")
    if has_money and "year" in li:
        by_year = li.dropna(subset=["year"]).groupby("year")["amount_inr"].sum()
        cov = li.dropna(subset=["year"]).groupby("year")["source"].nunique()
        tbl = pd.DataFrame({"allocation_cr": by_year.map(_cr),
                            "meetings_with_data": cov}).reset_index()
        tbl.to_csv(os.path.join(out_dir, "01_spend_by_year.csv"), index=False)
        _save_bar(by_year.map(_cr), "Allocation approved by year", "year",
                  os.path.join(charts, "01_spend_by_year.png"))
        md.append(_table(tbl))
        md.append("\n> Caveat: yearly totals reflect *which meetings approved money*, "
                  "not a steady budget series — SDRF approval meetings are irregular and "
                  "some years have none. Treat gaps as missing data, not zero spend.")
    else:
        md.append("_No money-bearing tables were parsed, so a time series cannot be built._")
    md.append("")

    # ---- 2. district & department -----------------------------------------
    md.append("## 2. District & department analysis (allocation)\n")
    if has_money:
        by_dist = (li.dropna(subset=["district"]).groupby("district")["amount_inr"]
                   .sum().sort_values(ascending=False))
        by_dept = (li.dropna(subset=["department"]).groupby("department")["amount_inr"]
                   .sum().sort_values(ascending=False))
        by_dist.map(_cr).to_csv(os.path.join(out_dir, "02_by_district.csv"))
        by_dept.map(_cr).to_csv(os.path.join(out_dir, "02_by_department.csv"))
        _save_bar(by_dist.head(15).map(_cr), "Top districts by allocation", "district",
                  os.path.join(charts, "02_by_district.png"))
        _save_bar(by_dept.head(15).map(_cr), "Allocation by department", "department",
                  os.path.join(charts, "02_by_department.png"))
        md.append("**Top districts (₹ crore):**\n")
        md.append(_table(by_dist.head(10).map(_cr).reset_index()
                         .rename(columns={"amount_inr": "allocation_cr"})))
        md.append("\n**By department (₹ crore):**\n")
        md.append(_table(by_dept.map(_cr).reset_index()
                         .rename(columns={"amount_inr": "allocation_cr"})))
        md.append("\n> Utilisation vs allocation: the minutes record *approved allocations*. "
                  "Actual fund **utilisation/expenditure** appears only sporadically inside "
                  "Action-Taken-Reports and is not a structured column — so a clean "
                  "allocation-vs-utilisation comparison is **not** reliably available from "
                  "this corpus. Allocation is reported here; utilisation is partial at best.")
    else:
        md.append("_No allocation tables parsed._")
    md.append("")

    # ---- 3. work types -----------------------------------------------------
    md.append("## 3. Types of work\n")
    if not li.empty:
        wt = li.groupby("work_type").agg(items=("work_text", "size"),
                                         allocation_cr=("amount_inr", lambda s: _cr(s.sum())))
        wt = wt.sort_values("allocation_cr", ascending=False)
        wt.to_csv(os.path.join(out_dir, "03_work_types.csv"))
        if has_money:
            _save_bar(wt["allocation_cr"].dropna(), "Allocation by work type", "work type",
                      os.path.join(charts, "03_work_types.png"))
        md.append(_table(wt.reset_index()))
        # work type x department cross-tab (counts) for the tagging requirement
        if li["department"].notna().any():
            ct = pd.crosstab(li["work_type"], li["department"])
            ct.to_csv(os.path.join(out_dir, "03_worktype_by_department.csv"))
            md.append("\n_(work-type × department cross-tab saved to "
                      "`03_worktype_by_department.csv`)_")
    md.append("")

    # ---- 4. stakeholder analysis ------------------------------------------
    md.append("## 4. Stakeholder / attendance analysis\n")
    if not attendees.empty:
        freq = attendees.groupby(["name"]).size().sort_values(ascending=False)
        dept = attendees.dropna(subset=["department"]).groupby("department").size() \
            .sort_values(ascending=False)
        freq.to_csv(os.path.join(out_dir, "04_attendee_frequency.csv"))
        dept.to_csv(os.path.join(out_dir, "04_attendance_by_department.csv"))
        md.append(f"- Distinct attendees identified: **{attendees['name'].nunique()}** "
                  f"across **{attendees['source'].nunique()}** meetings")
        md.append("\n**Most frequent attendees:**\n")
        md.append(_table(freq.head(15).reset_index().rename(columns={0: "meetings"})))
        md.append("\n**Departments represented (by attendance count):**\n")
        md.append(_table(dept.head(15).reset_index().rename(columns={0: "appearances"})))
    else:
        md.append("_No attendee lists were parsed. These live in annexures "
                  "('Annexure I' / 'annexed at A'); coverage depends on whether those "
                  "annexure pages are included in each document._")
    md.append("")

    # ---- 5. disaster phase -------------------------------------------------
    md.append("## 5. Disaster-management phase split\n")
    if not li.empty:
        ph = li.groupby("disaster_phase").agg(
            items=("work_text", "size"),
            allocation_cr=("amount_inr", lambda s: _cr(s.sum())))
        ph.to_csv(os.path.join(out_dir, "05_phase_split.csv"))
        if has_money:
            _save_bar(ph["allocation_cr"].dropna(),
                      "Allocation by disaster phase", "phase",
                      os.path.join(charts, "05_phase_split.png"))
        md.append(_table(ph.reset_index()))
        md.append("\n> Phase labels are inferred from work descriptions with a keyword "
                  "rubric (preparedness / mitigation / response-repair-restoration). "
                  "Many SDRF items are 'Immediate Measures' which are inherently "
                  "response/restoration; genuinely preventive 'mitigation' spend is the "
                  "harder, more ambiguous bucket — verify low-confidence rows.")
    md.append("")

    # ---- 5b. disaster type --------------------------------------------------
    md.append("## 5b. Disaster type (notified hazards)\n")
    if not li.empty and "disaster_type" in li.columns:
        dt = li.groupby("disaster_type").agg(
            items=("work_text", "size"),
            allocation_cr=("amount_inr", lambda s: _cr(s.sum())))
        dt = dt.sort_values("allocation_cr", ascending=False)
        dt.to_csv(os.path.join(out_dir, "05b_disaster_type.csv"))
        md.append(_table(dt.reset_index()))
        md.append("\n> Disaster type is inferred from each row's text against the "
                  "SDRF/NDRF notified-disaster list plus Assam's locally-notified "
                  "hazards (storm/Bordoisila, river erosion, lightning). Rows whose "
                  "text names no hazard (e.g. a bare school name) fall in "
                  "'Unspecified / Multi-hazard'; the hazard there sits in the table "
                  "header/narrative, not the row.")
    md.append("")

    # ---- 6. institutional shift -------------------------------------------
    md.append("## 6. How priorities shifted over time\n")
    if has_money and "year" in li and li["year"].notna().any():
        piv = li.dropna(subset=["year"]).pivot_table(
            index="year", columns="disaster_phase", values="amount_inr",
            aggfunc="sum", fill_value=0)
        share = piv.div(piv.sum(axis=1), axis=0)
        share.to_csv(os.path.join(out_dir, "06_phase_share_by_year.csv"))
        fig, ax = plt.subplots(figsize=(9, 4.5))
        share.plot(kind="area", stacked=True, ax=ax, cmap="viridis")
        ax.set_title("Share of allocation by phase over time")
        ax.set_ylabel("share"); plt.tight_layout()
        fig.savefig(os.path.join(charts, "06_phase_share.png"), dpi=130); plt.close(fig)
        md.append("_Phase share by year saved to `06_phase_share_by_year.csv` "
                  "and `charts/06_phase_share.png`._")
        wt_piv = li.dropna(subset=["year"]).pivot_table(
            index="year", columns="work_type", values="amount_inr",
            aggfunc="sum", fill_value=0)
        wt_piv.div(wt_piv.sum(axis=1), axis=0).to_csv(
            os.path.join(out_dir, "06_worktype_share_by_year.csv"))
        md.append("_Work-type share by year saved to `06_worktype_share_by_year.csv`._")
    else:
        md.append("_Need dated, money-bearing items across multiple years; not enough "
                  "parsed to chart a shift._")
    md.append("")

    report = "\n".join(md)
    with open(os.path.join(out_dir, "REPORT.md"), "w") as f:
        f.write(report)
    return report


def _table(df: pd.DataFrame) -> str:
    try:
        return df.to_markdown(index=False)
    except Exception:
        return "```\n" + df.to_string(index=False) + "\n```"
