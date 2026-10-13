# SPDX-License-Identifier: LGPL-3.0-or-later
"""Maya Plug-in Manager entry point."""


from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maya.api.OpenMaya import MObject

core: ModuleType | None = None


def maya_useNewAPI() -> None:
    """Required to use the API 2.0."""
    pass


def initializePlugin(obj: MObject) -> None:
    global core
    import lens_core

    core = lens_core
    core.initializePlugin(obj)


def uninitializePlugin(obj: MObject) -> None:
    core.uninitializePlugin(obj)
