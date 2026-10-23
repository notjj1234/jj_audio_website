"""Download the pinned faster-whisper-small model with urllib + SHA256.

No huggingface_hub. Prototype for the product download path.

    .venv311/bin/python docs/plans/moises-parity/_work/spikes/fetch_whisper_model.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "src"))
from audio_to_tab.roformer import download_sha256_file, file_sha256  # noqa: E402

REPO = "Systran/faster-whisper-small"
DEST = Path.home() / ".cache" / "audio_to_tab" / "analysis" / "faster-whisper-small"
API = f"https://huggingface.co/api/models/{REPO}/tree/main?recursive=true"
BASE = f"https://huggingface.co/{REPO}/resolve/main"


def fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "audio-to-tab-spike/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def download_plain(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "audio-to-tab-spike/0.1"})
    with urllib.request.urlopen(req, timeout=300) as resp, tmp.open("wb") as fh:
        while chunk := resp.read(1024 * 1024):
            fh.write(chunk)
    tmp.replace(dest)
    return dest


def main() -> int:
    items = fetch_json(API)
    manifest = []
    for item in items:
        if item.get("type") != "file" or item["path"].startswith("."):
            continue
        path = item["path"]
        dest = DEST / path
        lfs = item.get("lfs") or {}
        if lfs:
            print(f"pinned   {path} ({lfs['size'] / 1e6:.1f} MB)")
            download_sha256_file(f"{BASE}/{path}", dest, lfs["oid"], timeout=600)
            sha = lfs["oid"]
        else:
            print(f"download {path}")
            download_plain(f"{BASE}/{path}", dest)
            sha = file_sha256(dest)
        manifest.append({"path": path, "size": dest.stat().st_size, "sha256": sha})
        print(f"         sha256={sha}")

    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {DEST / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
