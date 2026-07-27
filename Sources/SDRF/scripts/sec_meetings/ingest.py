"""
Ingestion. Each input "PDF" in this corpus is actually a ZIP archive holding
per-page images (N.jpeg), per-page text (N.txt, usually empty for these scans)
and a manifest.json. This module abstracts that away and also falls back to
treating a real PDF as a PDF (rasterising with pdftoppm) so the pipeline works
on either input shape.
"""
from __future__ import annotations
import os
import json
import shutil
import zipfile
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Page:
    number: int
    image_path: str
    text: str            # text layer if present (often "" for scans)
    source: str          # archive/pdf filename (stem)


def _is_zip(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"PK"
    except OSError:
        return False


def _read_zip_pages(path: str, workdir: str) -> List[Page]:
    stem = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(workdir, stem)
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        z.extractall(dest)
    manifest_path = os.path.join(dest, "manifest.json")
    pages: List[Page] = []
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        for p in manifest.get("pages", []):
            img = os.path.join(dest, p["image"]["path"])
            txt_path = os.path.join(dest, p.get("text", {}).get("path", ""))
            text = ""
            if txt_path and os.path.exists(txt_path):
                with open(txt_path, errors="ignore") as tf:
                    text = tf.read()
            pages.append(Page(p["page_number"], img, text, stem))
    else:
        # no manifest: just grab numbered images
        imgs = sorted(
            [f for f in os.listdir(dest) if f.lower().endswith((".jpeg", ".jpg", ".png"))],
            key=lambda x: int("".join(ch for ch in x if ch.isdigit()) or 0),
        )
        for i, name in enumerate(imgs, 1):
            pages.append(Page(i, os.path.join(dest, name), "", stem))
    return pages


def _read_real_pdf(path: str, workdir: str, dpi: int = 200) -> List[Page]:
    stem = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(workdir, stem)
    os.makedirs(dest, exist_ok=True)
    prefix = os.path.join(dest, "page")
    subprocess.run(["pdftoppm", "-jpeg", "-r", str(dpi), path, prefix],
                   check=True, capture_output=True)
    imgs = sorted(f for f in os.listdir(dest) if f.endswith(".jpg"))
    pages = []
    for i, name in enumerate(imgs, 1):
        # try to pull a text layer too (born-digital PDFs)
        try:
            txt = subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), path, "-"],
                                 capture_output=True, text=True, timeout=30).stdout
        except Exception:
            txt = ""
        pages.append(Page(i, os.path.join(dest, name), txt, stem))
    return pages


def load_pages(path: str, workdir: str) -> List[Page]:
    """Return all pages of one input file (zip-archive or real PDF)."""
    if _is_zip(path):
        return _read_zip_pages(path, workdir)
    return _read_real_pdf(path, workdir)


def discover_inputs(input_dir: str) -> List[str]:
    return sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if f.lower().endswith(".pdf")
    )
