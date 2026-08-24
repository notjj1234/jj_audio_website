"""Windows CPU vs NVIDIA CUDA desktop edition (baked into the freeze)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

EDITION_CPU = "cpu"
EDITION_CUDA = "cuda"
EDITION_ENV = "AUDIO_TOOLS_EDITION"
CPU_APPID = "{A7C3E8F1-4B2D-4E9A-9C1F-8D6B5A2E0F73}"
CUDA_APPID = "{C4E91A2B-7D83-4F16-9B50-2A8E6C3D1F47}"


def normalize_edition(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if value in {EDITION_CUDA, "nvidia", "gpu"}:
        return EDITION_CUDA
    return EDITION_CPU


def edition_file_candidates(bundle: Path) -> tuple[Path, ...]:
    return (
        bundle / "packaging" / "edition.txt",
        bundle / "edition.txt",
    )


def read_edition_file(bundle: Path) -> str | None:
    for candidate in edition_file_candidates(bundle):
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return None


def desktop_edition(*, bundle: Path | None = None, frozen: bool | None = None) -> str:
    """cpu (default) or cuda. Env wins; frozen builds also read packaging/edition.txt."""
    env = os.environ.get(EDITION_ENV, "").strip()
    if env:
        return normalize_edition(env)
    is_frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
    if is_frozen:
        root = bundle
        if root is None:
            meipass = getattr(sys, "_MEIPASS", None)
            root = Path(meipass) if meipass else Path(sys.executable).resolve().parent
        file_val = read_edition_file(root)
        if file_val:
            return normalize_edition(file_val)
    return EDITION_CPU


def edition_app_name(edition: str | None = None, *, platform: str | None = None) -> str:
    """LocalAppData folder / process identity. CUDA is Windows-only."""
    ed = normalize_edition(edition) if edition is not None else desktop_edition()
    plat = platform if platform is not None else sys.platform
    if plat.startswith("win") and ed == EDITION_CUDA:
        return "AudioToolsNVIDIA"
    return "AudioTools"


def edition_window_title(edition: str | None = None) -> str:
    ed = normalize_edition(edition) if edition is not None else desktop_edition()
    if ed == EDITION_CUDA:
        return "Audio Tools (NVIDIA)"
    return "Audio Tools (CPU)"


def edition_product_name(edition: str | None = None) -> str:
    return edition_window_title(edition)


def edition_display_label(edition: str | None = None) -> str:
    ed = normalize_edition(edition) if edition is not None else desktop_edition()
    if ed == EDITION_CUDA:
        return "NVIDIA CUDA"
    return "CPU"
