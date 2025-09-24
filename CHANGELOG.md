# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-09-24
- Initialize Git repository for JointSpaceVisualizerStandalone.
- Add CHANGELOG and start `diary/` for progress logging.
- Baseline features in place:
  - Dual-view UI (Source/Result vs Target) with linked cameras
  - Load STL/PLY/VTK/VTP models
  - Compute point-to-point distance via `vtkDistancePolyDataFilter`
  - Custom LUT coloring and scalar bar
  - Visibility/opacity controls for result/target/source
  - Optional decimation (target reduction slider)
  - Save result and colored PLY, and side-by-side screenshot

