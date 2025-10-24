from PyInstaller.utils.hooks.qt import add_qt_dependencies

hiddenimports, binaries, datas = add_qt_dependencies(__file__)
