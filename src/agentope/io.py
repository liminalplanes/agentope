"""File reading, timestamps and durations."""

import gzip
import hashlib
import json
import math
import re
from collections.abc import Iterator
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import IO, Any

from .errors import DataError

type PathArg = str | PathLike[str]

_GZIP_MAGIC = b"\x1f\x8b"


def is_path(value: object) -> bool:
    return isinstance(value, (str, PathLike))


def open_text(path: PathArg) -> IO[str]:
    """Open a text file, transparently decompressing gzip (detected by content)."""
    p = Path(path)
    try:
        with p.open("rb") as f:
            magic = f.read(2)
    except FileNotFoundError:
        raise DataError(f"{path}: file not found") from None
    except IsADirectoryError:
        raise DataError(f"{path}: is a directory") from None
    if magic == _GZIP_MAGIC:
        return gzip.open(p, "rt", encoding="utf-8", newline="")
    return p.open("r", encoding="utf-8", newline="")


def first_char(path: PathArg) -> str:
    """The first non-whitespace character of a text file ('' if it is blank)."""
    with open_text(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                return stripped[0]
    return ""


def read_jsonl(path: PathArg) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield (line number, object) for each non-blank line of a JSON Lines file."""
    with open_text(path) as f:
        for lineno, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as e:
                raise DataError(f"{path}:{lineno}: invalid JSON ({e.msg})") from None
            if not isinstance(obj, dict):
                raise DataError(f"{path}:{lineno}: expected a JSON object")
            yield lineno, obj


def canonical_sha256(obj: Any) -> str:
    """SHA-256 of an object's canonical JSON (sorted keys, no whitespace)."""
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def sha256_file(path: PathArg) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_time(value: object, where: str, field: str = "t") -> float:
    """Unix seconds (number or numeric string) or an ISO 8601 timestamp with a timezone."""
    if isinstance(value, bool):
        raise DataError(f"{where}: {field} must be a timestamp, got {value!r}")
    if isinstance(value, (int, float)):
        t = float(value)
    elif isinstance(value, str):
        s = value.strip()
        try:
            t = float(s)
        except ValueError:
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                raise DataError(
                    f"{where}: {field} must be unix seconds or an ISO 8601 timestamp, got {value!r}"
                ) from None
            if dt.tzinfo is None:
                raise DataError(
                    f"{where}: timestamp {value!r} has no timezone; add one (e.g. 'Z')"
                ) from None
            t = dt.timestamp()
    else:
        raise DataError(f"{where}: {field} must be a timestamp, got {value!r}")
    if not math.isfinite(t):
        raise DataError(f"{where}: {field} must be finite, got {value!r}")
    return t


_UNITS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhdw]?)\s*$")


def parse_duration(value: object) -> float:
    """Parse a duration like '7d', '12h', '30m', '90s' or a number of seconds."""
    if isinstance(value, bool):
        raise DataError(f"invalid duration {value!r}")
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str) and (m := _DURATION.match(value)):
        seconds = float(m.group(1)) * _UNITS[m.group(2)]
    else:
        raise DataError(f"invalid duration {value!r}; use e.g. 7d, 12h, 30m or seconds")
    if not (math.isfinite(seconds) and seconds > 0):
        raise DataError(f"duration must be positive, got {value!r}")
    return seconds


def format_duration(seconds: float) -> str:
    for unit, size in (("w", 604800), ("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size and seconds % size == 0:
            return f"{int(seconds // size)}{unit}"
    return f"{seconds:g}s"


def format_rough_duration(seconds: float) -> str:
    days = seconds / 86400
    if days < 2:
        return f"~{max(1, round(seconds / 3600))} hours"
    if days < 21:
        return f"~{round(days)} days"
    return f"~{round(days / 7)} weeks"
