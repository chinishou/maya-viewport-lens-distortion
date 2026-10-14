# SPDX-License-Identifier: LGPL-3.0-or-later
"""Drag this file into Maya's viewport to install the module."""
from __future__ import annotations

from pathlib import Path
import sys


def install() -> None:
    """Register this checkout using Maya's official module description format."""
    from maya import cmds

    root: Path = Path(__file__).resolve().parent
    if not (root/'plugin/lens_distortion.py').is_file():
        raise RuntimeError('Keep install.py in the complete plug-in folder.')
    # internalVar respects MAYA_APP_DIR, redirected Documents and each platform.
    # https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/internalVar.html
    modules: Path = Path(cmds.internalVar(userAppDir=True))/'modules'
    modules.mkdir(parents=True, exist_ok=True)
    description: str = (root/'maya-viewport-lens-distortion.mod').read_text(encoding='utf-8')
    description = description.replace('0.1.0 .', f'0.1.0 {root.as_posix()}', 1)
    (modules/'maya-viewport-lens-distortion.mod').write_text(description, encoding='utf-8')

    # The .mod file supplies this on subsequent startups. Make it usable now too.
    # Maya's executeDroppedPythonFile removes sys.path[0] after this callback;
    # appending preserves its temporary entry and prevents removal of ours.
    plugin_dir: str = str(root/'plugin')
    if plugin_dir not in sys.path:
        sys.path.append(plugin_dir)
    print('Lens Distortion installed. Run this Python code to open the UI:')
    print('import lens_ui\nlens_ui.show()')


def onMayaDroppedPythonFile(*args: object) -> None:
    """Maya's Python drag-and-drop entry point."""
    install()


if __name__ == '__main__':
    install()
