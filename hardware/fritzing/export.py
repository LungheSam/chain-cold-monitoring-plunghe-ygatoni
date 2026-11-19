"""Build coldchain.fzz, let Fritzing export it, check every connection, save pictures.

Run:  python export.py
Steps:
1. make_fritzing.py writes coldchain.fzz.
2. Fritzing.exe -svg <folder> opens it and exports breadboard, schematic and PCB views as SVG.
3. check_export.py checks that every wire end and leg really touches the pin it is meant to.
4. Microsoft Edge (headless) turns the breadboard and schematic SVGs into PNGs for the report.
Output goes to output/.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import check_export
import make_fritzing

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "output"
FRITZING_EXE = pathlib.Path(make_fritzing.FRITZING_DIR) / "Fritzing.exe"
EDGE = pathlib.Path(r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")


def svg_size(svg_path):
    import re
    head = re.search(r"<svg[^>]*>", svg_path.read_text(encoding="utf-8", errors="ignore"), re.S).group(0)
    w = float(re.search(r"""\swidth=["']([\d.]+)""", head).group(1))
    h = float(re.search(r"""\sheight=["']([\d.]+)""", head).group(1))
    return w, h


def to_png(svg_path, png_path, width_px):
    """Render an SVG to PNG with headless Edge (white background)."""
    w, h = svg_size(svg_path)
    height_px = int(width_px * h / w) + 2
    html = pathlib.Path(tempfile.gettempdir()) / "coldchain_render.html"
    html.write_text(f'<html><body style="margin:0;background:#fff"><img src="{svg_path.as_uri()}" '
                    f'style="width:{width_px}px;display:block"></body></html>', encoding="utf-8")
    subprocess.run([str(EDGE), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--allow-file-access-from-files", f"--screenshot={png_path}",
                    f"--window-size={width_px},{height_px}", html.as_uri()],
                   check=False, capture_output=True, timeout=120)
    return png_path.exists()


def main():
    sketch = make_fritzing.build()
    fzz = HERE / "coldchain.fzz"
    sketch.save(str(fzz), "coldchain")
    print("1. wrote", fzz.name, "-", len(sketch.items), "parts,", len(sketch.wires), "wire segments")

    work = pathlib.Path(tempfile.mkdtemp(prefix="fritzing_export_"))
    shutil.copy(fzz, work / fzz.name)
    print("2. Fritzing export (about 30 s) ...")
    subprocess.run([str(FRITZING_EXE), "-svg", str(work)], check=False, timeout=300)
    OUT.mkdir(exist_ok=True)
    for view in ("breadboard", "schematic", "pcb"):
        src = work / f"coldchain_{view}.svg"
        if not src.exists():
            sys.exit(f"Fritzing did not export {src.name}")
        shutil.copy(src, OUT / src.name)

    print("3. connection check")
    bad = check_export.main(str(fzz), str(OUT / "coldchain_breadboard.svg"))

    if EDGE.exists():
        to_png(OUT / "coldchain_breadboard.svg", OUT / "coldchain_breadboard.png", 2400)
        to_png(OUT / "coldchain_schematic.svg", OUT / "coldchain_schematic.png", 2000)
        print("4. pictures in", OUT)
    else:
        print("4. Edge not found: no PNGs (the SVGs are in output/)")
    shutil.rmtree(work, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
