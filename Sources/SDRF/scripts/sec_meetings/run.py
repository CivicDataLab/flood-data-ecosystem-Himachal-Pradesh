#!/usr/bin/env python3
"""
End-to-end pipeline for Assam SEC / SDRF meeting minutes.

  python run.py --input ./pdfs --out ./output --backend openai
  python run.py --input ./pdfs --out ./output --backend tesseract   # offline
  python run.py --analyze-only --out ./output                       # re-run analyses from cache

Resumable: per-page extraction is cached under <out>/cache, so re-runs skip
work already done (and never re-pay the API). Use --no-cache to force re-extract.
"""
from __future__ import annotations
import os
import sys
import argparse
import tempfile

import config
import ingest
import scope
import reclassify
import extract as X
import aggregate as A
import analyze


def _write_manifest(items, out_dir):
    import csv
    path = os.path.join(out_dir, "selection.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["meeting_number", "year", "date", "date_source",
                    "in_range", "file", "note"])
        for s in sorted(items, key=lambda x: (x.meeting_number is None,
                                              x.meeting_number or 0)):
            w.writerow([s.meeting_number, s.year, s.date, s.source,
                        s.in_range, os.path.basename(s.path), s.note])
    return path


def process(args):
    work = tempfile.mkdtemp(prefix="sdrf_work_")
    cache = os.path.join(args.out, "cache")
    os.makedirs(cache, exist_ok=True)

    if args.from_year or args.to_year:
        fy = args.from_year or 0
        ty = args.to_year or 9999
        items = scope.select_range(args.input, work, fy, ty)
        man = _write_manifest(items, args.out)
        inputs = [s.path for s in items if s.in_range]
        print(f"[+] date filter {fy}-{ty}: selected {len(inputs)}/{len(items)} "
              f"files (manifest: {man})", file=sys.stderr)
    else:
        inputs = ingest.discover_inputs(args.input)

    if args.limit:
        inputs = inputs[: args.limit]
    print(f"[+] {len(inputs)} input files | backend={args.backend} "
          f"| cache={cache}", file=sys.stderr)

    if args.backend == "openai" and not config.OPENAI_API_KEY:
        sys.exit("OPENAI_API_KEY not set. Export it, or use --backend tesseract.")

    all_records = []
    failures = []
    for n, path in enumerate(inputs, 1):
        stem = os.path.splitext(os.path.basename(path))[0]
        print(f"  [{n}/{len(inputs)}] {stem}", file=sys.stderr)
        try:
            pages = ingest.load_pages(path, work)
        except Exception as e:
            print(f"      ! could not open: {e}", file=sys.stderr)
            failures.append((stem, None, f"open: {e}"))
            continue
        ctx = {}
        for pg in pages:
            try:
                rec = X.extract_page(pg, ctx, args.backend, cache,
                                     use_cache=not args.no_cache)
                ctx = X.update_context(ctx, rec)
                all_records.append(rec)
            except Exception as e:
                print(f"      ! page {pg.number} failed: {e}", file=sys.stderr)
                failures.append((stem, pg.number, str(e)[:120]))
    if failures:
        import csv
        fpath = os.path.join(args.out, "failed_pages.csv")
        with open(fpath, "w", newline="") as f:
            csv.writer(f).writerows([("file", "page", "error"), *failures])
        print(f"[!] {len(failures)} page(s) failed and were NOT cached. "
              f"Logged to {fpath}. Re-run the SAME command to retry only those "
              f"(cached pages are skipped).", file=sys.stderr)
    return all_records


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="directory of input .pdf (zip-archive) files")
    ap.add_argument("--out", default="./output", help="output directory")
    ap.add_argument("--backend", default=config.DEFAULT_BACKEND,
                    choices=["openai", "tesseract"])
    ap.add_argument("--model", help="override OpenAI model")
    ap.add_argument("--rpm", type=int, help="max OpenAI requests/min (default 400)")
    ap.add_argument("--tpm", type=int, help="max OpenAI tokens/min budget (default 160000)")
    ap.add_argument("--max-retries", type=int,
                    help="retries per page on 429/5xx (default 8)")
    ap.add_argument("--image-max-dim", type=int,
                    help="downscale page long-edge to N px before upload "
                         "(lower = cheaper/faster, slightly less accurate; default 1568)")
    ap.add_argument("--limit", type=int, help="process only the first N files")
    ap.add_argument("--from-year", type=int,
                    help="only process meetings held in this year or later")
    ap.add_argument("--to-year", type=int,
                    help="only process meetings held in this year or earlier")
    ap.add_argument("--no-cache", action="store_true", help="ignore the page cache")
    ap.add_argument("--analyze-only", action="store_true",
                    help="skip extraction; rebuild tables+analyses from cache "
                         "(uses labels frozen at extraction time)")
    ap.add_argument("--reclassify", action="store_true",
                    help="skip extraction; RE-APPLY normalize+classify over the "
                         "cache using current config (picks up rubric/vocabulary "
                         "edits), then rebuild tables+analyses. No API calls.")
    args = ap.parse_args()
    if args.model:
        config.OPENAI_MODEL = args.model
    if args.rpm:
        config.OPENAI_RPM = args.rpm
    if args.tpm:
        config.OPENAI_TPM = args.tpm
    if args.max_retries is not None:
        config.OPENAI_MAX_RETRIES = args.max_retries
    if args.image_max_dim:
        config.IMAGE_MAX_DIM = args.image_max_dim
    os.makedirs(args.out, exist_ok=True)

    if args.analyze_only or args.reclassify:
        cache = os.path.join(args.out, "cache")
        if not os.path.isdir(cache):
            sys.exit(f"no cache found at {cache} — run extraction first")
        if args.reclassify:
            nf, ni = reclassify.reapply(cache)
            print(f"[+] reclassified {ni} line-items across {nf} cached pages "
                  f"(no API)", file=sys.stderr)
        li, mt, at = A.from_cache(cache)
    else:
        if not args.input:
            sys.exit("--input is required unless --analyze-only is used")
        records = process(args)
        li, mt, at = A.build_tables(records)

    db = A.persist(li, mt, at, args.out)
    print(f"[+] tables -> {args.out} (sqlite: {db})", file=sys.stderr)
    analyze.run(li, mt, at, args.out)
    print(f"[+] report -> {os.path.join(args.out, 'REPORT.md')}", file=sys.stderr)


if __name__ == "__main__":
    main()
