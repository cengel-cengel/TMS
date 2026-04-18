from __future__ import annotations

import re
from datetime import date
from pathlib import Path


def resolve_dlv_file(dlv_dir: Path, pattern: str = "*.xlsx") -> Path:
    """
    Return the DLV file that applies for a given directory using year-fallback
    (2026 > 2025 > older).  Files in subdirectories named 'durch neue Offerten
    ersetzt' or 'nicht mehr relevant' are skipped.

    Args:
        dlv_dir: Directory containing year-labelled xlsx files and/or year
                 subdirectories (e.g. 2025/, 2026/).
        pattern:  Glob pattern for DLV files.

    Returns:
        Path to the best matching file.

    Raises:
        FileNotFoundError: if no matching file found.
    """
    SKIP_DIRS = {"durch neue offerten ersetzt", "nicht mehr relevant", "upload"}

    def year_from_path(p: Path) -> int:
        # Prefer year extracted from filename date prefix (YYYYMMDD_...)
        m = re.search(r"(202\d)", p.name)
        if m:
            return int(m.group(1))
        # Fall back to year found anywhere in the full path
        parts = [part for part in p.parts if part.lower() not in SKIP_DIRS]
        for part in reversed(parts):
            m2 = re.search(r"(202\d)", part)
            if m2:
                return int(m2.group(1))
        return 0

    candidates: list[tuple[int, Path]] = []
    for p in sorted(dlv_dir.rglob(pattern)):
        # Skip superseded / upload directories
        if any(part.lower() in SKIP_DIRS for part in p.parts):
            continue
        y = year_from_path(p)
        candidates.append((y, p))

    if not candidates:
        raise FileNotFoundError(f"No DLV files matching {pattern!r} under {dlv_dir}")

    # Sort descending by year, then by name for determinism
    candidates.sort(key=lambda t: (-t[0], t[1].name))
    return candidates[0][1]
