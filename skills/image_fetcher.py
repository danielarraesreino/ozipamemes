"""
ImageFetcher — busca a imagem do meme a partir da URL do artigo de fact-check.
Extrai og:image (Open Graph) que é sempre a imagem principal do artigo,
geralmente um screenshot do meme circulando nas redes.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

IMAGES_DIR = Path(__file__).parent.parent / "database" / "images"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
TIMEOUT = 15


def image_path_for(meme_id: str) -> Path | None:
    """Retorna o Path da imagem se ela já foi baixada, senão None."""
    for ext in ("jpg", "jpeg", "png", "webp", "gif"):
        p = IMAGES_DIR / f"{meme_id}.{ext}"
        if p.exists():
            return p
    return None


def fetch_and_save(meme_id: str, source_url: str) -> Path | None:
    """
    Baixa a og:image do artigo em source_url e salva em database/images/{meme_id}.ext
    Retorna o Path salvo ou None se falhar.
    """
    existing = image_path_for(meme_id)
    if existing:
        return existing

    try:
        resp = requests.get(source_url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        img_url = None
        # Prioridade: og:image → twitter:image → primeira <img> do artigo
        for prop in ("og:image", "twitter:image"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                img_url = tag["content"]
                break

        if not img_url:
            # Fallback: primeira imagem do artigo com tamanho razoável
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if src.startswith("http") and not any(x in src for x in ("logo", "icon", "avatar", "banner")):
                    img_url = src
                    break

        if not img_url:
            logger.warning(f"Nenhuma imagem encontrada em {source_url}")
            return None

        # Garante URL absoluta
        if img_url.startswith("//"):
            img_url = "https:" + img_url

        img_resp = requests.get(img_url, headers=HEADERS, timeout=TIMEOUT)
        img_resp.raise_for_status()

        content_type = img_resp.headers.get("content-type", "")
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "webp" in content_type:
            ext = "webp"
        elif "gif" in content_type:
            ext = "gif"

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        dest = IMAGES_DIR / f"{meme_id}.{ext}"
        dest.write_bytes(img_resp.content)
        logger.info(f"Imagem salva: {dest} ({len(img_resp.content)//1024}KB)")
        return dest

    except Exception as exc:
        logger.warning(f"fetch_and_save falhou para {meme_id}: {exc}")
        return None


def save_upload(meme_id: str, data: bytes, filename: str) -> Path:
    """Salva upload manual do Streamlit."""
    ext = Path(filename).suffix.lstrip(".") or "jpg"
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = IMAGES_DIR / f"{meme_id}.{ext}"
    dest.write_bytes(data)
    return dest


def fetch_all(memes: list[dict]) -> dict[str, Path]:
    """Busca imagens para todos os memes com source_url. Retorna {meme_id: path}."""
    results: dict[str, Path] = {}
    for m in memes:
        meme_id = m.get("id", "")
        source_url = m.get("source_url", "")
        if not source_url:
            continue
        path = fetch_and_save(meme_id, source_url)
        if path:
            results[meme_id] = path
    return results
