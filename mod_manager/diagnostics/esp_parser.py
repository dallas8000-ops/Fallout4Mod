"""Minimal, real binary parser for the Fallout 4 plugin (.esp/.esm/.esl)
file header -- specifically the master-file dependency list.

None of the six legacy scripts in this project ever look inside a plugin
file. check_mod_conflicts.py's "conflict detection" only pattern-matches
mod *folder names* against a hand-maintained list of problems already
diagnosed once. A missing-master crash (arguably the single most common
CTD-on-launch cause in Fallout 4 modding) is completely invisible to this
codebase before this file existed.

This reads just the first record (TES4) and its MAST subrecords -- nothing
else, no full plugin parse, no record editing. That is enough to answer
"does this plugin depend on a master that isn't installed / isn't active".

Record layout (Fallout4, same as Skyrim SE/AE):
  4s   signature          (b"TES4" for the header record)
  I    data size           (bytes following this 24-byte header)
  I    record flags        (bit 0x200 = ESL / light plugin)
  I    form id
  I    version control info
  H    form version
  H    unknown

Subrecord layout within the record's data:
  4s   signature
  H    size
  <size> bytes of data

A "XXXX" subrecord overrides the size of the subrecord immediately
following it with a 4-byte uint32 (used when a field is too large for the
16-bit size). Handled here for correctness even though it never applies to
the small header fields we read.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

RECORD_HEADER = struct.Struct("<4sIIIIHH")
SUBRECORD_HEADER = struct.Struct("<4sH")

ESL_FLAG = 0x00000200


@dataclass(frozen=True)
class PluginHeader:
    path: Path
    is_master_style: bool  # TES4 record found and parsed
    masters: list[str]
    is_light: bool
    author: str | None
    description: str | None
    error: str | None = None


def parse_header(path: Path) -> PluginHeader:
    """Parse just the TES4 record. Tolerant of truncated/odd files -- returns
    a PluginHeader with .error set rather than raising, since this runs
    against arbitrary third-party mod files of unknown provenance.
    """
    try:
        with path.open("rb") as f:
            raw = f.read(RECORD_HEADER.size)
            if len(raw) < RECORD_HEADER.size:
                return PluginHeader(path, False, [], False, None, None, "file too short for a record header")

            sig, data_size, flags, _form_id, _vc, _form_ver, _unk = RECORD_HEADER.unpack(raw)
            if sig != b"TES4":
                return PluginHeader(path, False, [], False, None, None, f"first record is {sig!r}, not TES4")

            is_light = bool(flags & ESL_FLAG)
            data = f.read(data_size)
            if len(data) < data_size:
                return PluginHeader(
                    path, True, [], is_light, None, None,
                    "TES4 record truncated (file shorter than declared data size)",
                )

            masters: list[str] = []
            author: str | None = None
            description: str | None = None

            pos = 0
            pending_xxxx_size: int | None = None
            while pos + SUBRECORD_HEADER.size <= len(data):
                sub_sig, sub_size = SUBRECORD_HEADER.unpack_from(data, pos)
                pos += SUBRECORD_HEADER.size

                if pending_xxxx_size is not None:
                    sub_size = pending_xxxx_size
                    pending_xxxx_size = None

                sub_data = data[pos : pos + sub_size]
                pos += sub_size

                if sub_sig == b"XXXX" and len(sub_data) == 4:
                    (pending_xxxx_size,) = struct.unpack("<I", sub_data)
                    continue
                if sub_sig == b"MAST":
                    masters.append(sub_data.rstrip(b"\x00").decode("cp1252", errors="replace"))
                elif sub_sig == b"CNAM":
                    author = sub_data.rstrip(b"\x00").decode("cp1252", errors="replace")
                elif sub_sig == b"SNAM":
                    description = sub_data.rstrip(b"\x00").decode("cp1252", errors="replace")

            return PluginHeader(path, True, masters, is_light, author, description)
    except OSError as exc:
        return PluginHeader(path, False, [], False, None, None, f"could not read file: {exc}")
