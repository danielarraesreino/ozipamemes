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


def test_tts_faz_retry_no_rate_limit(monkeypatch):
    """O TTS deve esperar e tentar de novo no 429 do free tier, não falhar seco."""
    from types import SimpleNamespace
    from google.api_core import exceptions as gexc

    chamadas = {"n": 0}

    def fake_generate(**kwargs):
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise gexc.ResourceExhausted("429 free tier")
        parte = SimpleNamespace(inline_data=SimpleNamespace(data=b"PCMOK"))
        cand = SimpleNamespace(content=SimpleNamespace(parts=[parte]))
        return SimpleNamespace(candidates=[cand])

    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate))
    monkeypatch.setattr(video_gen.genai, "Client", lambda api_key: fake_client)
    monkeypatch.setattr(video_gen.time, "sleep", lambda s: None)  # não trava o teste

    assert video_gen._sintetizar_fala("oi", "fake") == b"PCMOK"
    assert chamadas["n"] == 3  # 2 falhas + 1 sucesso


def _gera_clipe_teste(dest: Path, seg: float = 2.0) -> Path:
    """Cria um MP4 curto com stream de vídeo (testsrc) pra fazer de B-roll."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=640x480:rate=30:duration={seg}",
         "-pix_fmt", "yuv420p", str(dest)],
        capture_output=True, check=True,
    )
    return dest


def test_extrai_palavras_chave_sem_stopwords():
    chaves = video_gen._extrair_palavras_chave(
        "O meme quer que você acredite que a política não muda nada na sua vida"
    )
    assert "meme" in chaves
    assert "que" not in chaves and "não" not in chaves


def test_monta_srt_valido(tmp_path):
    srt = video_gen._montar_srt("uma pílula curta pra molecada testar", 6.0, tmp_path / "s.srt")
    txt = srt.read_text(encoding="utf-8")
    assert "-->" in txt and "00:00:00,000" in txt


def test_broll_end_to_end(videos_tmp, fala_mock, monkeypatch, tmp_path):
    """Pexels e download mockados; ffmpeg (normalizar+concat+legenda) roda de verdade."""
    fonte = _gera_clipe_teste(tmp_path / "fonte.mp4")
    monkeypatch.setattr(video_gen, "_pexels_buscar_clipes",
                        lambda query, api_key, n, locale="pt-BR": ["fake://1", "fake://2"])
    monkeypatch.setattr(video_gen, "_baixar", lambda url, dest: shutil.copy(fonte, dest) or dest)

    dest = video_gen.gerar_video(
        "m010", "Pílula com fundo de vídeo e legenda.",
        api_key="fake", estilo="broll", pexels_key="x",
    )
    assert dest.exists() and dest.stat().st_size > 0
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", str(dest)],
        capture_output=True, text=True,
    )
    assert "audio" in probe.stdout  # narração foi muxada


def test_broll_sem_chave_cai_pra_imagem(videos_tmp, fala_mock):
    """estilo='broll' sem PEXELS_API_KEY não falha — usa o modo imagem (fallback)."""
    dest = video_gen.gerar_video(
        "m011", "Sem chave.", api_key="fake", estilo="broll", pexels_key="", imagem=None,
    )
    assert dest.exists()


def test_tts_desiste_apos_retries(monkeypatch):
    from google.api_core import exceptions as gexc

    def sempre_429(**kwargs):
        raise gexc.ResourceExhausted("429")

    from types import SimpleNamespace
    fake_client = SimpleNamespace(models=SimpleNamespace(generate_content=sempre_429))
    monkeypatch.setattr(video_gen.genai, "Client", lambda api_key: fake_client)
    monkeypatch.setattr(video_gen.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError, match="rate limit"):
        video_gen._sintetizar_fala("oi", "fake", retries=2)
