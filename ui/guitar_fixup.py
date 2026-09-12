"""Post-separation guitar stem fix-up for the Mixer tab."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_to_tab.isolate import (
    GUITAR_PREREFINE_NAME,
    GUITAR_REFINED_NAME,
    BassBleedDiagnostics,
    LowEndRecoveryDiagnostics,
    analyze_bass_bleed,
    analyze_guitar_stem_quality,
    apply_guitar_low_end_recovery,
    has_guitar_prerefine,
    switch_guitar_stem_variant,
)

GUITAR_BACKUP_NAME = "guitar_original.wav"
GUITAR_HPF_TUNING_CAPTION = (
    "Drop D (~73 Hz) is kept; Drop C / 7-string / Drop A can lose fundamentals."
)


def guitar_backup_path(guitar_path: Path) -> Path:
    return guitar_path.parent / GUITAR_BACKUP_NAME


def has_guitar_backup(guitar_path: Path) -> bool:
    return guitar_backup_path(guitar_path).is_file()


def ensure_guitar_backup(guitar_path: Path) -> Path:
    """Keep an untouched copy of the guitar stem before the first fix-up apply."""
    backup = guitar_backup_path(guitar_path)
    if not backup.is_file():
        shutil.copy2(guitar_path, backup)
    return backup


def restore_guitar_from_backup(guitar_path: Path) -> bool:
    backup = guitar_backup_path(guitar_path)
    if not backup.is_file():
        return False
    shutil.copy2(backup, guitar_path)
    return True


def prepare_fixup_source(guitar_path: Path) -> Path:
    """Always process from the saved pre-fix-up guitar (no stacked applies)."""
    backup = guitar_backup_path(guitar_path)
    if backup.is_file():
        shutil.copy2(backup, guitar_path)
    else:
        ensure_guitar_backup(guitar_path)
    return guitar_path


def _competing_stems(stem_paths: dict[str, Path]) -> dict[str, Path]:
    return {
        name: path
        for name in ("bass", "piano", "drums", "vocals")
        if (path := stem_paths.get(name)) is not None and path.is_file()
    }


def load_guitar_stem_quality(artifacts: dict[str, Any]) -> dict[str, Any]:
    path = artifacts.get("guitar_stem_quality_diagnostics") or artifacts.get(
        "guitar_stem_quality"
    )
    if not path or not Path(path).exists():
        run_guess = None
        guitar = artifacts.get("guitar")
        if guitar:
            run_guess = Path(guitar).parent / "guitar_stem_quality.json"
            if run_guess.is_file():
                path = run_guess
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_fold_other_diagnostics(artifacts: dict[str, Any]) -> dict[str, Any]:
    path = artifacts.get("fold_other_diagnostics")
    if not path or not Path(path).exists():
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


@dataclass
class GuitarFixupResult:
    ok: bool
    message: str
    bass_bleed: BassBleedDiagnostics | None = None
    recovery: LowEndRecoveryDiagnostics | None = None
    artifact_updates: dict[str, str] | None = None


def refresh_guitar_diagnostics(
    guitar_path: Path,
    run_dir: Path,
    *,
    stem_paths: dict[str, Path],
) -> dict[str, str]:
    """Re-write bass-bleed / quality JSON after guitar.wav changed."""
    updates: dict[str, str] = {}
    bass_bleed = analyze_bass_bleed(guitar_path)
    bass_path = run_dir / "bass_bleed_diagnostics.json"
    bass_bleed.write_json(bass_path)
    updates["bass_bleed_diagnostics"] = str(bass_path)

    competing = _competing_stems(stem_paths)
    quality = analyze_guitar_stem_quality(
        guitar_path, competing_stems=competing or None
    )
    quality_path = run_dir / "guitar_stem_quality.json"
    quality.write_json(quality_path)
    updates["guitar_stem_quality_diagnostics"] = str(quality_path)
    return updates


def apply_mixer_guitar_fixup(
    *,
    guitar_path: Path,
    stem_paths: dict[str, Path],
    run_dir: Path,
    sub_bass_debleed: bool,
    low_end_restore_db: float,
) -> GuitarFixupResult:
    if not guitar_path.is_file():
        return GuitarFixupResult(ok=False, message="Guitar stem file is missing.")

    if not sub_bass_debleed and low_end_restore_db < 1e-6:
        return GuitarFixupResult(
            ok=False,
            message="Enable subtractive bass de-bleed and/or set low-end restore above 0 dB.",
        )

    if sub_bass_debleed and not (stem_paths.get("bass") and stem_paths["bass"].is_file()):
        return GuitarFixupResult(
            ok=False,
            message="Subtractive bass de-bleed needs a bass stem from this separation run.",
        )

    prepare_fixup_source(guitar_path)
    recovery = apply_guitar_low_end_recovery(
        guitar_path,
        guitar_path,
        bass_path=stem_paths.get("bass"),
        drums_path=stem_paths.get("drums"),
        sub_bass_debleed=sub_bass_debleed,
        boost_db=low_end_restore_db,
    )
    if not recovery.attempted:
        return GuitarFixupResult(
            ok=False,
            message=recovery.reason or "Fix-up did not change the guitar stem.",
            recovery=recovery,
        )

    recovery_path = run_dir / "low_end_recovery_diagnostics.json"
    recovery.write_json(recovery_path)
    updates = refresh_guitar_diagnostics(guitar_path, run_dir, stem_paths=stem_paths)
    updates["low_end_recovery_diagnostics"] = str(recovery_path)

    share = recovery.post_low_band_energy_share
    parts = [recovery.reason]
    if share is not None:
        parts.append(f"low-band share now {share:.2f}")
    return GuitarFixupResult(
        ok=True,
        message="; ".join(parts),
        bass_bleed=analyze_bass_bleed(guitar_path),
        recovery=recovery,
        artifact_updates=updates,
    )


def reset_mixer_guitar_fixup(
    *,
    guitar_path: Path,
    stem_paths: dict[str, Path],
    run_dir: Path,
) -> GuitarFixupResult:
    if not restore_guitar_from_backup(guitar_path):
        return GuitarFixupResult(
            ok=False,
            message="No saved original guitar stem — nothing to reset.",
        )
    updates = refresh_guitar_diagnostics(guitar_path, run_dir, stem_paths=stem_paths)
    recovery_path = run_dir / "low_end_recovery_diagnostics.json"
    if recovery_path.is_file():
        recovery_path.unlink()
        updates.pop("low_end_recovery_diagnostics", None)
    return GuitarFixupResult(
        ok=True,
        message="Restored the guitar stem from before fix-up.",
        bass_bleed=analyze_bass_bleed(guitar_path),
        artifact_updates=updates,
    )


def switch_mixer_guitar_variant(
    *,
    guitar_path: Path,
    stem_paths: dict[str, Path],
    run_dir: Path,
    use_prerefine: bool,
) -> GuitarFixupResult:
    label = "pre-refine (BS-RoFormer)" if use_prerefine else "MelBand refined"
    if not switch_guitar_stem_variant(guitar_path, use_prerefine=use_prerefine):
        need = GUITAR_PREREFINE_NAME if use_prerefine else GUITAR_REFINED_NAME
        return GuitarFixupResult(
            ok=False,
            message=f"No `{need}` backup in this run — re-separate with MelBand refine to create it.",
        )
    updates = refresh_guitar_diagnostics(guitar_path, run_dir, stem_paths=stem_paths)
    return GuitarFixupResult(
        ok=True,
        message=f"Switched guitar stem to {label}.",
        bass_bleed=analyze_bass_bleed(guitar_path),
        artifact_updates=updates,
    )


def merge_artifact_updates(artifacts: dict[str, Any], updates: dict[str, str] | None) -> dict[str, Any]:
    merged = dict(artifacts or {})
    if updates:
        merged.update(updates)
    return merged


def invalidate_mixer_playback(session: dict[str, Any]) -> None:
    for key in ("isolate_mixer_state", "isolate_mix_ready", "isolate_mix_fp"):
        session.pop(key, None)
