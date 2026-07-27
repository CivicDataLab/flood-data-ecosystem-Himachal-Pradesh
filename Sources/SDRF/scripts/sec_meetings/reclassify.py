"""
Re-apply normalisation + classification to the CACHED page extractions, without
calling the extraction backend again.

Use this after you edit the rubric or vocabularies in config.py (work-type rules,
phase rules, district/department aliases, units) or just want to regenerate
labels. It reads each cached page JSON, recomputes the derived fields from the
RAW fields the extractor preserved (work_text, amount_raw, amount_unit, district,
department / agenda_department) using the CURRENT config, and rewrites the cache.

Nothing here hits the network, so it is free and fast. After running, aggregate
+ analyze pick up the new labels automatically.
"""
from __future__ import annotations
import os
import glob
import json

import config
import normalize as N
import classify as C


def reapply(cache_dir: str):
    files = sorted(glob.glob(os.path.join(cache_dir, "*", "*.json")))
    n_files = n_items = 0
    for path in files:
        try:
            with open(path) as f:
                rec = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        unit = rec.get("default_amount_unit") or config.DEFAULT_UNIT
        agenda_dep = rec.get("agenda_department")
        for it in rec.get("line_items", []):
            amt = N.parse_amount(it.get("amount_raw"), it.get("amount_unit") or unit)
            it["amount_inr"] = amt["inr"]
            it["amount_lakh"] = (None if amt["inr"] is None
                                 else round(amt["inr"] / 1e5, 4))
            it["amount_basis"] = amt["basis"]
            it["amount_flag"] = amt["flag"]
            it["district_canon"] = N.canon_district(it.get("district") or "")
            it["department_canon"] = N.canon_department(
                it.get("department") or agenda_dep or "")
            it.update(C.classify(it.get("work_text", "")))
            n_items += 1
        with open(path, "w") as f:
            json.dump(rec, f, ensure_ascii=False)
        n_files += 1
    return n_files, n_items


if __name__ == "__main__":
    import sys
    cache = sys.argv[1] if len(sys.argv) > 1 else "./output/cache"
    nf, ni = reapply(cache)
    print(f"reclassified {ni} line-items across {nf} cached pages in {cache}")
