"""Helpers for preparing runtime environment directories."""

import os
from pathlib import Path


RUNTIME_ENV = "JSV_RUNTIME_DIR"
LOG_ENV = "JSV_LOG_DIR"
MPL_ENV = "MPLCONFIGDIR"
XDG_CACHE_ENV = "XDG_CACHE_HOME"


def prepare_runtime_dirs():
    """Ensure cache/log directories exist and configure env fallbacks."""
    configured = os.environ.get(RUNTIME_ENV)
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path.home() / ".joint_space_visualizer")
    candidates.append(Path.cwd() / ".joint_space_visualizer")

    base = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".perm_test"
            with test_file.open("wb") as handle:
                handle.write(b"0")
            test_file.unlink(missing_ok=True)
        except OSError:
            continue
        base = candidate
        break

    if base is None:
        raise PermissionError("Unable to create writable runtime directory")

    os.environ[LOG_ENV] = str(base)

    mpl_dir = base / "matplotlib"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ[MPL_ENV] = str(mpl_dir)

    cache_dir = base / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ[XDG_CACHE_ENV] = str(cache_dir)

    (cache_dir / "fontconfig").mkdir(parents=True, exist_ok=True)

    return base
