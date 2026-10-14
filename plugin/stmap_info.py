# SPDX-License-Identifier: LGPL-3.0-or-later
"""Inspect an STMap EXR header and its data/display windows without 3rd-party libs."""

from __future__ import annotations

from os import PathLike
from typing import TypedDict
import struct


class STMapInfo(TypedDict):
    width: int
    height: int
    channels: dict[str, tuple[int, int, int]]
    data_window: tuple[int, int, int, int]
    display_window: tuple[int, int, int, int]


def comparison_size(info: STMapInfo) -> tuple[str, int, int]:
    """Choose the dataWindow or displayWindow to compare with Maya Render Settings resolution."""
    data = info['data_window']
    display = info['display_window']
    extends: bool = (data[0] < display[0] or data[1] < display[1]
                     or data[2] > display[2] or data[3] > display[3])
    name: str = 'displayWindow' if extends else 'dataWindow'
    window: tuple[int, int, int, int] = display if extends else data
    return name, window[2]-window[0]+1, window[3]-window[1]+1


def inspect_stmap(path: str | PathLike[str]) -> STMapInfo:
    """Read the OpenEXR header and validate STMap compatibility.

    Header layout:
    - Magic number (4 bytes).
    - Version number and flags (4 bytes).
    - Attributes (variable length), terminated by a null byte.

    Pixel data is not decoded.
    """
    with open(path, "rb") as stream:
        header: bytes = stream.read(1024 * 1024)
    if len(header) < 8 or struct.unpack_from("<I", header)[0] != 20000630:
        raise ValueError("Not an OpenEXR file")
    version: int = struct.unpack_from("<I", header, 4)[0]
    if version & (0x800 | 0x1000):
        raise ValueError("Deep/multipart EXR STMaps are not supported")

    pos: int = 8
    attrs: dict[bytes, bytes] = {}

    def string_at(offset: int) -> tuple[bytes, int]:
        """Return a null-terminated string and the next offset."""
        end: int = header.index(b"\0", offset)
        return header[offset:end], end + 1

    try:
        while header[pos] != 0:
            name, pos = string_at(pos)
            _, pos = string_at(pos)
            size: int = struct.unpack_from("<I", header, pos)[0]
            pos += 4
            if pos + size > len(header):
                raise ValueError("EXR header exceeds 1 MiB or is truncated")
            attrs[name] = header[pos : pos + size]
            pos += size
        data: tuple[int, int, int, int] = struct.unpack("<4i", attrs[b"dataWindow"])
        display: tuple[int, int, int, int] = struct.unpack("<4i", attrs[b"displayWindow"])
        if any(window[2] < window[0] or window[3] < window[1] for window in (data, display)):
            raise ValueError("Invalid EXR window dimensions")
        channels: dict[str, tuple[int, int, int]] = {}
        raw: bytes = attrs[b"channels"]
        cursor: int = 0
        while raw[cursor] != 0:
            end: int = raw.index(b"\0", cursor)
            channel_name: str = raw[cursor:end].decode("ascii")
            cursor = end + 1
            pixel_type, linear, xs, ys = struct.unpack_from("<iB3xii", raw, cursor)
            channels[channel_name] = (pixel_type, xs, ys)
            cursor += 16
        # pixel type 1/2 are half/float; sampling must be 1 for per-pixel UV lookup.
        if any(channels.get(c) not in ((1, 1, 1), (2, 1, 1)) for c in ("R", "G")):
            raise ValueError(
                "STMap requires full-resolution floating-point R and G channels"
            )
        # Max coordinate of the EXR window includes the endpoint, so +1.
        return {"width": data[2]-data[0]+1, "height": data[3]-data[1]+1,
                "channels": channels, "data_window": data, "display_window": display}
    except (KeyError, IndexError, struct.error) as exc:
        raise ValueError("Incomplete or unsupported EXR header") from exc
