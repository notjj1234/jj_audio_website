"""Optional RoFormer backends for guitar isolation (opt-in, not the default).

2026-08-29: ``htdemucs_6s`` remains the default first-stage separator. Its guitar
head is the weak point of the Demucs family (bleed + lost clean content). Two
community models are the practical upgrades, loaded at runtime (never committed):

- **BS-RoFormer-SW 6-stem** (``bs_roformer_sw``) — genuine guitar stem, typically
  the largest SDR/SIR jump vs stock 6s. Architecture MIT (lucidrains / ZFTurbo).
  Current weight host: ``enerjazzer/BS-ROFO-SW-Fixed`` (the original
  ``jarredou/BS-ROFO-SW-Fixed`` Hugging Face account was deleted in 2026).
  **No stated license on the rehosted checkpoint — use accordingly.**
- **MelBand-Roformer Guitar by becruily** — 2-stem Guitar/Other specialist used
  as an opt-in *refine* pass on a first-stage guitar stem + residual. Model card
  exists on Hugging Face (``becruily/mel-band-roformer-guitar``).

Integration: prefer ``bs-roformer-infer`` (optional extra ``[roformer]``) — a
lightweight inference package, not the UVR stack. ``python-audio-separator``
(optional extra ``[separator]``) is a fallback. Weights are urllib + SHA256,
same pattern as guitar-ft; no ``huggingface_hub``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import shutil
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path

logger = logging.getLogger(__name__)

BS_ROFORMER_SW_ID = "bs_roformer_sw"
MELBAND_GUITAR_ID = "melband_roformer_guitar"
ROFORMER_MODELS = (BS_ROFORMER_SW_ID, MELBAND_GUITAR_ID)

# 6-stem BS-RoFormer-SW (jarredou / rehosted 2026 by enerjazzer).
# License: none stated on the checkpoint. Architecture (lucidrains BS-RoFormer) is MIT.
BS_ROFORMER_SW_HF_REPO = "enerjazzer/BS-ROFO-SW-Fixed"
BS_ROFORMER_SW_CKPT_NAME = "BS-Rofo-SW-Fixed.ckpt"
BS_ROFORMER_SW_YAML_NAME = "BS-Rofo-SW-Fixed.yaml"
BS_ROFORMER_SW_CKPT_URL = (
    f"https://huggingface.co/{BS_ROFORMER_SW_HF_REPO}/resolve/main/{BS_ROFORMER_SW_CKPT_NAME}"
)
BS_ROFORMER_SW_YAML_URL = (
    f"https://huggingface.co/{BS_ROFORMER_SW_HF_REPO}/resolve/main/{BS_ROFORMER_SW_YAML_NAME}"
)
BS_ROFORMER_SW_CKPT_SHA256 = "24e7d35ee9c64415673d3fd33e06a67cac2c103c5df6267ba1576459c775916e"
BS_ROFORMER_SW_YAML_SHA256 = "f9fada9f94e5ba2d2e4600196299459294bc5f532b314c209cc156ac63e4329b"
BS_ROFORMER_SW_STEMS = ("bass", "drums", "other", "vocals", "guitar", "piano")

# MelBand-Roformer Guitar (becruily). ~45 MB. 2-stem Guitar / Other, 44.1 kHz.
MELBAND_GUITAR_HF_REPO = "becruily/mel-band-roformer-guitar"
MELBAND_GUITAR_CKPT_NAME = "becruily_guitar.ckpt"
MELBAND_GUITAR_YAML_NAME = "config_guitar_becruily.yaml"
MELBAND_GUITAR_CKPT_URL = (
    f"https://huggingface.co/{MELBAND_GUITAR_HF_REPO}/resolve/main/{MELBAND_GUITAR_CKPT_NAME}"
)
MELBAND_GUITAR_YAML_URL = (
    f"https://huggingface.co/{MELBAND_GUITAR_HF_REPO}/resolve/main/{MELBAND_GUITAR_YAML_NAME}"
)
# Politrees UVR_resources mirror (same oid as the author repo).
MELBAND_GUITAR_CKPT_MIRROR_URL = (
    "https://huggingface.co/Politrees/UVR_resources/resolve/main/"
    "models/Roformer/MelBand/melband_roformer_guitar_becruily.ckpt"
)
MELBAND_GUITAR_CKPT_SHA256 = "83472bbf125774af5282d2e0b86df89eaf2dd45e8a4ec8d68e820ebf3e42a83c"
MELBAND_GUITAR_YAML_SHA256 = "b681c3f886251b04b666b3f06e87ce65d7ec610e40b5d75915c01782e5444b0e"

ROFORMER_INSTALL_HINT = (
    "RoFormer guitar models need the optional extra: pip install -e \".[roformer]\" "
    "(bs-roformer-infer). python-audio-separator is an alternate extra: "
    "pip install -e \".[separator]\"."
)

_USER_AGENT = "audio-to-tab-pdf/1.0 (guitar isolation; urllib)"
_CANONICAL_STEMS = ("bass", "drums", "other", "vocals", "guitar", "piano")


def is_roformer_available() -> bool:
    """True when ``bs-roformer-infer`` is importable (no torch import)."""
    return importlib.util.find_spec("bs_roformer") is not None


def is_audio_separator_available() -> bool:
    """True when ``python-audio-separator`` is importable (heavy UVR stack)."""
    return importlib.util.find_spec("audio_separator") is not None


def is_roformer_backend_available() -> bool:
    """True when at least one optional RoFormer runtime is installed."""
    return is_roformer_available() or is_audio_separator_available()


def is_guitar_refine_available() -> bool:
    """True when the MelBand guitar specialist can run (refine extra)."""
    return is_roformer_backend_available()


def separator_cache_dir() -> Path:
    """Local cache for community checkpoints (not committed)."""
    if env := os.environ.get("ATT_SEPARATOR_CACHE"):
        return Path(env)
    if env := os.environ.get("TORCH_HOME"):
        return Path(env) / "audio_to_tab_separators"
    return Path.home() / ".cache" / "audio_to_tab" / "separators"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_sha256_file(
    url: str,
    dest: Path,
    expected_sha256: str,
    *,
    timeout: int = 300,
    mirrors: tuple[str, ...] = (),
) -> Path:
    """Stream ``url`` to ``dest`` and verify SHA256. Tries ``mirrors`` on failure."""
    dest = Path(dest)
    if dest.is_file():
        digest = file_sha256(dest)
        if digest == expected_sha256:
            return dest
        logger.warning("Cached file failed hash check; re-downloading %s", dest)
        dest.unlink(missing_ok=True)

    dest.parent.mkdir(parents=True, exist_ok=True)
    urls = (url, *mirrors)
    last_exc: BaseException | None = None
    for candidate in urls:
        tmp = dest.with_suffix(dest.suffix + ".part")
        digest = hashlib.sha256()
        try:
            req = urllib.request.Request(candidate, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as fh:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                    digest.update(chunk)
            got = digest.hexdigest()
            if got != expected_sha256:
                tmp.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Hash mismatch for {candidate} (got {got}, expected {expected_sha256})"
                )
            tmp.replace(dest)
            return dest
        except (urllib.error.URLError, OSError, RuntimeError) as exc:
            last_exc = exc
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            logger.warning("Download failed from %s: %s", candidate, exc)
    raise RuntimeError(f"Failed to download verified weights from {url}") from last_exc


def bs_roformer_sw_paths() -> tuple[Path, Path]:
    root = separator_cache_dir() / BS_ROFORMER_SW_ID
    return root / BS_ROFORMER_SW_CKPT_NAME, root / BS_ROFORMER_SW_YAML_NAME


def melband_guitar_paths() -> tuple[Path, Path]:
    root = separator_cache_dir() / MELBAND_GUITAR_ID
    return root / MELBAND_GUITAR_CKPT_NAME, root / MELBAND_GUITAR_YAML_NAME


def download_bs_roformer_sw_weights(*, force: bool = False) -> tuple[Path, Path]:
    """Download BS-RoFormer-SW checkpoint + yaml (urllib, SHA256-pinned)."""
    ckpt, yaml_path = bs_roformer_sw_paths()
    if force:
        ckpt.unlink(missing_ok=True)
        yaml_path.unlink(missing_ok=True)
    download_sha256_file(BS_ROFORMER_SW_CKPT_URL, ckpt, BS_ROFORMER_SW_CKPT_SHA256)
    download_sha256_file(BS_ROFORMER_SW_YAML_URL, yaml_path, BS_ROFORMER_SW_YAML_SHA256)
    return ckpt, yaml_path


def download_melband_guitar_weights(*, force: bool = False) -> tuple[Path, Path]:
    """Download becruily MelBand guitar checkpoint + yaml (urllib, SHA256-pinned)."""
    ckpt, yaml_path = melband_guitar_paths()
    if force:
        ckpt.unlink(missing_ok=True)
        yaml_path.unlink(missing_ok=True)
    download_sha256_file(
        MELBAND_GUITAR_CKPT_URL,
        ckpt,
        MELBAND_GUITAR_CKPT_SHA256,
        mirrors=(MELBAND_GUITAR_CKPT_MIRROR_URL,),
    )
    download_sha256_file(MELBAND_GUITAR_YAML_URL, yaml_path, MELBAND_GUITAR_YAML_SHA256)
    return ckpt, yaml_path


def _canonical_stem_name(path: Path) -> str | None:
    """Map a separator output filename onto Demucs-style stem ids."""
    stem = path.stem.lower().replace(" ", "_")
    for name in _CANONICAL_STEMS:
        if stem == name:
            return name
        if stem.endswith((f"_{name}", f"-{name}")):
            return name
        if f"({name})" in stem or f"_{name}_" in stem:
            return name
    return None


def collect_canonical_stems(root: Path, dest_dir: Path) -> dict[str, Path]:
    """Copy recognized stem WAVs into ``dest_dir`` with Demucs filenames."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    found: dict[str, Path] = {}
    for wav in sorted(root.rglob("*.wav")):
        name = _canonical_stem_name(wav)
        if name is None or name in found:
            continue
        out = dest_dir / f"{name}.wav"
        if wav.resolve() != out.resolve():
            shutil.copy2(wav, out)
        found[name] = out
    return found


def collect_named_stems(root: Path, names: tuple[str, ...] | list[str]) -> dict[str, Path]:
    """Locate recognized stem WAVs under ``root`` without copying."""
    wanted = {str(name).lower() for name in names}
    found: dict[str, Path] = {}
    for wav in sorted(root.rglob("*.wav")):
        name = _canonical_stem_name(wav)
        if name is None or name not in wanted or name in found:
            continue
        found[name] = wav
    return found


def _torch_device(device: str):
    import torch

    name = device if device in {"cpu", "cuda", "mps"} else "cpu"
    if name == "cuda" and not torch.cuda.is_available():
        name = "cpu"
    if name == "mps":
        backend = getattr(torch.backends, "mps", None)
        ok = bool(
            backend is not None
            and getattr(backend, "is_available", lambda: False)()
        )
        if not ok:
            name = "cpu"
    return torch.device(name)


def _cap_cpu_threads(device: str) -> None:
    """Cap PyTorch intra-op threads for CPU inference (Apple Silicon P-cores).

    Each isolate job runs in its own ``multiprocessing.Process``, so setting the
    process-global torch thread pool here cannot disturb the UI or other jobs.
    """
    if device != "cpu":
        return
    import torch

    try:
        from audio_to_tab.hardware import recommended_cpu_threads

        torch.set_num_threads(recommended_cpu_threads())
    except Exception:
        pass


def _load_bs_roformer_config(yaml_path: Path):
    import yaml
    from ml_collections import ConfigDict

    text = yaml_path.read_text(encoding="utf-8")
    try:
        from bs_roformer.inference import SafeLoaderWithTuple

        loaded = yaml.load(text, Loader=SafeLoaderWithTuple)
    except Exception:
        cleaned = text.replace("!!python/tuple", "")
        loaded = yaml.safe_load(cleaned)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Invalid separator config at {yaml_path}")
    return ConfigDict(loaded)


def _resolve_bs_roformer_sw_assets() -> tuple[Path, Path]:
    """Return BS-RoFormer-SW checkpoint + yaml, preferring bs-roformer-infer's cache."""
    if is_roformer_available():
        try:
            from bs_roformer.download import ensure_model_assets
            from bs_roformer.model_registry import DEFAULT_MODEL

            return ensure_model_assets(DEFAULT_MODEL)
        except Exception as exc:
            logger.warning(
                "bs-roformer-infer ensure_model_assets failed; using urllib cache: %s",
                exc,
            )
    return download_bs_roformer_sw_weights()


def _run_via_bs_roformer_infer(
    audio_path: Path,
    dest_dir: Path,
    *,
    ckpt_path: Path,
    yaml_path: Path,
    device: str,
) -> dict[str, Path]:
    """Run BS-RoFormer-SW using the official bs-roformer-infer demix path."""
    import numpy as np
    import soundfile as sf
    import torch
    from bs_roformer.utils import demix_track, get_model_from_config

    _cap_cpu_threads(device)
    config = _load_bs_roformer_config(yaml_path)
    dev = _torch_device(device)
    model = get_model_from_config("bs_roformer", config)
    try:
        state = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    except Exception:
        state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    if isinstance(state, dict):
        for key in ("state", "state_dict", "model_state_dict"):
            if key in state and isinstance(state[key], dict):
                state = state[key]
                break
    model.load_state_dict(state, strict=False)
    model.eval()
    model.to(dev)

    mix, _sr = sf.read(str(audio_path), always_2d=True)
    if mix.shape[1] == 1:
        mix = np.repeat(mix, 2, axis=1)
    elif mix.shape[1] > 2:
        mix = mix[:, :2]
    mixture = torch.tensor(mix.T, dtype=torch.float32)

    try:
        res, _first = demix_track(config, model, mixture, dev, first_chunk_time=None)
    except Exception as exc:
        if dev.type != "cpu":
            logger.warning(
                "BS-RoFormer %s run failed (%s); retrying on CPU", dev.type, exc
            )
            _cap_cpu_threads("cpu")
            model = model.to("cpu")
            res, _first = demix_track(
                config, model, mixture.cpu(), torch.device("cpu"), first_chunk_time=None
            )
        else:
            raise
    instruments = list(config.training.instruments)
    if getattr(config.training, "target_instrument", None) is not None:
        instruments = [config.training.target_instrument]

    dest_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}
    sample_rate = int(getattr(getattr(config, "audio", None), "sample_rate", None) or 44100)
    for name in instruments:
        stem = res.get(name)
        if stem is None:
            continue
        wav = stem.T.astype(np.float32)
        if wav.ndim == 1:
            wav = np.column_stack([wav, wav])
        out = dest_dir / f"{name}.wav"
        peak = float(np.max(np.abs(wav))) if wav.size else 0.0
        if peak > 0.99:
            wav = wav * (0.99 / peak)
        sf.write(str(out), wav, sample_rate, subtype="PCM_16")
        artifacts[name] = out
    if "guitar" not in artifacts:
        raise RuntimeError("BS-RoFormer-SW did not produce a guitar stem")
    return artifacts


def _load_yaml(path: Path) -> dict:
    import yaml

    text = path.read_text(encoding="utf-8")
    try:
        from bs_roformer.inference import SafeLoaderWithTuple

        loaded = yaml.load(text, Loader=SafeLoaderWithTuple)
    except Exception:
        cleaned = text.replace("!!python/tuple", "")
        loaded = yaml.safe_load(cleaned)
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Invalid separator config at {path}")
    return loaded


def _demix_track(
    model,
    mix,
    *,
    device,
    chunk_size: int,
    n_overlap: int,
    num_stems: int,
):
    """Overlap-add inference (ZFTurbo-style). ``mix`` is (channels, samples)."""
    import numpy as np
    import torch

    channels, length = mix.shape
    fade_size = max(1, chunk_size // max(1, n_overlap))
    step = max(1, chunk_size - fade_size)
    pad_end = (fade_size - (length % fade_size)) % fade_size
    mix_p = np.pad(mix, ((0, 0), (0, pad_end)), mode="constant")
    total = mix_p.shape[1]

    window = np.ones(chunk_size, dtype=np.float32)
    fade_in = np.linspace(0.0, 1.0, fade_size, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_size, dtype=np.float32)
    window[:fade_size] = fade_in
    window[-fade_size:] = fade_out

    result = np.zeros((num_stems, channels, total), dtype=np.float32)
    counter = np.zeros(total, dtype=np.float32)

    model.eval()
    with torch.no_grad():
        for start in range(0, total, step):
            end = min(start + chunk_size, total)
            chunk = mix_p[:, start:end]
            if chunk.shape[1] < chunk_size:
                chunk = np.pad(chunk, ((0, 0), (0, chunk_size - chunk.shape[1])))
            x = torch.from_numpy(chunk.astype(np.float32)).to(device)[None]
            y = model(x)
            if isinstance(y, (tuple, list)):
                y = y[0]
            y_np = y.detach().float().cpu().numpy()
            if y_np.ndim == 4:
                y_np = y_np[0]
            elif y_np.ndim == 3:
                # (B, C, T) or (stems, C, T) already squeezed
                if y_np.shape[0] == 1:
                    y_np = y_np[0]
                if y_np.ndim == 2:
                    y_np = y_np[None, ...]
            elif y_np.ndim == 2:
                y_np = y_np[None, ...]
            sl = end - start
            w = window[:sl]
            stems_out = min(num_stems, y_np.shape[0])
            result[:stems_out, :, start:end] += y_np[:stems_out, :, :sl] * w
            counter[start:end] += w

    result /= np.maximum(counter, 1e-8)[None, None, :]
    return result[:, :, :length]


def _load_audio_stereo(path: Path, sample_rate: int):
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(str(path), always_2d=True)
    data = data.astype(np.float32)
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    elif data.shape[1] > 2:
        data = data[:, :2]
    if sr != sample_rate:
        import librosa

        left = librosa.resample(data[:, 0], orig_sr=sr, target_sr=sample_rate)
        right = librosa.resample(data[:, 1], orig_sr=sr, target_sr=sample_rate)
        n = min(len(left), len(right))
        data = np.column_stack([left[:n], right[:n]]).astype(np.float32)
    return data.T  # (channels, samples)


def _write_stems(
    sources,
    names: tuple[str, ...] | list[str],
    dest_dir: Path,
    sample_rate: int,
) -> dict[str, Path]:
    import numpy as np
    import soundfile as sf

    dest_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Path] = {}
    for idx, name in enumerate(names):
        if idx >= len(sources):
            break
        wav = sources[idx]
        if wav.ndim == 1:
            wav = np.column_stack([wav, wav])
        else:
            wav = wav.T if wav.shape[0] <= 8 else wav
            if wav.shape[1] == 1:
                wav = np.repeat(wav, 2, axis=1)
        out = dest_dir / f"{name}.wav"
        peak = float(np.max(np.abs(wav))) if wav.size else 0.0
        if peak > 0.99:
            wav = wav * (0.99 / peak)
        sf.write(str(out), wav.astype(np.float32), sample_rate, subtype="PCM_16")
        artifacts[name] = out
    return artifacts


def _instantiate_bs_roformer_model(config: dict, ckpt_path: Path, device):
    import torch
    from bs_roformer import get_model_from_config

    model_type = "bs_roformer"
    if "num_bands" in (config.get("model") or {}):
        model_type = "mel_band_roformer"
    try:
        model = get_model_from_config(model_type, config)
    except TypeError:
        # Some versions want a ConfigDict.
        from ml_collections import ConfigDict

        model = get_model_from_config(model_type, ConfigDict(config))
    try:
        state = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    except Exception:
        state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    if isinstance(state, dict):
        for key in ("state", "state_dict", "model_state_dict"):
            if key in state and isinstance(state[key], dict):
                state = state[key]
                break
    model.load_state_dict(state, strict=False)
    model.eval()
    model.to(device)
    return model


def _run_inprocess(
    audio_path: Path,
    dest_dir: Path,
    *,
    ckpt_path: Path,
    yaml_path: Path,
    device: str,
    stem_names: tuple[str, ...],
    num_stems: int,
) -> dict[str, Path]:
    """Legacy in-process demix for MelBand configs; BS-RoFormer uses infer API."""
    _cap_cpu_threads(device)
    if num_stems == 6 and is_roformer_available():
        return _run_via_bs_roformer_infer(
            audio_path,
            dest_dir,
            ckpt_path=ckpt_path,
            yaml_path=yaml_path,
            device=device,
        )

    import numpy as np

    config = _load_yaml(yaml_path)
    audio_cfg = config.get("audio") or {}
    infer_cfg = config.get("inference") or {}
    sample_rate = int(audio_cfg.get("sample_rate") or 44100)
    chunk_size = int(audio_cfg.get("chunk_size") or 485100)
    n_overlap = int(infer_cfg.get("num_overlap") or 2)
    mix = _load_audio_stereo(audio_path, sample_rate)
    dev = _torch_device(device)
    model = _instantiate_bs_roformer_model(config, ckpt_path, dev)
    sources = _demix_track(
        model,
        mix,
        device=dev,
        chunk_size=chunk_size,
        n_overlap=n_overlap,
        num_stems=num_stems,
    )
    if num_stems == 1 and len(stem_names) >= 2:
        # Specialist outputs Guitar only; Other is the residual.
        guitar = sources[0]
        residual = mix - guitar
        sources = np.stack([guitar, residual], axis=0)
        stem_names = ("guitar", "other")
    return _write_stems(sources, stem_names, dest_dir, sample_rate)


def run_bs_roformer_sw(
    audio_path: Path,
    output_root: Path,
    *,
    device: str = "cpu",
) -> dict[str, Path]:
    """
    6-stem BS-RoFormer-SW into ``output_root/bs_roformer_sw/<track>/``.

    Layout matches Demucs (``guitar.wav``, ``vocals.wav``, …) so isolate collection
    stays unchanged.
    """
    src = Path(audio_path)
    dest = Path(output_root) / BS_ROFORMER_SW_ID / src.stem
    dest.mkdir(parents=True, exist_ok=True)

    if not is_roformer_available():
        raise RuntimeError(
            "BS-RoFormer-SW requires bs-roformer-infer. " + ROFORMER_INSTALL_HINT
        )

    ckpt, yaml_path = _resolve_bs_roformer_sw_assets()
    try:
        return _run_via_bs_roformer_infer(
            src, dest, ckpt_path=ckpt, yaml_path=yaml_path, device=device
        )
    except Exception as exc:
        logger.warning("bs-roformer-infer BS-RoFormer-SW run failed: %s", exc)
        raise RuntimeError(f"BS-RoFormer-SW separation failed: {exc}") from exc


def _run_via_audio_separator(
    audio_path: Path,
    dest_dir: Path,
    *,
    ckpt_path: Path,
    yaml_path: Path | None = None,
    device: str = "cpu",
    single_stem: str | None = None,
) -> dict[str, Path]:
    from audio_separator.separator import Separator

    dest_dir.mkdir(parents=True, exist_ok=True)
    if yaml_path is not None and yaml_path.is_file():
        # audio-separator looks for a yaml next to the checkpoint.
        sidecar = ckpt_path.with_suffix(".yaml")
        if sidecar.resolve() != yaml_path.resolve():
            with suppress(OSError):
                shutil.copy2(yaml_path, sidecar)
    kwargs: dict = {
        "output_dir": str(dest_dir),
        "output_format": "WAV",
        "model_file_dir": str(ckpt_path.parent),
    }
    if single_stem:
        kwargs["output_single_stem"] = single_stem
    try:
        separator = Separator(**kwargs)
    except TypeError:
        separator = Separator(output_dir=str(dest_dir), output_format="WAV")
    separator.load_model(model_filename=ckpt_path.name)
    separator.separate(str(audio_path))
    found = collect_canonical_stems(dest_dir, dest_dir)
    if not found:
        found = collect_canonical_stems(Path(dest_dir), dest_dir)
    return found


def run_melband_guitar(
    audio_path: Path,
    output_root: Path,
    *,
    device: str = "cpu",
) -> dict[str, Path]:
    """2-stem MelBand guitar specialist → ``guitar.wav`` (+ ``other.wav`` when present)."""
    src = Path(audio_path)
    dest = Path(output_root) / MELBAND_GUITAR_ID / src.stem
    dest.mkdir(parents=True, exist_ok=True)
    ckpt, yaml_path = download_melband_guitar_weights()

    if is_roformer_available():
        try:
            found = _run_inprocess(
                src,
                dest,
                ckpt_path=ckpt,
                yaml_path=yaml_path,
                device=device,
                stem_names=("guitar", "other"),
                num_stems=1,
            )
            if "guitar" in found:
                return found
        except Exception as exc:
            logger.warning("in-process MelBand guitar failed: %s", exc)

    if is_audio_separator_available():
        found = _run_via_audio_separator(
            src,
            dest,
            ckpt_path=ckpt,
            yaml_path=yaml_path,
            device=device,
            single_stem="Guitar",
        )
        if "guitar" in found:
            return found

    raise RuntimeError(
        "MelBand guitar refine is not available. " + ROFORMER_INSTALL_HINT
    )


REFINE_OTHER_MIX_GAIN = 0.5


def refine_guitar_from_stems(
    artifacts: dict[str, Path],
    *,
    device: str = "cpu",
    work_dir: Path | None = None,
) -> dict[str, Path]:
    """Replace ``guitar`` using MelBand on guitar + residual ``other`` when present."""
    from audio_to_tab.mixer import mix_stems_to_wav

    guitar = artifacts.get("guitar")
    if guitar is None or not Path(guitar).is_file():
        return artifacts

    work = Path(work_dir) if work_dir is not None else Path(guitar).parent / "_guitar_refine"
    work.mkdir(parents=True, exist_ok=True)
    try:
        other = artifacts.get("other")
        source = Path(guitar)
        if other is not None and Path(other).is_file():
            mixed = work / "refine_input.wav"
            mix_stems_to_wav(
                {"guitar": Path(guitar), "other": Path(other)},
                output_path=mixed,
                gains={"guitar": 1.0, "other": REFINE_OTHER_MIX_GAIN},
            )
            source = mixed

        refined = run_melband_guitar(source, work / "out", device=device)
        new_guitar = refined.get("guitar")
        if new_guitar is not None and Path(new_guitar).is_file():
            shutil.copy2(new_guitar, guitar)
            artifacts["guitar"] = Path(guitar)
        new_other = refined.get("other")
        if (
            new_other is not None
            and Path(new_other).is_file()
            and other is not None
            and Path(other).is_file()
        ):
            shutil.copy2(new_other, other)
            artifacts["other"] = Path(other)
        return artifacts
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_roformer_model(
    audio_path: Path,
    output_root: Path,
    *,
    model: str,
    device: str = "cpu",
) -> dict[str, Path]:
    """Dispatch an opt-in RoFormer model into ``output_root/<model>/<track>/``."""
    src = Path(audio_path)
    root = Path(output_root)
    if model == BS_ROFORMER_SW_ID:
        return run_bs_roformer_sw(src, root, device=device)
    if model == MELBAND_GUITAR_ID:
        return run_melband_guitar(src, root, device=device)
    raise ValueError(
        f"Unsupported RoFormer model {model!r}. Choose from: {', '.join(ROFORMER_MODELS)}"
    )


def run_guitar_refine(
    guitar_path: Path,
    output_path: Path,
    *,
    residual_path: Path | None = None,
    device: str = "cpu",
) -> Path:
    """Refine a guitar stem in place (or to ``output_path``) using MelBand guitar."""
    from audio_to_tab.isolate import ensure_guitar_prerefine_backup, save_guitar_refined_backup

    guitar = Path(guitar_path)
    dest = Path(output_path)
    ensure_guitar_prerefine_backup(guitar)
    artifacts: dict[str, Path] = {"guitar": guitar}
    if residual_path is not None and Path(residual_path).is_file():
        artifacts["other"] = Path(residual_path)
    work = dest.parent / "_guitar_refine"
    refine_guitar_from_stems(artifacts, device=device, work_dir=work)
    refined = artifacts["guitar"]
    if Path(refined).resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(refined, dest)
    save_guitar_refined_backup(dest)
    return dest
