#!/usr/bin/env python3
"""Convert GenerateImage outputs (white-bg PNG/JPG) to 512x512 transparent WEBP,
overwriting the exact img/world/* paths listed in pixar_jobs.json.

Usage:
  python3 tools/world_art/process_pixar.py /path/to/raw_dir
  # raw_dir should contain files named by job id or by basename of out path
  # e.g. letters_a.png or a.png matching img/world/letters/a.webp

Also builds /workspace/app/world-shots/contact-sheet.png
"""
from __future__ import annotations
import json, sys, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from rembg import remove

REPO = Path(__file__).resolve().parents[2]
JOBS = json.load(open(Path(__file__).with_name("pixar_jobs.json")))["jobs"]
SIZE = 512
MARGIN = 0.06  # fraction of canvas kept empty around subject

def fit_subject(rgba: Image.Image, size=SIZE, margin=MARGIN) -> Image.Image:
    rgba = rgba.convert("RGBA")
    a = rgba.split()[-1]
    bbox = a.getbbox()
    if not bbox:
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        return out
    subject = rgba.crop(bbox)
    max_side = int(size * (1 - 2 * margin))
    sw, sh = subject.size
    scale = min(max_side / sw, max_side / sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    subject = subject.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(subject, ((size - nw) // 2, (size - nh) // 2), subject)
    return out

def find_raw(raw_dir: Path, job: dict) -> Path | None:
    stem = Path(job["out"]).stem  # a, lion, cameroon-food
    id_ = job["id"]
    cands = [
        raw_dir / f"{id_}.png",
        raw_dir / f"{id_}.jpg",
        raw_dir / f"{id_}.webp",
        raw_dir / f"{stem}.png",
        raw_dir / f"{stem}.jpg",
        raw_dir / f"{stem}.webp",
        raw_dir / Path(job["out"]).name.replace(".webp", ".png"),
    ]
    for c in cands:
        if c.exists():
            return c
    return None

def process_one(raw: Path, dest: Path) -> None:
    im = Image.open(raw).convert("RGB")
    cut = remove(im)
    out = fit_subject(cut)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "WEBP", quality=90, method=6)
    print("OK", dest, out.size)

def checkerboard(size, cell=16):
    im = Image.new("RGBA", (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            c = 230 if ((x // cell) + (y // cell)) % 2 == 0 else 200
            px[x, y] = (c, c, c, 255)
    return im

def contact_sheet(paths, out_path, cols=8, thumb=128):
    n = len(paths)
    rows = (n + cols - 1) // cols
    pad = 4
    label_h = 18
    cell_w, cell_h = thumb + pad * 2, thumb + pad * 2 + label_h
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (245, 245, 248))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except Exception:
        font = ImageFont.load_default()
    for i, p in enumerate(paths):
        r, c = divmod(i, cols)
        x0, y0 = c * cell_w, r * cell_h
        bg = checkerboard(thumb)
        if Path(p).exists():
            im = Image.open(p).convert("RGBA").resize((thumb, thumb), Image.LANCZOS)
            bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB"), (x0 + pad, y0 + pad))
        label = Path(p).name
        draw.text((x0 + pad, y0 + pad + thumb + 2), label[:22], fill=(40, 40, 50), font=font)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "PNG")
    print("contact", out_path, sheet.size)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        # still allow --sheet-only
        if len(sys.argv) == 2 and sys.argv[1] == "--sheet-only":
            pass
        elif len(sys.argv) == 1:
            paths = [REPO / j["out"] for j in JOBS]
            contact_sheet(paths, Path("/workspace/app/world-shots/contact-sheet.png"))
            return
        sys.exit(1)
    if sys.argv[1] == "--sheet-only":
        paths = [REPO / j["out"] for j in JOBS]
        contact_sheet(paths, Path("/workspace/app/world-shots/contact-sheet.png"))
        return
    raw_dir = Path(sys.argv[1])
    missing = []
    for j in JOBS:
        raw = find_raw(raw_dir, j)
        if not raw:
            missing.append(j["out"])
            continue
        process_one(raw, REPO / j["out"])
    if missing:
        print("MISSING raw for", len(missing), "jobs:")
        for m in missing:
            print(" ", m)
        sys.exit(2)
    paths = [REPO / j["out"] for j in JOBS]
    contact_sheet(paths, Path("/workspace/app/world-shots/contact-sheet.png"))
    print("ALL", len(JOBS), "processed")

if __name__ == "__main__":
    main()
