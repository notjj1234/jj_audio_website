"""Best-effort model prewarm to avoid first-request timeouts."""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("prewarm")


def main() -> int:
    try:
        from basic_pitch.inference import Model
        from basic_pitch import ICASSP_2022_MODEL_PATH

        log.info("Warming Basic Pitch…")
        Model(ICASSP_2022_MODEL_PATH)
        log.info("Basic Pitch ready")
    except Exception as exc:
        log.warning("Basic Pitch prewarm skipped: %s", exc)

    try:
        import torch
        from demucs.pretrained import get_model

        log.info("Warming Demucs htdemucs…")
        get_model("htdemucs")
        if torch.cuda.is_available():
            log.info("CUDA available")
        log.info("Demucs ready")
    except Exception as exc:
        log.warning("Demucs prewarm skipped: %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
