# Enclosure (FreeCAD)

Phase 6. `enclosure.py` will be a parametric Part-workbench script, run headless:

```bash
freecadcmd enclosure.py
```

It will write STEP + STL per printed part, and an editable `.FCStd`, into `exports/`.
On the development laptop FreeCAD 1.1.4 is installed but not on PATH, so run:

```bash
"/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" enclosure.py
```
