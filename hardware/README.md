# Hardware

| Folder | Contents | Phase |
|---|---|---|
| `fritzing/` | Breadboard model of the reduced design we build (required for the design review) | wiring list in Phase 2, `.fzz` drawn by hand |
| `freecad/` | Parametric enclosure script `enclosure.py` (FreeCAD 1.x, runs with `freecadcmd`), STL/STEP/FCStd exports, PNG views, report | 6 (done) |
| `kicad/` | 2-layer carrier PCB (HAT size) generated from a netlist table, ERC/DRC clean, Gerbers/BOM/STEP in `output/` | 7 (done) |

Every dimension or pin-out that is not confirmed from a datasheet or by measurement is marked **VERIFY**.
The list of things to measure is in `docs/decisions.md` ("Things to measure").
