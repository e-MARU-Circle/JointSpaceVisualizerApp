from PyInstaller.utils.hooks.qt import QtLibraryInfo

_ALLOWED_PLUGIN_TYPES = {
    "platforms",
    "platforms/darwin",
    "styles",
    "imageformats",
    "iconengines",
}


def _collect_plugins_filtered(self, plugin_type):
    if plugin_type not in _ALLOWED_PLUGIN_TYPES:
        return []
    return self._jsv_original_collect_plugins(plugin_type)


if not hasattr(QtLibraryInfo, "_jsv_original_collect_plugins"):
    QtLibraryInfo._jsv_original_collect_plugins = QtLibraryInfo.collect_plugins
    QtLibraryInfo.collect_plugins = _collect_plugins_filtered
