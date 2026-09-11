"""Fixture-building helpers shared across the test suite (kept out of
conftest.py so test modules can import them directly without relying on
pytest's fixture-injection machinery for pure data builders).
"""
from __future__ import annotations

import struct
from pathlib import Path


def build_esp_bytes(masters: list[str], *, is_light: bool = False, author: str = "test") -> bytes:
    """Construct a minimal-but-real TES4 record with MAST/DATA subrecords,
    matching the layout esp_parser.py reads.
    """
    RECORD_HEADER = struct.Struct("<4sIIIIHH")
    SUBRECORD_HEADER = struct.Struct("<4sH")

    body = b""

    hedr_data = struct.pack("<fii", 1.71, 0, 2048)
    body += SUBRECORD_HEADER.pack(b"HEDR", len(hedr_data)) + hedr_data

    cnam_data = author.encode("cp1252") + b"\x00"
    body += SUBRECORD_HEADER.pack(b"CNAM", len(cnam_data)) + cnam_data

    for m in masters:
        mast_data = m.encode("cp1252") + b"\x00"
        body += SUBRECORD_HEADER.pack(b"MAST", len(mast_data)) + mast_data
        data_data = struct.pack("<Q", 0)
        body += SUBRECORD_HEADER.pack(b"DATA", len(data_data)) + data_data

    flags = 0x200 if is_light else 0
    header = RECORD_HEADER.pack(b"TES4", len(body), flags, 0, 0, 44, 0)
    return header + body


def make_mod_folder(mods_path: Path, name: str, files: dict[str, bytes] | None = None) -> Path:
    mod_dir = mods_path / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    for rel, data in (files or {}).items():
        target = mod_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return mod_dir
