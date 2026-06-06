"""
video_gen — gera o vídeo da pílula com IA (narração + visual).

Pega o texto editorial JÁ APROVADO da pílula (pilula_sabedoria / pilula_alt1 /
pilula_alt2), sintetiza a narração com o TTS do Gemini (mesma GEMINI_API_KEY do
pipeline) e compõe com a imagem do meme num MP4 vertical 1080x1920 via ffmpeg.

Por que TTS e não Veo (texto→clipe mudo): a pílula é orientação prática falada
pra molecada de 12–17 (educação midiática, sem ranço). As palavras são as
aprovadas, palavra por palavra — o R8 (anti-alucinação) continua valendo, porque
a IA narra o texto exato, não improvisa conteúdo.

A saída segue a convenção do banco de vídeos (database/videos/{meme_id}.mp4),
então a galeria e o export pro jogo (web_url_for) pegam de graça.

Fronteira de rede: só `_sintetizar_fala` fala com a API. O resto (wav + ffmpeg)
é local — daí os testes monkeypatcham essa função e exercitam o ffmpeg de verdade.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import requests
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from skills.video_fetcher import VIDEOS_DIR, delete as _delete_video

logger = logging.getLogger(__name__)

# Modelo de TTS do Gemini (preview). Override por argumento se mudar de nome.
MODELO_TTS = "gemini-2.5-flash-preview-tts"

# Voz prebuilt padrão. "Kore" é firme/clara; o TTS é multilíngue e fala PT-BR bem.
VOZ_PADRAO = "Kore"

# PCM que o TTS devolve: 24kHz, mono, 16-bit signed LE.
TTS_SAMPLE_RATE = 24000
TTS_CANAIS = 1
TTS_BYTES_POR_AMOSTRA = 2

# Cor de fundo da campanha (azul-noite), usada na borda/letterbox e no fallback.
COR_FUNDO = "0x0E1B2A"

# Direção de locução: tom jovem e direto, sem pregar. Vai como prefixo de estilo
# no prompt do TTS (o Gemini entende instruções de estilo antes do texto).
ESTILO_LOCUCAO = (
    "Leia em português do Brasil, com voz jovem, próxima e direta, como quem "
    "explica pra um amigo de 15 anos — sem tom professoral, sem pregação:\n\n"
)


def _sintetizar_fala(
    texto: str, api_key: str, voz: str = VOZ_PADRAO, retries: int = 3
) -> bytes:
    """
    Chama o TTS do Gemini e devolve o áudio PCM cru (24kHz/mono/16-bit).

    Tem retry com backoff porque o TTS divide a cota do free tier (5 req/min) com
    o pipeline — sem isso, gerar vídeos em sequência estouraria 429 e falharia seco.
    """
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voz)
            )
        ),
    )
    last_exc: Exception | None = None
    for tentativa in range(retries):
        try:
            resp = client.models.generate_content(
                model=MODELO_TTS, contents=ESTILO_LOCUCAO + texto, config=config,
            )
            return resp.candidates[0].content.parts[0].inline_data.data
        except google_exceptions.ResourceExhausted as exc:
            # Free tier: 5 req/min. Espera crescente antes de tentar de novo.
            espera = min(15 * (tentativa + 1), 45)
            logger.warning(f"TTS rate limit (429) — aguardando {espera}s e tentando de novo…")
            time.sleep(espera)
            last_exc = exc
    raise RuntimeError(
        f"TTS do Gemini falhou após {retries} tentativas (rate limit do free tier?): {last_exc}"
    )


def _pcm_para_wav(pcm: bytes, dest: Path) -> Path:
    """Embrulha o PCM cru num container WAV pro ffmpeg ler."""
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(TTS_CANAIS)
        w.setsampwidth(TTS_BYTES_POR_AMOSTRA)
        w.setframerate(TTS_SAMPLE_RATE)
        w.writeframes(pcm)
    return dest


def _montar_video(wav: Path, dest: Path, imagem: Path | None) -> Path:
    """
    Compõe o MP4 vertical 1080x1920 com ffmpeg.
    Com imagem: fundo desfocado preenchendo a tela + imagem nítida centralizada.
    Sem imagem: fundo sólido da campanha. Em ambos a duração segue o áudio.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if imagem and imagem.exists():
        filtro = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=24[bg];"
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(imagem),
            "-i", str(wav),
            "-filter_complex", filtro,
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            str(dest),
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c={COR_FUNDO}:s=1080x1920",
            "-i", str(wav),
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest",
            str(dest),
        ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(f"ffmpeg falhou ({proc.returncode}): {proc.stderr[-800:]}")
    return dest


# ── B-roll (estilo "trazer vídeos", inspirado no MoneyPrinterTurbo) ──────────
# Em vez da imagem estática do meme, busca clipes de banco no Pexels combinando
# com a pílula, costura sob a narração e queima legendas. Mantém o R8: a fala é o
# texto aprovado; o vídeo de fundo é só ambientação. Sem chave/rede → cai pro modo
# imagem (ethos offline preservado).

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Query de reserva quando a pílula não rende boas palavras-chave (tema da campanha).
QUERY_FALLBACK = "young people city brazil"

# Stopwords PT pra extrair palavras-chave sem LLM (offline, barato).
_STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "que", "em", "um", "uma", "para", "pra", "com",
    "no", "na", "os", "as", "se", "por", "mais", "como", "mas", "ao", "dos", "das",
    "seu", "sua", "ou", "quando", "muito", "já", "também", "só", "pelo", "pela",
    "até", "isso", "ela", "ele", "você", "voce", "ser", "tem", "foi", "são", "sao",
    "não", "nao", "sim", "vai", "está", "esta", "isto", "essa", "esse", "aqui",
}


def _pexels_key(api_key: str | None = None) -> str:
    return api_key or os.environ.get("PEXELS_API_KEY", "")


def _extrair_palavras_chave(texto: str, n: int = 4) -> list[str]:
    """Top-n palavras de conteúdo da pílula (sem stopwords), por frequência."""
    palavras = re.findall(r"[a-zà-ÿ]{4,}", texto.lower())
    freq: dict[str, int] = {}
    for p in palavras:
        if p in _STOPWORDS:
            continue
        freq[p] = freq.get(p, 0) + 1
    ordenadas = sorted(freq, key=lambda p: (-freq[p], -len(p)))
    return ordenadas[:n]


def _duracao_wav(wav: Path) -> float:
    with wave.open(str(wav), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _pexels_buscar_clipes(query: str, api_key: str, n: int, locale: str = "pt-BR") -> list[str]:
    """Busca vídeos verticais no Pexels e devolve URLs .mp4 (até n)."""
    resp = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "portrait", "per_page": n, "locale": locale},
        timeout=20,
    )
    resp.raise_for_status()
    urls: list[str] = []
    for video in resp.json().get("videos", []):
        # Pega o melhor arquivo vertical ≤1080 de largura (evita 4K gigante).
        arquivos = sorted(
            (f for f in video.get("video_files", []) if f.get("link")),
            key=lambda f: (f.get("width") or 0),
            reverse=True,
        )
        escolhido = next((f for f in arquivos if (f.get("width") or 0) <= 1080), None) or (
            arquivos[-1] if arquivos else None
        )
        if escolhido:
            urls.append(escolhido["link"])
    return urls


def _baixar(url: str, dest: Path) -> Path:
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    return dest


def _ts_srt(segundos: float) -> str:
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    ms = int((segundos - int(segundos)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _montar_srt(texto: str, duracao: float, dest: Path, max_palavras: int = 6) -> Path:
    """Quebra a pílula em legendas curtas, distribuídas proporcionalmente no tempo."""
    palavras = texto.split()
    blocos = [
        " ".join(palavras[i : i + max_palavras])
        for i in range(0, len(palavras), max_palavras)
    ] or [texto]
    total_chars = sum(len(b) for b in blocos) or 1
    linhas: list[str] = []
    t = 0.0
    for i, bloco in enumerate(blocos, 1):
        dur = duracao * (len(bloco) / total_chars)
        linhas.append(f"{i}\n{_ts_srt(t)} --> {_ts_srt(t + dur)}\n{bloco}\n")
        t += dur
    dest.write_text("\n".join(linhas), encoding="utf-8")
    return dest


def _normalizar_clipe(src: Path, dest: Path, seg_dur: float) -> Path:
    """Recorta o clipe pra 1080x1920, fps fixo e duração seg_dur (sem áudio)."""
    cmd = [
        "ffmpeg", "-y", "-i", str(src), "-t", f"{seg_dur:.2f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
               "crop=1080:1920,fps=30,format=yuv420p",
        "-an", "-c:v", "libx264", "-preset", "veryfast", str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(f"ffmpeg normalizar falhou: {proc.stderr[-400:]}")
    return dest


def _montar_broll(segs: list[Path], wav: Path, srt: Path, dest: Path) -> Path:
    """Concatena os clipes normalizados, queima legendas e casa com a narração."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Concat por demuxer (todos os segs têm os mesmos parâmetros → -c copy).
    lista = dest.parent / f"{dest.stem}_lista.txt"
    lista.write_text("".join(f"file '{s.resolve()}'\n" for s in segs), encoding="utf-8")
    visual = dest.parent / f"{dest.stem}_visual.mp4"
    cat = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
         "-c", "copy", str(visual)],
        capture_output=True, text=True,
    )
    if cat.returncode != 0 or not visual.exists():
        raise RuntimeError(f"ffmpeg concat falhou: {cat.stderr[-400:]}")

    estilo = "FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H99000000,BorderStyle=3,MarginV=120"
    mux = subprocess.run(
        ["ffmpeg", "-y", "-i", str(visual), "-i", str(wav),
         "-vf", f"subtitles={srt.as_posix()}:force_style='{estilo}'",
         "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
         "-pix_fmt", "yuv420p", "-shortest", str(dest)],
        capture_output=True, text=True,
    )
    lista.unlink(missing_ok=True)
    visual.unlink(missing_ok=True)
    if mux.returncode != 0 or not dest.exists():
        raise RuntimeError(f"ffmpeg mux/legenda falhou: {mux.stderr[-400:]}")
    return dest


def _gerar_broll(
    texto: str, wav: Path, dest: Path, tmp: Path, api_key_pexels: str, locale: str = "pt-BR"
) -> Path:
    """Pipeline B-roll completo: keywords → Pexels → download → concat+legenda."""
    duracao = _duracao_wav(wav)
    chaves = _extrair_palavras_chave(texto)
    query = " ".join(chaves[:2]) if chaves else QUERY_FALLBACK
    logger.info(f"B-roll: buscando clipes no Pexels (query='{query}', {duracao:.1f}s)…")

    n_clipes = max(2, min(5, round(duracao / 4)))  # ~4s por clipe
    urls = _pexels_buscar_clipes(query, api_key_pexels, n_clipes, locale)
    if not urls:
        urls = _pexels_buscar_clipes(QUERY_FALLBACK, api_key_pexels, n_clipes, "en-US")
    if not urls:
        raise RuntimeError("Pexels não retornou clipes")

    # Cada clipe cobre uma fatia da narração (+ folga p/ o -shortest cortar no áudio).
    seg_dur = duracao / len(urls) + 0.5
    segs: list[Path] = []
    for i, url in enumerate(urls):
        bruto = _baixar(url, tmp / f"clip_{i}.mp4")
        segs.append(_normalizar_clipe(bruto, tmp / f"seg_{i}.mp4", seg_dur))

    srt = _montar_srt(texto, duracao, tmp / "legenda.srt")
    return _montar_broll(segs, wav, srt, dest)


def gerar_video(
    meme_id: str,
    texto: str,
    *,
    api_key: str | None = None,
    voz: str = VOZ_PADRAO,
    imagem: Path | None = None,
    overwrite: bool = True,
    estilo: str = "imagem",
    pexels_key: str | None = None,
    locale: str = "pt-BR",
) -> Path:
    """
    Gera o vídeo da pílula para um meme e salva em database/videos/{meme_id}.mp4.

    texto    : o texto da pílula a narrar (já aprovado — preserva o R8).
    api_key  : GEMINI_API_KEY; se None, puxa de get_config().
    imagem   : fundo; se None, usa a imagem do meme (image_fetcher) ou fundo sólido.
    overwrite: se False e já existe vídeo, levanta erro em vez de sobrescrever.
    estilo   : "imagem" (narração sobre a imagem do meme) ou "broll" (clipes do
               Pexels + legendas, à la MoneyPrinterTurbo). Sem chave/rede o "broll"
               cai pro "imagem" automaticamente.
    pexels_key: chave da API do Pexels; se None, usa PEXELS_API_KEY do ambiente.

    Retorna o Path do MP4 gerado.
    """
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("gerar_video: texto da pílula vazio")

    if api_key is None:
        from config import get_config
        api_key = get_config().gemini_api_key
    if not api_key:
        raise RuntimeError("gerar_video requer GEMINI_API_KEY configurada")

    dest = VIDEOS_DIR / f"{meme_id}.mp4"
    if dest.exists() and not overwrite:
        raise FileExistsError(f"{meme_id} já tem vídeo (use overwrite=True)")

    if imagem is None:
        from skills.image_fetcher import image_path_for
        imagem = image_path_for(meme_id)

    logger.info(f"gerar_video[{meme_id}]: sintetizando narração ({len(texto)} chars)…")
    pcm = _sintetizar_fala(texto, api_key, voz)

    chave_pexels = _pexels_key(pexels_key)
    with tempfile.TemporaryDirectory() as tmp:
        wav = _pcm_para_wav(pcm, Path(tmp) / "fala.wav")
        # Remove vídeo anterior de qualquer extensão antes de gravar o novo.
        _delete_video(meme_id)
        if estilo == "broll" and chave_pexels:
            try:
                _gerar_broll(texto, wav, dest, Path(tmp), chave_pexels, locale)
            except Exception as e:
                # Sem rede / Pexels fora / ffmpeg → não falha: cai pro modo imagem.
                logger.warning(f"B-roll falhou ({e}); usando imagem do meme.")
                _montar_video(wav, dest, imagem)
        else:
            if estilo == "broll":
                logger.warning("estilo='broll' sem PEXELS_API_KEY; usando imagem do meme.")
            _montar_video(wav, dest, imagem)

    logger.info(f"gerar_video[{meme_id}]: pronto → {dest} ({dest.stat().st_size // 1024}KB)")
    return dest
