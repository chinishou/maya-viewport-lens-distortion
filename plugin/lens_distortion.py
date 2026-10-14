# SPDX-License-Identifier: LGPL-3.0-or-later
"""Maya Plug-in Manager entry point."""


from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maya.api.OpenMaya import MObject

override_module: ModuleType | None = None


def maya_useNewAPI() -> None:
    """Required to use the API 2.0."""
    pass


def initializePlugin(obj: MObject) -> None:
    global override_module
    import lens_override

    override_module = lens_override
    override_module.initializePlugin(obj)


def uninitializePlugin(obj: MObject) -> None:
    override_module.uninitializePlugin(obj)
