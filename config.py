"""
Configuração central do OzielMemes Pipeline.
Carrega do ambiente ou de um arquivo .env na raiz do projeto.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent

# Tenta carregar .env se existir (desenvolvimento local)
_env_file = ROOT / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Tenta carregar secrets do Streamlit Cloud (produção)
try:
    import streamlit as st
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass


@dataclass
class Config:
    # ── Gemini API (tier gratuito) ────────────────────────────────────────────
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    gemini_model: str = "gemini-flash-latest"
    claude_model: str = "gemini-flash-latest"  # alias mantido para compat interna

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))
    db_path: str = str(ROOT / "database" / "oziel_pipeline.db")
    memes_json_path: str = str(ROOT / "database" / "memes.json")

    # ── Cache de dados abertos ────────────────────────────────────────────────
    data_cache_dir: str = str(ROOT / "data")
    cache_ttl_hours: int = 24

    # ── Output ───────────────────────────────────────────────────────────────
    output_dir: str = str(ROOT / "output")

    # ── IBGE ─────────────────────────────────────────────────────────────────
    ibge_campinas_code: str = "3509502"
    ibge_base_url: str = "https://servicodados.ibge.gov.br/api/v3"

    # ── TSE ──────────────────────────────────────────────────────────────────
    tse_base_url: str = "https://dadosabertos.tse.jus.br"
    tse_campinas_code: str = "70190"  # código municipal TSE

    # ── SEADE ─────────────────────────────────────────────────────────────────
    seade_base_url: str = "https://repositorio.seade.gov.br/api/action"

    # ── SSP-SP ────────────────────────────────────────────────────────────────
    ssp_base_url: str = "https://www.ssp.sp.gov.br/estatistica"

    # ── Portal Transparência ──────────────────────────────────────────────────
    transparencia_base_url: str = "https://portaldatransparencia.gov.br/api-de-dados"
    transparencia_api_key: str = field(
        default_factory=lambda: os.environ.get("TRANSPARENCIA_API_KEY", "")
    )

    # ── RSS Sources ───────────────────────────────────────────────────────────
    rss_sources: list[dict] = field(default_factory=list)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    max_items_per_run: int = 10
    max_tentativas_por_item: int = 3
    request_timeout_seconds: int = 30
    rss_lookback_hours: int = 72
    claude_sleep_between_calls: float = 1.0  # evita rate limit

    # ── Classificação de meme ─────────────────────────────────────────────────
    meme_score_min: float = 0.4

    # ── Mapeamento tag → skills ───────────────────────────────────────────────
    tag_to_skills: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY não definida.\n"
                "Obtenha em: https://aistudio.google.com/app/apikey (gratuito)\n"
                "Execute: export GEMINI_API_KEY='AIza...'\n"
                "Ou crie um arquivo .env na raiz do projeto com:\n"
                "  GEMINI_API_KEY=AIza..."
            )

        if not self.rss_sources:
            self.rss_sources = [
                {
                    "nome": "Agência Lupa",
                    "url": "https://piaui.folha.uol.com.br/lupa/feed/",
                    "agencia": "lupa",
                },
                {
                    "nome": "Aos Fatos",
                    "url": "https://aosfatos.org/feed/",
                    "agencia": "aosfatos",
                },
                {
                    "nome": "Boatos.org",
                    "url": "https://www.boatos.org/feed",
                    "agencia": "boatos",
                },
                {
                    "nome": "E-Farsas",
                    "url": "https://www.e-farsas.com/feed",
                    "agencia": "efarsas",
                },
                {
                    "nome": "G1 Fato ou Fake",
                    "url": "https://g1.globo.com/rss/g1/fato-ou-fake/",
                    "agencia": "g1",
                },
                {
                    "nome": "Projeto Comprova",
                    "url": "https://projetocomprova.com.br/feed/",
                    "agencia": "comprova",
                },
                {
                    "nome": "Estadão Verifica",
                    "url": "https://www.estadao.com.br/arc/outboundfeeds/feeds/rss/sections/estadao-verifica/?outputType=xml",
                    "agencia": "estadao",
                },
                {
                    "nome": "Agência Pública (Truco)",
                    "url": "https://apublica.org/tag/truco/feed/",
                    "agencia": "publica",
                },
            ]

        if not self.tag_to_skills:
            self.tag_to_skills = {
                "eleicao": ["tse_data", "ibge_demografico"],
                "eleição": ["tse_data", "ibge_demografico"],
                "voto": ["tse_data"],
                "vereador": ["tse_data", "camara_campinas"],
                "câmara": ["tse_data", "camara_campinas"],
                "camara": ["tse_data", "camara_campinas"],
                "saúde": ["ibge_demografico", "datasus"],
                "sus": ["ibge_demografico"],
                "vacina": ["datasus"],
                "violencia": ["ssp_violencia"],
                "violência": ["ssp_violencia"],
                "seguranca": ["ssp_violencia"],
                "educacao": ["ibge_educacao", "seade"],
                "educação": ["ibge_educacao", "seade"],
                "escola": ["ibge_educacao"],
                "transporte": ["ibge_demografico"],
                "onibus": ["ibge_demografico"],
                "ônibus": ["ibge_demografico"],
                "imposto": ["transparencia_federal"],
                "orçamento": ["transparencia_federal"],
                "orcamento": ["transparencia_federal"],
                "bolsa família": ["transparencia_federal", "ibge_demografico"],
                "bolsa familia": ["transparencia_federal", "ibge_demografico"],
                "habitacao": ["ibge_demografico", "seade"],
                "habitação": ["ibge_demografico", "seade"],
                "renda": ["ibge_demografico"],
                "desemprego": ["ibge_demografico", "seade"],
                "participacao": ["tse_data", "camara_campinas"],
                "participação": ["tse_data", "camara_campinas"],
                "terra": ["ibge_demografico"],
                "reforma agrária": ["ibge_demografico"],
                # Âncora local — demandas reais do bairro na Câmara de Campinas
                "territorio": ["camara_campinas"],
                "território": ["camara_campinas"],
                "oziel": ["camara_campinas"],
                "bairro": ["camara_campinas"],
                "promessa": ["camara_campinas"],
                "campinas": ["camara_campinas"],
            }


# Singleton para uso direto nos módulos (lazy-load com env)
_config_instance: Config | None = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
