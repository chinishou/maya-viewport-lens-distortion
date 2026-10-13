# SPDX-License-Identifier: LGPL-3.0-or-later
"""STMap path, resolution warnings and UI callbacks."""
from __future__ import annotations

from maya import cmds
import lens_core as core
from stmap_io import STMapInfo, comparison_size


def confirm_resolution(path: str) -> bool:
    info: STMapInfo = core.validate_stmap(path)
    window_name, width, height = comparison_size(info)
    render_width: int = cmds.getAttr('defaultResolution.width')
    render_height: int = cmds.getAttr('defaultResolution.height')
    if (width, height) == (render_width, render_height):
        return True

    choice: str = cmds.confirmDialog(
        title='STMap resolution warning',
        message=(f'{window_name}: {width} x {height}\n'
                 f'Render Settings: {render_width} x {render_height}\n\n'
                 'The resolutions differ. Load this STMap anyway?'),
        button=['Continue', 'Cancel'], defaultButton='Continue',
        cancelButton='Cancel', dismissString='Cancel', icon='warning',
    )
    return choice == 'Continue'


def show() -> None:
    """UI entry point."""
    core.plugin_load_check()
    # Capture the model panel before the UI takes focus.
    panel: str = core.active_panel()
    name: str = "stmapLensWindow"
    if cmds.window(name, exists=True):
        cmds.deleteUI(name)
    cmds.window(name, title="STMap Lens Distortion", widthHeight=(480, 150))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(label="Raw float EXR / R=U, G=V / full viewport map domain")
    field: str = cmds.textFieldButtonGrp(label="STMap", buttonLabel="Browse",
                                         text=core.get_stmap_path())

    def update_btns_states(*_: object) -> None:
        active: bool = core.is_enabled(panel)
        has_path: bool = bool(cmds.textFieldButtonGrp(field, query=True, text=True).strip())
        cmds.button(enable_button, edit=True, enable=has_path and not active)
        cmds.button(disable_button, edit=True, enable=active)
        cmds.textFieldButtonGrp(field, edit=True, enable=not active)

    def browse(*_: object) -> None:
        paths: list[str] | None = cmds.fileDialog2(fileMode=1, fileFilter="EXR (*.exr)")
        if paths:
            cmds.textFieldButtonGrp(field, edit=True, text=paths[0])
            update_btns_states()

    def enable_btn_clicked(*_: object) -> None:
        try:
            path: str = cmds.textFieldButtonGrp(field, query=True, text=True)
            if confirm_resolution(path):
                core.enable(path, panel)
        finally:
            update_btns_states()

    def disable_btn_clicked(*_: object) -> None:
        try:
            core.disable(panel)
        finally:
            update_btns_states()

    enable_button: str = cmds.button(label="Enable on viewport", command=enable_btn_clicked, enable=False)
    disable_button: str = cmds.button(label="Disable", command=disable_btn_clicked, enable=False)
    cmds.textFieldButtonGrp(field, edit=True, buttonCommand=browse, textChangedCommand=update_btns_states)
    update_btns_states()
    cmds.showWindow(name)
