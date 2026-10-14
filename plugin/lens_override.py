# SPDX-License-Identifier: LGPL-3.0-or-later
"""Python API 2.0 STMap viewport override.

Reference: https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=MAYA_API_REF_py_ref_python_2api2_2py2_view_render_override_8py_example_html
STMap definition: https://learn.foundry.com/nuke/content/reference_guide/transform_nodes/stmap.html
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maya.api.OpenMaya import MObject

from maya import cmds
from maya.api import OpenMayaRender as R
from stmap_info import STMapInfo, inspect_stmap

NAME: str = "stmapLensDistortion"
_override: LensOverride | None = None


class Target(Enum):
    """Render targets and their Maya texture formats.
    
    https://help.autodesk.com/view/MAYAUL/2016/ENU/?guid=__cpp_ref_namespace_m_h_w_render_html
    
    """

    SCENE_COLOR = ("lensSceneColor", R.MRenderer.kR8G8B8A8_UNORM)
    SCENE_DEPTH = ("lensSceneDepth", R.MRenderer.kD24S8)
    DISTORTED_COLOR = ("lensDistortedColor", R.MRenderer.kR8G8B8A8_UNORM)

    def __init__(self, resource_name: str, raster_format: int) -> None:
        self.resource_name: str = resource_name
        self.raster_format: int = raster_format


def maya_useNewAPI() -> None:
    """Required to use the API 2.0."""
    pass

class LensOverride(R.MRenderOverride):
    """https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_render_override.html
    """
    def __init__(self) -> None:
        super().__init__(NAME)
        self.targets: dict[Target, R.MRenderTarget] = {}
        self.target_size: tuple[int, int] | None = None
        self.shader_instance: R.MShaderInstance | None = None
        self.stmap_texture: R.MTexture | None = None
        self.stmap_path: str = ""
        self.ops: list[R.MRenderOperation] = [Scene(self), Distort(self), Present(self)]

    def uiName(self) -> str:
        return "STMap Lens Distortion"

    def supportedDrawAPIs(self) -> int:
        return R.MRenderer.kOpenGLCoreProfile

    def startOperationIterator(self) -> bool:
        self.index: int = 0
        return True

    def renderOperation(self) -> R.MRenderOperation | None:
        return self.ops[self.index] if self.index < len(self.ops) else None

    def nextRenderOperation(self) -> bool:
        self.index += 1
        return self.index < len(self.ops)

    def setup(self, destination: str) -> None:
        """Prepare GPU resources and shader inputs before the render operations.

        Maya supplies the destination panel name. This override uses the current
        output dimensions rather than querying that panel's on-screen dimensions.
        """
        if self.stmap_texture is None:
            raise RuntimeError("Choose an STMap and enable it from the Lens Distortion UI first")
        manager: R.MRenderTargetManager = R.MRenderer.getRenderTargetManager()
        output_size: tuple[int, int] = R.MRenderer.outputTargetSize()

        # Allocate targets on first use, then update them when output size changes.
        # https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_render_target_manager.html
        if output_size != self.target_size:
            for kind in Target:
                desc: R.MRenderTargetDescription = R.MRenderTargetDescription(
                    kind.resource_name, output_size[0], output_size[1], 1,
                    kind.raster_format, 0, False
                )
                if kind in self.targets:
                    # Resize the existing target without acquiring another one.
                    self.targets[kind].updateDescription(desc)
                else:
                    # First time allocation: acquire a new render target from the manager.
                    target: R.MRenderTarget | None = manager.acquireRenderTarget(desc)
                    if target is None:
                        raise RuntimeError("Unable to allocate lens render target")
                    self.targets[kind] = target
            self.target_size = output_size

        # Cache the shader instance after the first compilation.
        if self.shader_instance is None:
            shader_manager: R.MShaderManager = R.MRenderer.getShaderManager()
            self.shader_instance = shader_manager.getEffectsFileShader(
                str(Path(__file__).with_name("lens_distortion.ogsfx")), "Main"
            )
            if self.shader_instance is None:
                raise RuntimeError("Lens shader: " + str(shader_manager.getLastError()))
        shader: R.MShaderInstance = self.shader_instance
        shader.setParameter("sceneTexture", self.targets[Target.SCENE_COLOR])
        assignment: R.MTextureAssignment = R.MTextureAssignment()
        assignment.texture = self.stmap_texture
        shader.setParameter("stmapTexture", assignment)

    def set_stmap(self, path: str) -> None:
        """Validate and load an STMap texture, preserving the current STMap on failure.

        https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_texture_manager.html
        """
        path = str(Path(path).resolve()) if path.strip() else path
        validate_stmap(path)
        tex_manager: R.MTextureManager = R.MRenderer.getTextureManager()
        # In Maya's OpenGL Core path, the first (top) EXR row becomes texture
        # V=0. The screen quad also supplies V=0 at its top, so the shader can
        # read the matching STMap row without flipping its UV or the map's G.
        # One mipmap level keeps this floating-point STMap at its source size.
        new_stmap_texture: R.MTexture | None = tex_manager.acquireTexture(path, "", 1)
        if new_stmap_texture is None:
            raise RuntimeError("Maya could not load STMap: " + path)
        
        # Replace the current STMap only after the new texture loads successfully.
        previous: R.MTexture | None = self.stmap_texture
        self.stmap_texture = new_stmap_texture
        self.stmap_path = path
        if previous is not None:
            tex_manager.releaseTexture(previous)

    def release(self) -> None:
        """Release this override's shader, texture and render targets."""
        shader_manager: R.MShaderManager = R.MRenderer.getShaderManager()
        if self.shader_instance is not None:
            shader_manager.releaseShader(self.shader_instance)
            self.shader_instance = None
        if self.stmap_texture is not None:
            tex_manager: R.MTextureManager = R.MRenderer.getTextureManager()
            tex_manager.releaseTexture(self.stmap_texture)
            self.stmap_texture = None
        target_manager: R.MRenderTargetManager = R.MRenderer.getRenderTargetManager()
        for target in self.targets.values():
            target_manager.releaseRenderTarget(target)
        self.targets = {}
        self.target_size = None


class Scene(R.MSceneRender):
    """Render the scene into color and depth targets.

    https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_scene_render.html
    """
    def __init__(self, render_override: LensOverride) -> None:
        super().__init__("lensScene")
        self.render_override: LensOverride = render_override

    def targetOverrideList(self) -> list[R.MRenderTarget]:
        # Return the scene color and depth targets allocated in setup().
        return [
            self.render_override.targets[Target.SCENE_COLOR],
            self.render_override.targets[Target.SCENE_DEPTH],
        ]

    def clearOperation(self) -> R.MClearOperation:
        """Clear the scene targets using Maya's background preferences.

        https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_clear_operation.html
        """
        # Use Maya's background preferences.
        clear: R.MClearOperation = super().clearOperation()
        clear.setOverridesColors(False)
        clear.setMask(R.MClearOperation.kClearAll)
        return clear


class Distort(R.MQuadRender):
    """Apply the STMap shader to a screen quad.

    https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_quad_render.html
    """
    def __init__(self, render_override: LensOverride) -> None:
        super().__init__("lensDistort")
        self.render_override: LensOverride = render_override

    def targetOverrideList(self) -> list[R.MRenderTarget]:
        return [self.render_override.targets[Target.DISTORTED_COLOR]]

    def shader(self) -> R.MShaderInstance | None:
        return self.render_override.shader_instance


class Present(R.MPresentTarget):
    """Present the distorted color target to the viewport or playblast output.

    https://help.autodesk.com/cloudhelp/2026/ENU/MAYA-API-REF/py_ref/class_open_maya_render_1_1_m_present_target.html
    """
    def __init__(self, render_override: LensOverride) -> None:
        super().__init__("lensPresent")
        self.render_override: LensOverride = render_override

    def targetOverrideList(self) -> list[R.MRenderTarget]:
        return [self.render_override.targets[Target.DISTORTED_COLOR]]


def active_panel() -> str:
    """Return the focused model panel, falling back to a visible model panel."""
    panel: str | None = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        return panel
    panels: list[str] = cmds.getPanel(visiblePanels=True)
    return next(
        (p for p in panels if cmds.getPanel(typeOf=p) == "modelPanel"), "modelPanel4"
    )


def enable(path: str, panel: str | None = None) -> str:
    """Load an STMap and enable the override on a model panel. """

    if not path.strip():
        raise ValueError("Choose an STMap before enabling lens distortion")
    if _override is None:
        raise RuntimeError("Load lens_distortion.py in Plug-in Manager first")
    if R.MRenderer.drawAPI() != R.MRenderer.kOpenGLCoreProfile:
        raise RuntimeError(
            "Select OpenGL Core Profile in Maya preferences and restart Maya"
        )

    # Set the panel renderer override without changing the camera or scene nodes.
    _override.set_stmap(path)
    panel = panel or active_panel()
    previous_renderer: str = cmds.modelEditor(panel, query=True, rendererName=True)
    previous_override: str = cmds.modelEditor(panel, query=True, rendererOverrideName=True)
    try:
        cmds.modelEditor(
            panel, edit=True, rendererName="vp2Renderer", rendererOverrideName=NAME
        )
        cmds.refresh(force=True)
    except Exception:
        # Restore the previous renderer if switching or refreshing fails.
        cmds.modelEditor(panel, edit=True, rendererName=previous_renderer,
                         rendererOverrideName=previous_override)
        raise
    return panel


def disable(panel: str | None = None) -> None:
    """Remove this override from the panel, keeping GPU resources for reuse."""
    panel = panel or active_panel()
    if cmds.modelEditor(panel, query=True, rendererOverrideName=True) == NAME:
        cmds.modelEditor(panel, edit=True, rendererOverrideName="")
        cmds.refresh(force=True)


def plugin_load_check() -> None:
    """Load the entry point if the renderer has not been initialized."""
    if _override is None:
        cmds.loadPlugin(str(Path(__file__).with_name('lens_distortion.py')), quiet=True)
        if _override is None:
            raise RuntimeError('Plug-in is loaded but its renderer is not initialized. '
                               'Restart Maya to clear stale Python modules.')


def get_stmap_path() -> str:
    return _override.stmap_path if _override is not None else ""


def is_enabled(panel: str) -> bool:
    return cmds.modelEditor(panel, query=True, rendererOverrideName=True) == NAME


def validate_stmap(path: str) -> STMapInfo:
    """Validate the file path and EXR header."""
    if not path.strip():
        raise ValueError("Choose an STMap before enabling lens distortion")
    if not Path(path).is_file() or Path(path).suffix.lower() != ".exr":
        raise ValueError("Choose a raw floating-point EXR STMap")
    return inspect_stmap(path)


def initializePlugin(obj: MObject) -> None:
    global _override
    _override = LensOverride()
    R.MRenderer.registerOverride(_override)


def uninitializePlugin(obj: MObject) -> None:
    global _override
    # Detach panels before unregistering the override and releasing its GPU resources.
    for panel in cmds.getPanel(type="modelPanel"):
        if cmds.modelEditor(panel, query=True, rendererOverrideName=True) == NAME:
            cmds.modelEditor(panel, edit=True, rendererOverrideName="")
    R.MRenderer.deregisterOverride(_override)
    _override.release()
    _override = None
