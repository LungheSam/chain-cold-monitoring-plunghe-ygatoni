# Hardware

| Folder | Contents | Phase |
|---|---|---|
| `fritzing/` | Breadboard model of the reduced design we build (required for the design review) | wiring list in Phase 2, `.fzz` drawn by hand |
| `freecad/` | Parametric enclosure script `enclosure.py` (FreeCAD 1.x, runs with `freecadcmd`) and its exports | 6 |
| `kicad/` | 2-layer carrier PCB that plugs onto the Pi 40-pin header | 7 |

Every dimension or pin-out that is not confirmed from a datasheet or by measurement is marked **VERIFY**.
The list of things to measure is in `docs/decisions.md` ("Things to measure").
