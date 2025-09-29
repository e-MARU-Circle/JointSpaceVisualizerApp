# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

pyvista_datas = collect_data_files('pyvista')
pyvistaqt_datas = collect_data_files('pyvistaqt')
vtk_binaries = collect_dynamic_libs('vtkmodules')
hiddenimports = collect_submodules('pyvista') + collect_submodules('pyvistaqt') + ['PyQt5.sip']


a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=vtk_binaries,
    datas=pyvista_datas + pyvistaqt_datas + [('resources', 'resources')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=False,
    name='JointSpaceVisualizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JointSpaceVisualizer',
)
