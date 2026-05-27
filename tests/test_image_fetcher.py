"""
TDD — image_fetcher.py
Testa busca, download e armazenamento de imagens de memes.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── image_path_for ─────────────────────────────────────────────────────────────

class TestImagePathFor:
    def test_encontra_jpg(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m001.jpg").write_bytes(b"fake")
        from skills.image_fetcher import image_path_for
        assert image_path_for("m001") == tmp_path / "m001.jpg"

    def test_encontra_png(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m002.png").write_bytes(b"fake")
        from skills.image_fetcher import image_path_for
        assert image_path_for("m002") == tmp_path / "m002.png"

    def test_encontra_webp(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m003.webp").write_bytes(b"fake")
        from skills.image_fetcher import image_path_for
        assert image_path_for("m003") == tmp_path / "m003.webp"

    def test_retorna_none_se_nao_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import image_path_for
        assert image_path_for("m999") is None

    def test_prioriza_jpg_sobre_outros(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m001.jpg").write_bytes(b"jpg")
        (tmp_path / "m001.png").write_bytes(b"png")
        from skills.image_fetcher import image_path_for
        assert image_path_for("m001").suffix == ".jpg"


# ── fetch_and_save ─────────────────────────────────────────────────────────────

class TestFetchAndSave:
    def _make_html_resp(self, img_url: str, prop="og:image") -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.text = f'<html><head><meta property="{prop}" content="{img_url}"/></head></html>'
        return resp

    def _make_img_resp(self, content=b"IMGDATA", content_type="image/jpeg") -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = content
        resp.headers = {"content-type": content_type}
        return resp

    def test_retorna_existente_sem_download(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m001.jpg").write_bytes(b"cached")
        from skills.image_fetcher import fetch_and_save
        with patch("skills.image_fetcher.requests.get") as mock_get:
            result = fetch_and_save("m001", "https://example.com/artigo")
            mock_get.assert_not_called()
        assert result == tmp_path / "m001.jpg"

    def test_baixa_og_image(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_and_save
        with patch("skills.image_fetcher.requests.get") as mock_get:
            mock_get.side_effect = [
                self._make_html_resp("https://cdn.example.com/meme.jpg"),
                self._make_img_resp(b"JPEG_BYTES", "image/jpeg"),
            ]
            result = fetch_and_save("m001", "https://example.com/artigo")
        assert result == tmp_path / "m001.jpg"
        assert (tmp_path / "m001.jpg").read_bytes() == b"JPEG_BYTES"

    def test_fallback_twitter_image(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_and_save
        html = '<html><head><meta name="twitter:image" content="https://cdn.example.com/img.png"/></head></html>'
        html_resp = MagicMock()
        html_resp.raise_for_status = MagicMock()
        html_resp.text = html
        img_resp = self._make_img_resp(b"PNG_BYTES", "image/png")
        with patch("skills.image_fetcher.requests.get") as mock_get:
            mock_get.side_effect = [html_resp, img_resp]
            result = fetch_and_save("m002", "https://example.com/artigo")
        assert result == tmp_path / "m002.png"

    def test_detecta_extensao_png(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_and_save
        with patch("skills.image_fetcher.requests.get") as mock_get:
            mock_get.side_effect = [
                self._make_html_resp("https://cdn.example.com/img.png"),
                self._make_img_resp(b"DATA", "image/png"),
            ]
            result = fetch_and_save("m003", "https://example.com/artigo")
        assert result.suffix == ".png"

    def test_detecta_extensao_webp(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_and_save
        with patch("skills.image_fetcher.requests.get") as mock_get:
            mock_get.side_effect = [
                self._make_html_resp("https://cdn.example.com/img.webp"),
                self._make_img_resp(b"DATA", "image/webp"),
            ]
            result = fetch_and_save("m004", "https://example.com/artigo")
        assert result.suffix == ".webp"

    def test_retorna_none_sem_imagem_na_pagina(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_and_save
        html_resp = MagicMock()
        html_resp.raise_for_status = MagicMock()
        html_resp.text = "<html><head><title>sem imagem</title></head></html>"
        with patch("skills.image_fetcher.requests.get") as mock_get:
            mock_get.return_value = html_resp
            result = fetch_and_save("m005", "https://example.com/artigo")
        assert result is None

    def test_retorna_none_em_erro_de_rede(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_and_save
        with patch("skills.image_fetcher.requests.get") as mock_get:
            mock_get.side_effect = Exception("timeout")
            result = fetch_and_save("m006", "https://example.com/artigo")
        assert result is None


# ── save_upload ────────────────────────────────────────────────────────────────

class TestSaveUpload:
    def test_salva_bytes_com_extensao_correta(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import save_upload
        result = save_upload("m001", b"PNG_DATA", "foto.png")
        assert result == tmp_path / "m001.png"
        assert result.read_bytes() == b"PNG_DATA"

    def test_salva_jpg_por_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import save_upload
        result = save_upload("m001", b"DATA", "semextensao")
        assert result.suffix == ".jpg"

    def test_sobrescreve_existente(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m001.jpg").write_bytes(b"VELHO")
        from skills.image_fetcher import save_upload
        result = save_upload("m001", b"NOVO", "foto.jpg")
        assert result.read_bytes() == b"NOVO"


# ── fetch_all ──────────────────────────────────────────────────────────────────

class TestFetchAll:
    def test_pula_memes_sem_source_url(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        from skills.image_fetcher import fetch_all
        with patch("skills.image_fetcher.requests.get") as mock_get:
            fetch_all([{"id": "m001"}, {"id": "m002", "source_url": ""}])
            mock_get.assert_not_called()

    def test_retorna_dict_id_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m001.jpg").write_bytes(b"cached")
        from skills.image_fetcher import fetch_all
        result = fetch_all([{"id": "m001", "source_url": "https://x.com"}])
        assert "m001" in result
        assert result["m001"] == tmp_path / "m001.jpg"

    def test_processa_multiplos(self, tmp_path, monkeypatch):
        monkeypatch.setattr("skills.image_fetcher.IMAGES_DIR", tmp_path)
        (tmp_path / "m001.jpg").write_bytes(b"img1")
        (tmp_path / "m002.jpg").write_bytes(b"img2")
        from skills.image_fetcher import fetch_all
        memes = [
            {"id": "m001", "source_url": "https://x.com/1"},
            {"id": "m002", "source_url": "https://x.com/2"},
            {"id": "m003"},
        ]
        result = fetch_all(memes)
        assert set(result.keys()) == {"m001", "m002"}
