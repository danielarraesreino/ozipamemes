"""
Testes do meme_media — imagem e vídeo do PRÓPRIO meme (print de corrente).

A imagem é 100% offline (Pillow), então roda sempre. O vídeo usa ffmpeg de
verdade e é pulado quando o binário não está instalado.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PIL import Image

from skills import meme_media


@pytest.fixture
def dirs_tmp(tmp_path, monkeypatch):
    """Aponta os bancos de imagem e vídeo de meme pra diretórios temporários."""
    img = tmp_path / "meme_imagens"
    vid = tmp_path / "meme_videos"
    img.mkdir()
    vid.mkdir()
    monkeypatch.setattr(meme_media, "IMAGENS_DIR", img)
    monkeypatch.setattr(meme_media, "VIDEOS_DIR", vid)
    return img, vid


def test_gera_imagem_png_no_tamanho_certo(dirs_tmp):
    dest = meme_media.gerar_meme_imagem("m001", "Todo político é ladrão", "eleição")
    assert dest.exists()
    with Image.open(dest) as im:
        assert im.size == (meme_media.LARGURA, meme_media.ALTURA)
        assert im.format == "PNG"


def test_texto_vazio_levanta(dirs_tmp):
    with pytest.raises(ValueError):
        meme_media.gerar_meme_imagem("m002", "   ", "eleição")


def test_web_url_imagem(dirs_tmp):
    assert meme_media.web_url_imagem("m003") == ""  # ainda não existe
    meme_media.gerar_meme_imagem("m003", "Voto não muda nada", "participação")
    assert meme_media.web_url_imagem("m003") == "/meme_imagens/m003.png"


def test_overwrite_false_preserva(dirs_tmp):
    p1 = meme_media.gerar_meme_imagem("m004", "Texto A", "eleição")
    mtime = p1.stat().st_mtime_ns
    p2 = meme_media.gerar_meme_imagem("m004", "Texto B", "eleição", overwrite=False)
    assert p2 == p1
    assert p2.stat().st_mtime_ns == mtime  # não regravou


def test_quebra_texto_longo_em_varias_linhas(dirs_tmp):
    from PIL import ImageFont
    f = ImageFont.truetype(meme_media.FONTE_BOLD, 56)
    longo = "palavra " * 30
    linhas = meme_media._quebrar(longo.strip(), f, 900)
    assert len(linhas) > 1
    for linha in linhas:
        assert f.getlength(linha) <= 900


def test_modulo_desconhecido_usa_cor_padrao(dirs_tmp):
    # Não deve quebrar com módulo fora do mapa.
    dest = meme_media.gerar_meme_imagem("m005", "Meme sem módulo", "inexistente")
    assert dest.exists()


def test_delete_imagem(dirs_tmp):
    meme_media.gerar_meme_imagem("m006", "Apagável", "eleição")
    assert meme_media.imagem_path_for("m006") is not None
    assert meme_media.delete_imagem("m006") is True
    assert meme_media.imagem_path_for("m006") is None
    assert meme_media.delete_imagem("m006") is False  # já não existe


def test_list_imagens(dirs_tmp):
    meme_media.gerar_meme_imagem("m007", "Um", "eleição")
    meme_media.gerar_meme_imagem("m008", "Dois", "território")
    listadas = meme_media.list_imagens()
    assert set(listadas.keys()) == {"m007", "m008"}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg não instalado")
def test_gera_video_do_meme(dirs_tmp):
    dest = meme_media.gerar_meme_video("m009", "Vídeo do meme", "desinformação", duracao=1.0)
    assert dest.exists()
    assert dest.stat().st_size > 0
    assert meme_media.web_url_video("m009") == "/meme_videos/m009.mp4"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg não instalado")
def test_video_sem_imagem_nem_texto_levanta(dirs_tmp):
    with pytest.raises(ValueError):
        meme_media.gerar_meme_video("m010", "", "eleição")
