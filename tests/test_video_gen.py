"""
Testes do video_gen — gera o vídeo da pílula (TTS + ffmpeg).

A narração (única fronteira de rede) é mockada com PCM silencioso; o ffmpeg roda
de verdade, então estes testes exercitam a montagem do MP4 offline.
"""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from skills import video_gen, video_fetcher

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg não instalado"
)


def _pcm_silencioso(segundos: float = 0.3) -> bytes:
    """PCM 24kHz/mono/16-bit de silêncio (zeros)."""
    return b"\x00" * int(video_gen.TTS_SAMPLE_RATE * segundos) * video_gen.TTS_BYTES_POR_AMOSTRA


@pytest.fixture
def videos_tmp(tmp_path, monkeypatch):
    """Aponta o banco de vídeos pra um diretório temporário nos dois módulos."""
    d = tmp_path / "videos"
    d.mkdir()
    monkeypatch.setattr(video_gen, "VIDEOS_DIR", d)
    monkeypatch.setattr(video_fetcher, "VIDEOS_DIR", d)
    return d


@pytest.fixture
def fala_mock(monkeypatch):
    """Substitui o TTS por PCM silencioso — sem rede."""
    monkeypatch.setattr(video_gen, "_sintetizar_fala", lambda texto, api_key, voz: _pcm_silencioso())


@pytest.fixture
def imagem_teste(tmp_path):
    """Gera um JPG pequeno via ffmpeg pra testar o ramo com imagem."""
    img = tmp_path / "fundo.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x240", "-frames:v", "1", str(img)],
        capture_output=True, check=True,
    )
    return img


def test_pcm_para_wav_valido(tmp_path):
    wav = video_gen._pcm_para_wav(_pcm_silencioso(0.2), tmp_path / "a.wav")
    with wave.open(str(wav), "rb") as w:
        assert w.getframerate() == video_gen.TTS_SAMPLE_RATE
        assert w.getnchannels() == video_gen.TTS_CANAIS
        assert w.getnframes() > 0


def test_gera_video_com_imagem(videos_tmp, fala_mock, imagem_teste):
    dest = video_gen.gerar_video(
        "m001", "Pílula de teste.", api_key="fake", imagem=imagem_teste,
    )
    assert dest.exists() and dest.suffix == ".mp4"
    assert dest.stat().st_size > 0
    assert video_fetcher.video_path_for("m001") == dest


def test_gera_video_sem_imagem_usa_fallback(videos_tmp, fala_mock):
    dest = video_gen.gerar_video("m002", "Sem imagem.", api_key="fake", imagem=None)
    assert dest.exists()
    # ffmpeg conseguiu ler o MP4 (probe não falha).
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(dest)],
        capture_output=True, text=True,
    )
    assert probe.returncode == 0


def test_texto_vazio_levanta(videos_tmp, fala_mock):
    with pytest.raises(ValueError):
        video_gen.gerar_video("m003", "   ", api_key="fake")


def test_sobrescreve_video_anterior(videos_tmp, fala_mock):
    (videos_tmp / "m004.webm").write_bytes(b"antigo")
    dest = video_gen.gerar_video("m004", "Novo.", api_key="fake", imagem=None)
    assert dest.exists()
    # o vídeo antigo (.webm) foi removido pra não deixar órfão
    assert not (videos_tmp / "m004.webm").exists()


def test_sem_overwrite_recusa(videos_tmp, fala_mock):
    (videos_tmp / "m005.mp4").write_bytes(b"existe")
    with pytest.raises(FileExistsError):
        video_gen.gerar_video("m005", "X.", api_key="fake", overwrite=False)
