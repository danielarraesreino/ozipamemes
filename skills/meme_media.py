"""
Gerador de mídia do PRÓPRIO meme — imagem e vídeo no estilo "print de corrente".

Diferente de:
  - skills/video_gen.py  → vídeo da PÍLULA (narração TTS, exibido após a escolha)
  - skills/video_fetcher → banco de vídeos manuais

Aqui geramos o visual do meme em si (o "print" que viraliza no zap), pra preencher
os campos meme_imagem / meme_video do card do jogo. Tudo offline (Pillow + ffmpeg),
sem API e sem custo, espelhando o visual do SwipeCard do jogo.

Saídas:
  database/meme_imagens/{meme_id}.png   (1080x1350, 4:5)
  database/meme_videos/{meme_id}.mp4    (zoom suave sobre a imagem)

URLs no jogo (Next serve public/):
  /meme_imagens/{id}.png   ·   /meme_videos/{id}.mp4
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

IMAGENS_DIR = Path(__file__).parent.parent / "database" / "meme_imagens"
VIDEOS_DIR = Path(__file__).parent.parent / "database" / "meme_videos"

LARGURA, ALTURA = 1080, 1350

# Cores espelhando o jogo (globals.css / MODULO_COR do SwipeCard).
COR_FUNDO = (15, 15, 16)        # #0F0F10
COR_CARD = (28, 28, 30)         # #1C1C1E
COR_BORDA = (44, 44, 46)        # #2C2C2E
COR_BOLHA = (11, 20, 26)        # #0B141A (estilo WhatsApp)
COR_BOLHA_BORDA = (34, 45, 52)  # #222D34
COR_TEXTO = (245, 240, 232)     # #F5F0E8
COR_SECUNDARIA = (134, 150, 160)  # #8696A0
COR_FRACA = (85, 85, 85)        # #555

MODULO_COR = {
    "participação": (45, 212, 160), "participacao": (45, 212, 160),
    "desinformação": (232, 64, 64), "desinformacao": (232, 64, 64),
    "eleição": (59, 130, 246), "eleicao": (59, 130, 246),
    "território": (245, 158, 11), "territorio": (245, 158, 11),
}
COR_MODULO_PADRAO = (136, 136, 136)

FONTE_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTE_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def imagem_path_for(meme_id: str) -> Path | None:
    p = IMAGENS_DIR / f"{meme_id}.png"
    return p if p.exists() else None


def video_path_for(meme_id: str) -> Path | None:
    p = VIDEOS_DIR / f"{meme_id}.mp4"
    return p if p.exists() else None


def web_url_imagem(meme_id: str) -> str:
    p = imagem_path_for(meme_id)
    return f"/meme_imagens/{p.name}" if p else ""


def web_url_video(meme_id: str) -> str:
    p = video_path_for(meme_id)
    return f"/meme_videos/{p.name}" if p else ""


def _fonte(caminho: str, tam: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(caminho, tam)
    except OSError:
        return ImageFont.load_default()


def _quebrar(texto: str, fonte: ImageFont.FreeTypeFont, largura_max: int) -> list[str]:
    """Quebra o texto em linhas que cabem em largura_max (px)."""
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if fonte.getlength(teste) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def gerar_meme_imagem(
    meme_id: str,
    texto: str,
    modulo: str = "",
    *,
    overwrite: bool = True,
    dest_dir: Path | None = None,
) -> Path:
    """Renderiza o meme como 'print de corrente' e salva PNG 1080x1350."""
    if not texto or not texto.strip():
        raise ValueError("texto do meme vazio")

    destino_dir = dest_dir or IMAGENS_DIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    dest = destino_dir / f"{meme_id}.png"
    if dest.exists() and not overwrite:
        return dest

    cor_mod = MODULO_COR.get(modulo.strip().lower(), COR_MODULO_PADRAO)

    img = Image.new("RGB", (LARGURA, ALTURA), COR_FUNDO)
    d = ImageDraw.Draw(img)

    margem = 60
    # Card de fundo
    d.rounded_rectangle(
        [margem, margem, LARGURA - margem, ALTURA - margem],
        radius=40, fill=COR_CARD, outline=COR_BORDA, width=2,
    )

    cx0 = margem + 50  # conteúdo interno
    cx1 = LARGURA - margem - 50
    largura_conteudo = cx1 - cx0

    # ── Barra superior: bolinha do módulo + nome + "encaminhada"
    topo = margem + 50
    f_mono = _fonte(FONTE_BOLD, 26)
    raio = 26
    d.ellipse([cx0, topo, cx0 + raio * 2, topo + raio * 2], fill=cor_mod)
    inicial = (modulo[:1].upper() or "?")
    bb = d.textbbox((0, 0), inicial, font=f_mono)
    d.text(
        (cx0 + raio - (bb[2] - bb[0]) / 2, topo + raio - (bb[3] - bb[1]) / 2 - bb[1]),
        inicial, font=f_mono, fill=(0, 0, 0),
    )
    d.text((cx0 + raio * 2 + 18, topo + raio - 16), (modulo or "meme").upper(),
           font=f_mono, fill=cor_mod)
    f_peq = _fonte(FONTE_REG, 22)
    txt_dir = "ENCAMINHADA →"
    d.text((cx1 - f_peq.getlength(txt_dir), topo + raio - 14), txt_dir,
           font=f_peq, fill=COR_FRACA)

    # ── Bolha estilo WhatsApp (centralizada verticalmente no card)
    bolha_pad = 44
    bx0, bx1 = cx0, cx1
    largura_texto = (bx1 - bx0) - bolha_pad * 2

    f_meta = _fonte(FONTE_REG, 26)
    f_texto = _fonte(FONTE_BOLD, 56)
    linhas = _quebrar(texto.strip(), f_texto, largura_texto)
    altura_linha = 76

    cabecalho_h = 48
    corpo_h = len(linhas) * altura_linha
    rodape_h = 44
    bolha_h = bolha_pad + cabecalho_h + 24 + corpo_h + 24 + rodape_h + bolha_pad

    area_top = topo + raio * 2 + 40        # logo abaixo da barra do módulo
    area_bottom = ALTURA - margem - 110    # logo acima do rodapé de jogo
    bolha_top = area_top + max(0, ((area_bottom - area_top) - bolha_h) // 2)
    bolha_bottom = bolha_top + bolha_h

    d.rounded_rectangle(
        [bx0, bolha_top, bx1, bolha_bottom],
        radius=36, fill=COR_BOLHA, outline=COR_BOLHA_BORDA, width=2,
    )

    iy = bolha_top + bolha_pad
    # avatar (círculo cinza, sem emoji pra render confiável)
    d.ellipse([bx0 + bolha_pad, iy, bx0 + bolha_pad + 40, iy + 40], fill=(44, 57, 66))
    d.text((bx0 + bolha_pad + 56, iy + 6), "recebida no grupo", font=f_meta, fill=COR_SECUNDARIA)

    ty = iy + cabecalho_h + 24
    for linha in linhas:
        d.text((bx0 + bolha_pad, ty), linha, font=f_texto, fill=COR_TEXTO)
        ty += altura_linha

    rodape = "encaminhada muitas vezes →"
    d.text((bx1 - bolha_pad - f_meta.getlength(rodape), bolha_bottom - bolha_pad - 18),
           rodape, font=f_meta, fill=COR_SECUNDARIA)

    # ── Rodapé do card: dica de jogo
    f_dica = _fonte(FONTE_BOLD, 30)
    disc, conc = "◀ DISCORDO", "CONCORDO ▶"
    base = ALTURA - margem - 70
    d.text((cx0, base), disc, font=f_dica, fill=(232, 64, 64))
    d.text((cx1 - f_dica.getlength(conc), base), conc, font=f_dica, fill=(45, 212, 160))

    img.save(dest, "PNG")
    logger.info("Imagem de meme gerada: %s", dest)
    return dest


def gerar_meme_video(
    meme_id: str,
    texto: str = "",
    modulo: str = "",
    *,
    duracao: float = 5.0,
    overwrite: bool = True,
    imagem: Path | None = None,
    dest_dir: Path | None = None,
) -> Path:
    """Anima a imagem do meme com zoom suave (Ken Burns) e salva MP4."""
    destino_dir = dest_dir or VIDEOS_DIR
    destino_dir.mkdir(parents=True, exist_ok=True)
    dest = destino_dir / f"{meme_id}.mp4"
    if dest.exists() and not overwrite:
        return dest

    # Garante a imagem-base.
    img = imagem or imagem_path_for(meme_id)
    if img is None:
        if not texto:
            raise ValueError("sem imagem nem texto pra gerar o vídeo do meme")
        img = gerar_meme_imagem(meme_id, texto, modulo, overwrite=overwrite)

    frames = max(1, int(duracao * 30))
    # Pré-escala 2x e zoompan pra um zoom limpo sem tremer.
    vf = (
        f"scale={LARGURA*2}:{ALTURA*2},"
        f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={LARGURA}x{ALTURA}:fps=30,format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(img),
        "-t", f"{duracao}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao gerar vídeo do meme: {proc.stderr[-400:]}")
    logger.info("Vídeo de meme gerado: %s", dest)
    return dest


def delete_imagem(meme_id: str) -> bool:
    p = IMAGENS_DIR / f"{meme_id}.png"
    if p.exists():
        p.unlink()
        return True
    return False


def delete_video(meme_id: str) -> bool:
    p = VIDEOS_DIR / f"{meme_id}.mp4"
    if p.exists():
        p.unlink()
        return True
    return False


def list_imagens() -> dict[str, Path]:
    if not IMAGENS_DIR.exists():
        return {}
    return {p.stem: p for p in sorted(IMAGENS_DIR.glob("*.png"))}


def list_videos() -> dict[str, Path]:
    if not VIDEOS_DIR.exists():
        return {}
    return {p.stem: p for p in sorted(VIDEOS_DIR.glob("*.mp4"))}
