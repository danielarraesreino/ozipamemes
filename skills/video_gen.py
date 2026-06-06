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
import subprocess
import tempfile
import time
import wave
from pathlib import Path

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


def gerar_video(
    meme_id: str,
    texto: str,
    *,
    api_key: str | None = None,
    voz: str = VOZ_PADRAO,
    imagem: Path | None = None,
    overwrite: bool = True,
) -> Path:
    """
    Gera o vídeo da pílula para um meme e salva em database/videos/{meme_id}.mp4.

    texto    : o texto da pílula a narrar (já aprovado — preserva o R8).
    api_key  : GEMINI_API_KEY; se None, puxa de get_config().
    imagem   : fundo; se None, usa a imagem do meme (image_fetcher) ou fundo sólido.
    overwrite: se False e já existe vídeo, levanta erro em vez de sobrescrever.

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

    with tempfile.TemporaryDirectory() as tmp:
        wav = _pcm_para_wav(pcm, Path(tmp) / "fala.wav")
        # Remove vídeo anterior de qualquer extensão antes de gravar o novo.
        _delete_video(meme_id)
        _montar_video(wav, dest, imagem)

    logger.info(f"gerar_video[{meme_id}]: pronto → {dest} ({dest.stat().st_size // 1024}KB)")
    return dest
