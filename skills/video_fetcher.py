"""
VideoFetcher — banco de vídeos da campanha, um por meme (saída do pipeline).

Espelha o image_fetcher: vídeos são arquivos locais em database/videos/{meme_id}.ext,
por convenção de filesystem (não ficam no DB, igual às imagens). Cada meme aprovado
pode ter um vídeo curto da pílula/campanha anexado, que aparece na galeria e é
exportado como video_url no dilemas.ts do jogo.
"""
from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEOS_DIR = Path(__file__).parent.parent / "database" / "videos"

# Extensões aceitas, em ordem de preferência para reprodução na web.
EXTENSOES = ("mp4", "webm", "mov", "m4v")

# Padrão de meme_id (m001, m004, …). Usado como validação fraca quando o chamador
# não passa a lista real de ids — evita importar material geral por engano.
MEME_ID_RE = re.compile(r"^m\d+$")


def video_path_for(meme_id: str) -> Path | None:
    """Retorna o Path do vídeo se já existe no banco, senão None."""
    for ext in EXTENSOES:
        p = VIDEOS_DIR / f"{meme_id}.{ext}"
        if p.exists():
            return p
    return None


def web_url_for(meme_id: str) -> str:
    """
    URL relativa pro jogo (Next.js serve a pasta public/).
    Convenção: copiar os vídeos do banco para public/videos/ no projeto do jogo.
    Retorna "" se o meme não tem vídeo.
    """
    p = video_path_for(meme_id)
    return f"/videos/{p.name}" if p else ""


def save_upload(meme_id: str, data: bytes, filename: str) -> Path:
    """Salva upload manual do Streamlit. Substitui vídeo anterior de outra extensão."""
    ext = Path(filename).suffix.lstrip(".").lower() or "mp4"
    if ext not in EXTENSOES:
        ext = "mp4"
    # Remove vídeo anterior (qualquer extensão) para não deixar órfãos.
    delete(meme_id)
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    dest = VIDEOS_DIR / f"{meme_id}.{ext}"
    dest.write_bytes(data)
    logger.info(f"Vídeo salvo: {dest} ({len(data)//1024}KB)")
    return dest


def delete(meme_id: str) -> bool:
    """Remove o vídeo do meme, se houver. Retorna True se algo foi removido."""
    removed = False
    for ext in EXTENSOES:
        p = VIDEOS_DIR / f"{meme_id}.{ext}"
        if p.exists():
            p.unlink()
            removed = True
    return removed


def ingest_folder(
    folder: str | Path,
    valid_ids: Iterable[str] | None = None,
    overwrite: bool = False,
) -> dict[str, list[str]]:
    """
    Importa um repositório de vídeos de uma pasta para o banco.
    Só importa arquivos cujo nome (sem extensão) é um meme_id válido — assim
    material geral (ex.: 'A CURIOSA HISTÓRIA DOS MEMES.mp4') não entra por engano.

    valid_ids: conjunto de meme_ids aceitos (passe db.get_approved_meme_ids() ou
    db.list_memes()). Se None, valida pelo padrão m\\d+ (m004, m012…).

    Retorna {"importados": [...], "ignorados": [...], "ja_existiam": [...]}.
    """
    folder = Path(folder)
    if not folder.is_dir():
        logger.warning(f"ingest_folder: pasta inexistente: {folder}")
        return {"importados": [], "ignorados": [], "ja_existiam": []}

    ids_ok = set(valid_ids) if valid_ids is not None else None

    def eh_meme_id(stem: str) -> bool:
        return stem in ids_ok if ids_ok is not None else bool(MEME_ID_RE.match(stem))

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    importados: list[str] = []
    ignorados: list[str] = []
    ja_existiam: list[str] = []

    for src in sorted(folder.iterdir()):
        ext = src.suffix.lstrip(".").lower()
        if not src.is_file() or ext not in EXTENSOES:
            continue
        meme_id = src.stem
        if not eh_meme_id(meme_id):
            ignorados.append(src.name)
            logger.warning(f"ingest_folder: ignorado (nome não é meme_id): {src.name}")
            continue
        if not overwrite and video_path_for(meme_id):
            ja_existiam.append(meme_id)
            continue
        delete(meme_id)
        dest = VIDEOS_DIR / f"{meme_id}.{ext}"
        shutil.copy2(src, dest)
        importados.append(meme_id)
        logger.info(f"Vídeo importado: {meme_id} ← {src.name}")

    return {"importados": importados, "ignorados": ignorados, "ja_existiam": ja_existiam}


def list_all() -> dict[str, Path]:
    """Retorna {meme_id: path} de todos os vídeos no banco."""
    if not VIDEOS_DIR.exists():
        return {}
    results: dict[str, Path] = {}
    for p in VIDEOS_DIR.iterdir():
        if p.is_file() and p.suffix.lstrip(".").lower() in EXTENSOES:
            results[p.stem] = p
    return results
