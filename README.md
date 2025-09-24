Joint Space Visualizer (Standalone)
===================================

A PyQt5 + PyVista application to visualize distances between two 3D surface models using `vtkDistancePolyDataFilter`. Includes snapshot tabs, a side-by-side compare view, decimation, and export utilities.

Quickstart
----------

- Requirements: Python 3.9+ (recommended), macOS/Windows/Linux
- Create venv and install deps:
  - `python -m venv venv && source venv/bin/activate` (Windows: `venv\\Scripts\\activate`)
  - `pip install -r requirements.txt`

Run
---

- `python app/main.py`
- Notes:
  - Headless environments: set `QT_QPA_PLATFORM=offscreen`
  - On some macOS setups you may need `export QT_MAC_WANTS_LAYER=1`

Smoke Test
----------

- `python scripts/smoke_test.py`
- Launches the app offscreen and exits after ~1.5s printing `SMOKE_OK`.

Build (PyInstaller)
-------------------

- `pip install pyinstaller`
- `pyinstaller JointSpaceVisualizer.spec`
- Result under `dist/JointSpaceVisualizer`

Features
--------

- Load STL/PLY/VTK/VTP models (Target/Source)
- Compute point-to-point distance (VTK) with custom LUT
- Visibility/opacity controls; optional decimation
- Save result (VTP/PLY/STL) and color-baked PLY
- Snapshot tabs; side-by-side compare with linked cameras
- Save screenshots (single/compare)

License
-------

- TBD
