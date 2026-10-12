"""Pure helpers for desktop YouTube search dialogs (no Streamlit widgets)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from audio_to_tab.ingest import YouTubeSearchHit

PAGE_SIZE = 10


def page_offset(page: int, *, page_size: int = PAGE_SIZE) -> int:
    """0-based offset for a 1-based page index."""
    return max(0, (max(1, int(page)) - 1) * int(page_size))


def normalize_page(page: Any) -> int:
    try:
        return max(1, int(page))
    except (TypeError, ValueError):
        return 1


def has_next_page(n_hits: int, *, page_size: int = PAGE_SIZE) -> bool:
    """True when the current page looks full (another fetch may return more)."""
    return int(n_hits) >= int(page_size)


def result_range_caption(
    page: int,
    n_hits: int,
    *,
    page_size: int = PAGE_SIZE,
) -> str:
    """Human label like ``Page 2 · results 11–20`` (or ``no results``)."""
    p = normalize_page(page)
    n = max(0, int(n_hits))
    if n == 0:
        return f"Page {p} · no results"
    start = page_offset(p, page_size=page_size) + 1
    end = start + n - 1
    return f"Page {p} · results {start}–{end}"


def hit_as_dict(hit: YouTubeSearchHit) -> dict[str, Any]:
    return {
        "video_id": hit.video_id,
        "title": hit.title,
        "channel": hit.channel,
        "duration_sec": hit.duration_sec,
        "url": hit.url,
        "thumbnail_url": hit.thumbnail_url,
    }


def hits_as_dicts(hits: Sequence[YouTubeSearchHit]) -> list[dict[str, Any]]:
    return [hit_as_dict(h) for h in hits]


def meta_line(hit: Mapping[str, Any], *, duration_label: str) -> str:
    channel = str(hit.get("channel") or "").strip()
    bits = [b for b in (channel, (duration_label or "").strip()) if b]
    return " · ".join(bits)
