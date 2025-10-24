# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.config import CONF
from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)
from PyInstaller.building.datastruct import TOC

import os

CONF['cachedir'] = os.path.join(os.getcwd(), '.pyinstaller-cache')

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
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['scipy'],
    noarchive=False,
    optimize=0,
)

_ALLOWED_QT_PLUGIN_PREFIXES = [
    'PyQt5/Qt5/plugins/platforms/',
    'PyQt5/Qt5/plugins/styles/',
    'PyQt5/Qt5/plugins/imageformats/',
    'PyQt5/Qt5/plugins/iconengines/',
]


def _filter_binaries(entries):
    filtered = []
    for entry in entries:
        dest = entry[0]
        if dest.startswith('PyQt5/Qt5/plugins/'):
            if any(dest.startswith(prefix) for prefix in _ALLOWED_QT_PLUGIN_PREFIXES):
                filtered.append(entry)
        else:
            filtered.append(entry)
    return TOC(filtered)


a.binaries = _filter_binaries(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JointSpaceVisualizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
app = BUNDLE(
    coll,
    name='JointSpaceVisualizer.app',
    icon=None,
    bundle_identifier='jp.ema.JointSpaceVisualizer',
)
