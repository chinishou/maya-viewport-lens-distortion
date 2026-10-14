# SPDX-License-Identifier: LGPL-3.0-or-later
"""Drag this file into Maya's viewport to unregister this installation."""
from __future__ import annotations

from pathlib import Path
import sys


def uninstall() -> None:
    """Remove the user module registration without deleting the source folder."""
    from maya import cmds

    root: Path = Path(__file__).resolve().parent
    module_file: Path = (Path(cmds.internalVar(userAppDir=True))/'modules'
                         /'maya-viewport-lens-distortion.mod')
    expected: str = (root/'maya-viewport-lens-distortion.mod').read_text(encoding='utf-8')
    expected = expected.replace('0.1.0 .', f'0.1.0 {root.as_posix()}', 1)
    # Another checkout may have replaced the registration. Do not uninstall it.
    if module_file.exists() and module_file.read_text(encoding='utf-8').strip() != expected.strip():
        raise RuntimeError(f'Module registration differs from this installation: {module_file}')

    entry: Path = (root/'plugin/lens_distortion.py').resolve()
    # Only unload this exact entry, never another plug-in with the same name.
    # https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/pluginInfo.html
    for plugin in cmds.pluginInfo(query=True, listPlugins=True) or []:
        if Path(cmds.pluginInfo(plugin, query=True, path=True)).resolve() == entry:
            cmds.pluginInfo(plugin, edit=True, autoload=False)
            cmds.pluginInfo(savePluginPrefs=True)
            # No force: if Maya cannot unload safely, leave registration in place.
            cmds.unloadPlugin(plugin)

    override_module = sys.modules.get('lens_override')
    if (override_module is not None
            and Path(getattr(override_module, '__file__', '')).resolve() == root/'plugin/lens_override.py'):
        if cmds.window('stmapLensWindow', exists=True):
            cmds.deleteUI('stmapLensWindow')
    module_file.unlink(missing_ok=True)
    # Do not mutate sys.path here: Maya's drag handler owns a temporary entry.
    print('Lens Distortion uninstalled. Restart Maya to clear session search paths.')
    print('Source files are unchanged. Remove any paths you manually added to Maya.env yourself.')


def onMayaDroppedPythonFile(*args: object) -> None:
    """Maya's Python drag-and-drop entry point."""
    uninstall()


if __name__ == '__main__':
    uninstall()
