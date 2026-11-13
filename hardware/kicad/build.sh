#!/usr/bin/env bash
# Rebuilds the carrier board from carrier.py and makes every output in output/:
#   schematic (ERC), board (routing + DRC with schematic parity), Gerbers + drill (zipped for the
#   fab house), BOM, pick-and-place, STEP, PDF schematic and 3D renders.
# Run from Git Bash:  cd hardware/kicad && ./build.sh      (about 2 minutes)
set -e
cd "$(dirname "$0")"
K="${KICAD_BIN:-/c/Program Files/KiCad/10.0/bin}"
PY="$K/python.exe"
CLI="$K/kicad-cli.exe"
mkdir -p output/gerbers
rm -f output/gerbers/*

echo "== 1. Schematic"
"$PY" make_schematic.py
"$CLI" sch erc carrier.kicad_sch -o output/erc.rpt --severity-all --exit-code-violations
"$CLI" sch export pdf carrier.kicad_sch -o output/carrier-schematic.pdf

echo "== 2. Board (placement and routing)"
"$PY" make_pcb.py

echo "== 3. DRC (fills the GND zones and saves the board; any error stops the build)"
"$CLI" pcb drc carrier.kicad_pcb --refill-zones --save-board --schematic-parity --severity-error \
    --exit-code-violations -o output/drc-errors.rpt
"$CLI" pcb drc carrier.kicad_pcb --schematic-parity --severity-all -o output/drc.rpt   # warnings too, for reading

echo "== 4. Fabrication files"
"$CLI" pcb export gerbers carrier.kicad_pcb -o output/gerbers/ \
    --layers F.Cu,B.Cu,F.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask
"$CLI" pcb export drill carrier.kicad_pcb -o output/gerbers/ --format excellon --excellon-separate-th \
    --generate-map --map-format gerberx2
"$PY" -c "import shutil; shutil.make_archive('output/carrier-gerbers', 'zip', 'output/gerbers')"
"$CLI" sch export bom carrier.kicad_sch -o output/carrier-bom.csv \
    --fields 'Reference,Value,Footprint,${QUANTITY},Description' --labels 'Refs,Value,Footprint,Qty,Notes' \
    --group-by 'Value,Footprint' --ref-range-delimiter ''
"$CLI" pcb export pos carrier.kicad_pcb -o output/carrier-pos.csv --format csv --units mm --side both     --use-drill-file-origin
"$CLI" pcb export step carrier.kicad_pcb -o output/carrier.step --subst-models --force

echo "== 5. Pictures"
"$CLI" pcb render carrier.kicad_pcb -o output/carrier-top.png --side top --width 1600 --height 1300 --quality high
"$CLI" pcb render carrier.kicad_pcb -o output/carrier-bottom.png --side bottom --width 1600 --height 1300 --quality high
"$CLI" pcb render carrier.kicad_pcb -o output/carrier-3d.png --width 1600 --height 1200 --quality high \
    --rotate '-35,0,25' --zoom 0.9

echo "Done. ERC and DRC reports: output/erc.rpt, output/drc.rpt"
