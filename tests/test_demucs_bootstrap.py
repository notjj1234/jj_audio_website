"""Regression tests for the Demucs WAV-writer workaround.

torchaudio >= 2.9 saves through torchcodec, whose wheels support FFmpeg 4-8.
With FFmpeg 9, Demucs finished separating and then crashed while writing the
stems. These tests pin the soundfile-backed writer and the subprocess bootstrap.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import soundfile as sf
import torch

from audio_to_tab.demucs_bootstrap import install_soundfile_writer, save_audio
from audio_to_tab.separate import run_demucs


def test_save_audio_writes_stereo_wav(tmp_path):
    wav = torch.zeros(2, 1000)
    wav[0] = 0.5
    wav[1] = -0.5
    out = tmp_path / "stem.wav"

    save_audio(wav, out, samplerate=44100)

    data, sr = sf.read(out, always_2d=True)
    assert sr == 44100
    assert data.shape == (1000, 2)
    assert np.max(np.abs(data)) <= 1.0


def test_save_audio_rescales_hot_signal(tmp_path):
    wav = torch.full((1, 100), 4.0)
    out = tmp_path / "hot.wav"

    save_audio(wav, out, samplerate=8000)

    data, _ = sf.read(out)
    assert np.max(np.abs(data)) <= 1.0
    assert np.max(np.abs(data)) > 0.9


def test_install_patches_demucs_module_references(monkeypatch):
    import demucs.audio
    import demucs.separate

    monkeypatch.setattr(demucs.audio, "save_audio", demucs.audio.save_audio)
    monkeypatch.setattr(demucs.separate, "save_audio", demucs.separate.save_audio)

    install_soundfile_writer()

    assert demucs.audio.save_audio is save_audio
    assert demucs.separate.save_audio is save_audio


def test_run_demucs_subprocess_uses_soundfile_bootstrap(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_process(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("audio_to_tab.separate.run_process", fake_run_process)

    run_demucs(["-n", "htdemucs_6s", "song.wav"])

    cmd = captured["cmd"]
    assert cmd[0].endswith("python") or "python" in str(cmd[0])
    assert cmd[1:4] == ["-m", "audio_to_tab.demucs_bootstrap", "-n"]
    assert cmd[4:] == ["htdemucs_6s", "song.wav"]
