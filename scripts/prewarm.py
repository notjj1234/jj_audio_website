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

        log.info("Warming Demucs htdemucs_6s (default isolate model)…")
        get_model("htdemucs_6s")
        log.info("Demucs htdemucs_6s ready")

        try:
            log.info("Warming Demucs htdemucs (optional presets)…")
            get_model("htdemucs")
            log.info("Demucs htdemucs ready")
        except Exception as exc:
            log.warning("Demucs htdemucs prewarm skipped: %s", exc)

        if torch.cuda.is_available():
            log.info("CUDA available")
    except Exception as exc:
        log.warning("Demucs prewarm skipped: %s", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
