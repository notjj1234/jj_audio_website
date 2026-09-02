"""Optional SCNet backend for guitar isolation (opt-in, not the default).

2026-08-30: ``htdemucs_6s`` remains the default first-stage separator. SCNet is
an alternative opt-in engine for dense mixes — a ~10.6M-param frequency-domain
model (starrytong "Sparse Compression Network", arXiv:2401.13276, MIT) trained
on MUSDB18 (avg 9.03 dB vs htdemucs_6s ≈5.25 dB guitar SDR). Tree: ``guitar_scnet``.

SCNet is a 4-stem model (drums / bass / other / vocals); guitar content lives
in its ``other`` stem, so the backend renames that stem to ``guitar.wav`` and
also emits the drums/bass/vocals stems for the downstream bleed gate / fold
diagnostics. The MSST (Music-Source-Separation-Training) implementation of the
architecture is recreated here so it matches the published checkpoint state-dict
(the MSST ``models/scnet`` reference has no released weights).

Integration mirrors ``roformer.py``: weights are urllib + SHA256-pinned (no
``huggingface_hub``) and cached under ``separator_cache_dir()``. Runtime needs
torch only (optional extra ``[scnet]``).
"""

from __future__ import annotations

import importlib.util
import logging
from collections import deque
from pathlib import Path

import numpy as np

from audio_to_tab.roformer import download_sha256_file, separator_cache_dir

logger = logging.getLogger(__name__)

SCNET_MODEL_ID = "guitar_scnet"
SCNET_MODELS = (SCNET_MODEL_ID,)
# Source order of the published musdb18 checkpoint (matches its MSST config).
SCNET_SOURCES = ("drums", "bass", "other", "vocals")
# SCNet has no dedicated guitar head; the non-rhythm-section ``other`` stem is
# what actual guitar content lands in (drum/bass/vocal sections are the paths
# htdemucs also calls "other", so this is a fuzzier mapping than a dedicated
# guitar-stem model — opt-in only, never the default).
SCNET_GUITAR_FROM_STEM = "other"

SCNET_CKPT_NAME = "scnet_checkpoint_musdb18.ckpt"
SCNET_CKPT_URL = (
    "https://huggingface.co/Politrees/UVR_resources/resolve/main/"
    f"models/SCnet/{SCNET_CKPT_NAME}"
)
# Published in the Politrees/UVR_resources model metadata (re-verified locally).
SCNET_CKPT_SHA256 = "1bc0d1abb20bfdf966dcd07637bafd03e4bc13653d09ef18bc9b3e342eafe2aa"
# 42 MB. Trained at 44.1 kHz (MSST musdb18 config).
SCNET_SAMPLE_RATE = 44100

SCNET_INSTALL_HINT = (
    "SCNet guitar isolation needs the optional extra (loaded torch runtime): "
    'pip install -e ".[scnet]"'
)

# MSST scnet musdb18 inference settings (config_musdb18_scnet.yaml).
SCNET_CHUNK_SIZE = 485100  # 44100 * 11
SCNET_NUM_OVERLAP = 4
SCNET_FADE_SIZE = SCNET_CHUNK_SIZE // 10  # linear fade-in/out
SCNET_STEP = SCNET_CHUNK_SIZE // SCNET_NUM_OVERLAP

_USER_AGENT = "audio-to-tab-pdf/1.0 (guitar isolation; urllib)"
_SCNET_STEMS_WRITE_ORDER = ("drums", "bass", "guitar", "vocals")


def is_scnet_available() -> bool:
    """True when torch is importable (the SCNet runtime dependency)."""
    return importlib.util.find_spec("torch") is not None


def scnet_weights_path() -> Path:
    """Local cache location for the SCNet checkpoint (not committed)."""
    return separator_cache_dir() / SCNET_MODEL_ID / SCNET_CKPT_NAME


def download_scnet_weights(*, force: bool = False) -> Path:
    """Download the SCNet checkpoint (urllib, SHA256-pinned)."""
    ckpt = scnet_weights_path()
    if force:
        ckpt.unlink(missing_ok=True)
    download_sha256_file(SCNET_CKPT_URL, ckpt, SCNET_CKPT_SHA256)
    return ckpt


def load_scnet_model(ckpt_path: Path, device: str):
    """Build the SCNet architecture and load ``ckpt_path`` strictly."""
    import torch

    state = torch.load(str(ckpt_path), map_location="cpu", weights_only=True)
    if isinstance(state, dict):
        for key in ("state", "state_dict", "model_state_dict"):
            if key in state and isinstance(state[key], dict):
                state = state[key]
                break
    model = _scnet_architecture_module()
    missing, unexpected = model.load_state_dict(state, strict=True)
    if missing or unexpected:
        raise RuntimeError(
            "SCNet checkpoint keys do not match the recreated architecture "
            f"({len(missing)} missing, {len(unexpected)} unexpected)"
        )
    model.eval()
    return model.to(device)


def run_scnet_model(
    audio_path: Path,
    output_root: Path,
    *,
    device: str = "cpu",
) -> dict[str, Path]:
    """
    4-stem SCNet into ``output_root/guitar_scnet/<track>/``.

    The SCNet ``other`` stem is written as ``guitar.wav``, alongside the drum /
    bass / vocal stems. Layout matches Demucs so isolate collection is unchanged.
    """
    src = Path(audio_path)
    dest = Path(output_root) / SCNET_MODEL_ID / src.stem
    dest.mkdir(parents=True, exist_ok=True)

    if not is_scnet_available():
        raise RuntimeError(f"SCNet requires torch. {SCNET_INSTALL_HINT}")

    ckpt = download_scnet_weights()
    dev = _torch_device(device)
    model = load_scnet_model(ckpt, dev)

    mix = _load_audio_stereo(src, SCNET_SAMPLE_RATE)
    mix, (mean, std) = _msst_normalize(mix)
    sources = _demix_scnet(model, mix, dev)
    denormalized = sources * std + mean

    stems: dict[str, Path] = {}
    for name in _SCNET_STEMS_WRITE_ORDER:
        index = SCNET_SOURCES.index(name if name != "guitar" else SCNET_GUITAR_FROM_STEM)
        stems[name] = _write_stem(denormalized[index], dest, name, SCNET_SAMPLE_RATE)
    return stems


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


def _msst_normalize(mix: np.ndarray) -> tuple[np.ndarray, tuple[float, float]]:
    """MSST normalize_audio: whole-track mono mean/std (same for all channels)."""
    mono = mix.mean(0)
    mean = float(mono.mean())
    std = float(mono.std())
    if std <= 1e-12:
        return mix, (mean, std)
    return (mix - mean) / std, (mean, std)


def _demix_scnet(model, mix, device) -> np.ndarray:
    """MSST generic-chunk overlap-add inference (batch_size=1, identical math)."""
    import torch
    import torch.nn.functional as F

    chunk_size = SCNET_CHUNK_SIZE
    fade_size = SCNET_FADE_SIZE
    step = SCNET_STEP
    border = chunk_size - step

    mix = torch.tensor(mix, dtype=torch.float32)
    length_init = mix.shape[-1]
    windowing_array = torch.ones(chunk_size, dtype=torch.float32)
    windowing_array[:fade_size] = torch.linspace(0, 1, fade_size, dtype=torch.float32)
    windowing_array[-fade_size:] = torch.linspace(1, 0, fade_size, dtype=torch.float32)

    applied_border = 0
    if length_init > 2 * border and border > 0:
        mix = F.pad(mix, (border, border), mode="reflect")
        applied_border = border

    num_instruments = len(SCNET_SOURCES)
    result = torch.zeros((num_instruments, *mix.shape), dtype=torch.float32)
    counter = torch.zeros(mix.shape[1], dtype=torch.float32)

    batch: list[torch.Tensor] = []
    locations: list[tuple[int, int]] = []
    model.eval()
    with torch.inference_mode():
        i = 0
        total = mix.shape[1]
        while i < total:
            part = mix[:, i : i + chunk_size].to(device)
            chunk_len = part.shape[-1]
            pad_mode = "reflect" if chunk_len > chunk_size // 2 else "constant"
            part = F.pad(part, (0, chunk_size - chunk_len), mode=pad_mode, value=0)
            batch.append(part)
            locations.append((i, chunk_len))
            i += step

            if len(batch) >= 1 or i >= total:
                arr = torch.stack(batch, dim=0)
                x = model(arr)
                window = windowing_array.clone()
                if i - step == 0:  # first chunk: no fade-in
                    window[:fade_size] = 1
                elif i >= total:  # last chunk: no fade-out
                    window[-fade_size:] = 1
                for j, (start, seg_len) in enumerate(locations):
                    result[..., start : start + seg_len] += (
                        x[j, ..., :seg_len].float().cpu() * window[..., :seg_len]
                    )
                    counter[start : start + seg_len] += window[..., :seg_len]
                batch.clear()
                locations.clear()

    counter = torch.clamp(counter, min=1e-8)
    estimated = result / counter.unsqueeze(0).unsqueeze(0)
    estimated = estimated.cpu().numpy()
    np.nan_to_num(estimated, copy=False, nan=0.0)
    if applied_border:
        estimated = estimated[..., applied_border:-applied_border]
    return estimated


def _write_stem(samples: np.ndarray, dest_dir: Path, name: str, sample_rate: int) -> Path:
    import soundfile as sf

    wav = samples
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
    return out


def _scnet_architecture_module():
    """Recreate the MSST ``models/scnet`` SCNet that matches the checkpoint.

    All torch imports are local: importing ``audio_to_tab.scnet`` must not
    require torch (that would break ``import audio_to_tab.isolate`` on hosts
    without the ``[scnet]`` extra).
    """
    import math

    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class Swish(nn.Module):
        def forward(self, x):
            return x * x.sigmoid()

    class ConvolutionModule(nn.Module):
        def __init__(self, channels, depth=2, compress=4, kernel=3):
            super().__init__()
            assert kernel % 2 == 1
            self.depth = abs(depth)
            hidden_size = int(channels / compress)
            self.layers = nn.ModuleList([])
            for _ in range(self.depth):
                padding = kernel // 2
                mods = [
                    nn.GroupNorm(1, channels),
                    nn.Conv1d(channels, hidden_size * 2, kernel, padding=padding),
                    nn.GLU(1),
                    nn.Conv1d(hidden_size, hidden_size, kernel, padding=padding, groups=hidden_size),
                    nn.GroupNorm(1, hidden_size),
                    Swish(),
                    nn.Conv1d(hidden_size, channels, 1),
                ]
                self.layers.append(nn.Sequential(*mods))

        def forward(self, x):
            for layer in self.layers:
                x = x + layer(x)
            return x

    class FusionLayer(nn.Module):
        def __init__(self, channels, kernel_size=3, stride=1, padding=1):
            super().__init__()
            self.conv = nn.Conv2d(channels * 2, channels * 2, kernel_size, stride=stride, padding=padding)

        def forward(self, x, skip=None):
            if skip is not None:
                x += skip
            x = x.repeat(1, 2, 1, 1)
            x = self.conv(x)
            return F.glu(x, dim=1)

    class SDlayer(nn.Module):
        def __init__(self, channels_in, channels_out, band_configs):
            super().__init__()
            self.convs = nn.ModuleList()
            self.strides = []
            self.kernels = []
            for config in band_configs.values():
                self.convs.append(
                    nn.Conv2d(channels_in, channels_out, (config["kernel"], 1), (config["stride"], 1), (0, 0))
                )
                self.strides.append(config["stride"])
                self.kernels.append(config["kernel"])
            self.SR_low = band_configs["low"]["SR"]
            self.SR_mid = band_configs["mid"]["SR"]

        def forward(self, x):
            _, _, Fr, _ = x.shape
            splits = [
                (0, math.ceil(Fr * self.SR_low)),
                (math.ceil(Fr * self.SR_low), math.ceil(Fr * (self.SR_low + self.SR_mid))),
                (math.ceil(Fr * (self.SR_low + self.SR_mid)), Fr),
            ]
            outputs = []
            original_lengths = []
            for (start, end), conv, stride, kernel in zip(
                    splits, self.convs, self.strides, self.kernels, strict=True
                ):
                extracted = x[:, :, start:end, :]
                original_lengths.append(end - start)
                current_length = extracted.shape[2]
                if stride == 1:
                    total_padding = kernel - stride
                else:
                    total_padding = (stride - current_length % stride) % stride
                pad_left = total_padding // 2
                pad_right = total_padding - pad_left
                padded = F.pad(extracted, (0, 0, pad_left, pad_right))
                outputs.append(conv(padded))
            return outputs, original_lengths

    class SUlayer(nn.Module):
        def __init__(self, channels_in, channels_out, band_configs):
            super().__init__()
            self.convtrs = nn.ModuleList(
                [
                    nn.ConvTranspose2d(channels_in, channels_out, [config["kernel"], 1], [config["stride"], 1])
                    for config in band_configs.values()
                ]
            )

        def forward(self, x, lengths, origin_lengths):
            splits = [
                (0, lengths[0]),
                (lengths[0], lengths[0] + lengths[1]),
                (lengths[0] + lengths[1], None),
            ]
            outputs = []
            for idx, (convtr, (start, end)) in enumerate(zip(self.convtrs, splits, strict=True)):
                out = convtr(x[:, :, start:end, :])
                current_fr_length = out.shape[2]
                dist = abs(origin_lengths[idx] - current_fr_length) // 2
                outputs.append(out[:, :, dist : dist + origin_lengths[idx], :])
            return torch.cat(outputs, dim=2)

    class SDblock(nn.Module):
        def __init__(self, channels_in, channels_out, band_configs, conv_config, depths, kernel_size=3):
            super().__init__()
            self.SDlayer = SDlayer(channels_in, channels_out, band_configs)
            self.conv_modules = nn.ModuleList(
                [ConvolutionModule(channels_out, depth, **conv_config) for depth in depths]
            )
            self.globalconv = nn.Conv2d(channels_out, channels_out, kernel_size, 1, (kernel_size - 1) // 2)

        def forward(self, x):
            bands, original_lengths = self.SDlayer(x)
            bands = [
                F.gelu(
                    conv(band.permute(0, 2, 1, 3).reshape(-1, band.shape[1], band.shape[3]))
                    .view(band.shape[0], band.shape[2], band.shape[1], band.shape[3])
                    .permute(0, 2, 1, 3)
                )
                for conv, band in zip(self.conv_modules, bands, strict=True)
            ]
            lengths = [band.size(-2) for band in bands]
            full_band = torch.cat(bands, dim=2)
            skip = full_band
            output = self.globalconv(full_band)
            return output, skip, lengths, original_lengths

    class FeatureConversion(nn.Module):
        def __init__(self, channels, inverse):
            super().__init__()
            self.inverse = inverse
            self.channels = channels

        def forward(self, x):
            if self.inverse:
                x = x.float()
                x_r = x[:, : self.channels // 2, :, :]
                x_i = x[:, self.channels // 2 :, :, :]
                x = torch.complex(x_r, x_i)
                x = torch.fft.irfft(x, dim=3, norm="ortho")
            else:
                x = x.float()
                x = torch.fft.rfft(x, dim=3, norm="ortho")
                x_real = x.real
                x_imag = x.imag
                x = torch.cat([x_real, x_imag], dim=1)
            return x

    class DualPathRNN(nn.Module):
        def __init__(self, d_model, expand, bidirectional=True):
            super().__init__()
            self.d_model = d_model
            self.hidden_size = d_model * expand
            self.bidirectional = bidirectional
            self.lstm_layers = nn.ModuleList(
                [nn.LSTM(d_model, self.hidden_size, num_layers=1, bidirectional=self.bidirectional, batch_first=True) for _ in range(2)]
            )
            self.linear_layers = nn.ModuleList([nn.Linear(self.hidden_size * 2, d_model) for _ in range(2)])
            self.norm_layers = nn.ModuleList([nn.GroupNorm(1, d_model) for _ in range(2)])

        def forward(self, x):
            B, C, F, T = x.shape
            original_x = x
            x = self.norm_layers[0](x)
            x = x.transpose(1, 3).contiguous().view(B * T, F, C)
            x, _ = self.lstm_layers[0](x)
            x = self.linear_layers[0](x)
            x = x.view(B, T, F, C).transpose(1, 3)
            x = x + original_x

            original_x = x
            x = self.norm_layers[1](x)
            x = x.transpose(1, 2).contiguous().view(B * F, C, T).transpose(1, 2)
            x, _ = self.lstm_layers[1](x)
            x = self.linear_layers[1](x)
            x = x.transpose(1, 2).contiguous().view(B, F, C, T).transpose(1, 2)
            x = x + original_x
            return x

    class SeparationNet(nn.Module):
        def __init__(self, channels, expand=1, num_layers=6):
            super().__init__()
            self.num_layers = num_layers
            self.dp_modules = nn.ModuleList(
                [DualPathRNN(channels * (2 if i % 2 == 1 else 1), expand) for i in range(num_layers)]
            )
            self.feature_conversion = nn.ModuleList(
                [FeatureConversion(channels * 2, inverse=i % 2 != 0) for i in range(num_layers)]
            )

        def forward(self, x):
            for i in range(self.num_layers):
                x = self.dp_modules[i](x)
                x = self.feature_conversion[i](x)
            return x

    class SCNet(nn.Module):
        def __init__(
            self,
            sources=None,
            audio_channels=2,
            dims=None,
            nfft=4096,
            hop_size=1024,
            win_size=4096,
            normalized=True,
            band_SR=None,
            band_stride=None,
            band_kernel=None,
            conv_depths=None,
            compress=4,
            conv_kernel=3,
            num_dplayer=6,
            expand=1,
        ):
            super().__init__()
            self.sources = list(sources or ["drums", "bass", "other", "vocals"])
            self.audio_channels = audio_channels
            self.dims = list(dims or [4, 32, 64, 128])
            band_keys = ["low", "mid", "high"]
            band_SR = band_SR or [0.175, 0.392, 0.433]
            band_stride = band_stride or [1, 4, 16]
            band_kernel = band_kernel or [3, 4, 16]
            self.band_configs = {
                band_keys[i]: {"SR": band_SR[i], "stride": band_stride[i], "kernel": band_kernel[i]}
                for i in range(len(band_keys))
            }
            self.hop_length = hop_size
            self.conv_config = {"compress": compress, "kernel": conv_kernel}
            self.stft_config = {
                "n_fft": nfft,
                "hop_length": hop_size,
                "win_length": win_size,
                "center": True,
                "normalized": normalized,
            }
            self.encoder = nn.ModuleList()
            self.decoder = nn.ModuleList()
            conv_depths = list(conv_depths or [3, 2, 1])
            for index in range(len(self.dims) - 1):
                enc = SDblock(
                    channels_in=self.dims[index],
                    channels_out=self.dims[index + 1],
                    band_configs=self.band_configs,
                    conv_config=self.conv_config,
                    depths=conv_depths,
                )
                self.encoder.append(enc)
                dec = nn.Sequential(
                    FusionLayer(channels=self.dims[index + 1]),
                    SUlayer(
                        channels_in=self.dims[index + 1],
                        channels_out=self.dims[index] if index != 0 else self.dims[index] * len(self.sources),
                        band_configs=self.band_configs,
                    ),
                )
                self.decoder.insert(0, dec)
            self.separation_net = SeparationNet(channels=self.dims[-1], expand=expand, num_layers=num_dplayer)

        def forward(self, x):
            B = x.shape[0]
            padding = self.hop_length - x.shape[-1] % self.hop_length
            if (x.shape[-1] + padding) // self.hop_length % 2 == 0:
                padding += self.hop_length
            x = F.pad(x, (0, padding))
            L = x.shape[-1]
            x = x.reshape(-1, L)
            x = torch.stft(x, **self.stft_config, return_complex=True)
            x = torch.view_as_real(x)
            x = x.permute(0, 3, 1, 2).reshape(
                x.shape[0] // self.audio_channels,
                x.shape[3] * self.audio_channels,
                x.shape[1],
                x.shape[2],
            )
            B, _, Fr, T = x.shape
            save_skip = deque()
            save_lengths = deque()
            save_original_lengths = deque()
            for sd_layer in self.encoder:
                x, skip, lengths, original_lengths = sd_layer(x)
                save_skip.append(skip)
                save_lengths.append(lengths)
                save_original_lengths.append(original_lengths)
            x = self.separation_net(x)
            for fusion_layer, su_layer in self.decoder:
                x = fusion_layer(x, save_skip.pop())
                x = su_layer(x, save_lengths.pop(), save_original_lengths.pop())
            n = self.dims[0]
            x = x.view(B, n, -1, Fr, T)
            x = x.reshape(-1, 2, Fr, T).permute(0, 2, 3, 1)
            x = torch.view_as_complex(x.contiguous())
            x = torch.istft(x, **self.stft_config)
            x = x.reshape(B, len(self.sources), self.audio_channels, -1)
            x = x[:, :, :, :-padding]
            return x

    return SCNet()