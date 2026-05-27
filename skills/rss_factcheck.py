"""
RSS Fact-Checkers — skill para buscar memes políticos verificados.
Fontes: Agência Lupa, Aos Fatos, Boatos.org, E-Farsas

Aplica filtro heurístico em 2 etapas:
  1. Filtro lexical: padrões de meme (imperativo, absoluto, aspas)
  2. Gate político: vocabulário controlado de política/cidadania

Retorna lista de MemeCandidate com score de relevância.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser

logger = logging.getLogger(__name__)

# ── Vocabulário de classificação ───────────────────────────────────────────────

GATILHOS_MEME = [
    # Imperativos compartilháveis
    r"\bcompartilha\b", r"\bpassa pra frente\b", r"\bsalva\b", r"\breposta\b",
    r"\bviral\b", r"\bcircula\b",
    # Absolutismo / afirmação forte
    r"\btodos?\s+\w+\s+são\b", r"\bnunca\b", r"\bsempre\b", r"\bcomprovad[oa]\b",
    r"\bgarantid[oa]\b", r"\bé\s+falso\b", r"\bé\s+mentira\b", r"\bé\s+verdade\b",
    r"\bprova que\b", r"\bprove que\b",
    # Apelo emocional / urgência
    r"\babsurdo\b", r"\bescandal\b", r"\burgente\b", r"\balerta\b", r"\batenção\b",
    # Aspas de discurso atribuído (frase em aspas com 5+ palavras)
    r'["""][^"""]{20,}["""]',
    # Padrões de verificação/debunking
    r"\bé\s+(falso|enganoso|verdadeiro|misleading)\b",
    r"\bfake\s+news\b",
    r"\bdesinformação\b",
    r"\bchecagem\b",
]

VOCABULARIO_POLITICO = [
    "eleição", "eleições", "vereador", "vereadores", "prefeito", "governador",
    "governo", "imposto", "impostos", "votação", "votar", "voto", "urna",
    "câmara", "senado", "congresso", "parlamento", "deputado", "ministro",
    "bolsa família", "benefício", "sus", "saúde pública", "escola pública",
    "transporte", "ônibus", "orçamento", "reforma", "partido", "candidato",
    "democracia", "constituição", "política", "político", "políticos",
    "participação popular", "audiência pública", "conselho tutelar",
    "fake news", "desinformação", "checagem", "fato ou fake",
    "milícia", "corrupção", "transparência", "licitação",
]

# Status de verificação normalizados
STATUS_MAP = {
    "falso": "falso",
    "false": "falso",
    "mentira": "falso",
    "fake": "falso",
    "enganoso": "enganoso",
    "misleading": "enganoso",
    "exagerado": "enganoso",
    "distorcido": "enganoso",
    "contexto": "contexto_ausente",
    "incompleto": "contexto_ausente",
    "verdadeiro": "verdadeiro",
    "true": "verdadeiro",
    "correto": "verdadeiro",
}

RE_GATILHOS = [re.compile(p, re.IGNORECASE) for p in GATILHOS_MEME]


@dataclass
class MemeCandidate:
    meme_texto: str
    source_url: str
    agencia: str
    titulo_original: str
    resumo: str = ""
    status_verificacao: str = ""
    explicacao: str = ""
    data_publicacao: str = ""
    score: float = 0.0
    tags_detectadas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "meme_texto": self.meme_texto,
            "source_url": self.source_url,
            "source_rss": self.agencia,
            "agencia": self.agencia,
            "titulo_original": self.titulo_original,
            "resumo": self.resumo,
            "status_verificacao": self.status_verificacao,
            "explicacao": self.explicacao,
            "data_publicacao": self.data_publicacao,
            "score": self.score,
            "tags": self.tags_detectadas,
        }


class RSSFactCheckSkill:
    def __init__(
        self,
        sources: list[dict] | None = None,
        lookback_hours: int = 72,
        min_score: float = 0.4,
        timeout: int = 20,
    ) -> None:
        self.sources = sources or [
            {"nome": "Agência Lupa", "url": "https://piaui.folha.uol.com.br/lupa/feed/", "agencia": "lupa"},
            {"nome": "Aos Fatos", "url": "https://aosfatos.org/feed/", "agencia": "aosfatos"},
            {"nome": "Boatos.org", "url": "https://www.boatos.org/feed", "agencia": "boatos"},
            {"nome": "E-Farsas", "url": "https://www.e-farsas.com/feed", "agencia": "efarsas"},
        ]
        self.lookback_hours = lookback_hours
        self.min_score = min_score
        self.timeout = timeout

    def fetch_all(self) -> list[MemeCandidate]:
        """Busca todos os RSS e retorna candidatos deduplicados."""
        all_candidates: list[MemeCandidate] = []
        seen_hashes: set[str] = set()

        for source in self.sources:
            try:
                candidates = self._fetch_source(source)
                for c in candidates:
                    h = _hash_text(c.meme_texto)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        all_candidates.append(c)
            except Exception as exc:
                logger.warning("RSS %s falhou: %s", source["agencia"], exc)

        return sorted(all_candidates, key=lambda c: c.score, reverse=True)

    def _fetch_source(self, source: dict) -> list[MemeCandidate]:
        feed = feedparser.parse(source["url"])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        candidates = []

        for entry in feed.entries:
            # Filtro temporal
            pub_date = _parse_date(entry)
            if pub_date and pub_date < cutoff:
                continue

            titulo = getattr(entry, "title", "")
            resumo = getattr(entry, "summary", "")
            link = getattr(entry, "link", "")
            texto_completo = f"{titulo} {resumo}"

            score, status = self._classify(texto_completo, source["agencia"])
            if score < self.min_score:
                continue

            meme_texto = self._extrair_meme(titulo, resumo)
            if not meme_texto or len(meme_texto) < 15:
                continue

            tags = self._extrair_tags(texto_completo)

            candidates.append(
                MemeCandidate(
                    meme_texto=meme_texto,
                    source_url=link,
                    agencia=source["agencia"],
                    titulo_original=titulo,
                    resumo=resumo[:500],
                    status_verificacao=status,
                    explicacao=self._extrair_explicacao(resumo),
                    data_publicacao=pub_date.isoformat() if pub_date else "",
                    score=score,
                    tags_detectadas=tags,
                )
            )

        return candidates

    def fetch_from_xml(self, xml_content: str, agencia: str = "lupa") -> list[MemeCandidate]:
        """Parseia XML diretamente — usado em testes com fixtures."""
        feed = feedparser.parse(xml_content)
        source = {"agencia": agencia, "url": ""}
        candidates = []

        for entry in feed.entries:
            titulo = getattr(entry, "title", "")
            resumo = getattr(entry, "summary", "")
            link = getattr(entry, "link", "")
            texto = f"{titulo} {resumo}"

            score, status = self._classify(texto, agencia)
            if score < self.min_score:
                continue

            meme_texto = self._extrair_meme(titulo, resumo)
            if not meme_texto or len(meme_texto) < 15:
                continue

            candidates.append(
                MemeCandidate(
                    meme_texto=meme_texto,
                    source_url=link,
                    agencia=agencia,
                    titulo_original=titulo,
                    resumo=resumo[:500],
                    status_verificacao=status,
                    explicacao=self._extrair_explicacao(resumo),
                    score=score,
                    tags_detectadas=self._extrair_tags(texto),
                )
            )
        return candidates

    def _classify(self, texto: str, agencia: str) -> tuple[float, str]:
        """Retorna (score, status_verificacao)."""
        score = 0.0

        # Gate 1: padrões de meme
        gatilhos_encontrados = sum(1 for r in RE_GATILHOS if r.search(texto))
        if gatilhos_encontrados == 0:
            return 0.0, ""
        score += min(gatilhos_encontrados * 0.15, 0.45)

        # Gate 2: vocabulário político
        texto_lower = texto.lower()
        politico_encontrado = sum(1 for p in VOCABULARIO_POLITICO if p in texto_lower)
        if politico_encontrado == 0:
            return 0.0, ""
        score += min(politico_encontrado * 0.1, 0.3)

        # Bonus: veio de fact-checker (já é verificado)
        if agencia in ("lupa", "aosfatos", "boatos", "efarsas"):
            score += 0.25

        # Detecta status de verificação
        status = self._detectar_status(texto)

        return min(score, 1.0), status

    def _detectar_status(self, texto: str) -> str:
        texto_lower = texto.lower()
        for termo, status in STATUS_MAP.items():
            if termo in texto_lower:
                return status
        return "enganoso"  # default conservador para fact-checkers

    def _extrair_meme(self, titulo: str, resumo: str) -> str:
        """Extrai o texto do meme a partir do título do fact-check."""
        # Padrão: "É FALSO/ENGANOSO que 'texto do meme'"
        patterns = [
            r'(?:é\s+(?:falso|enganoso|verdadeiro|mentira)\s+que\s+)["\"]?(.{10,150})["\"]?',
            r'["""]([^"""]{15,200})["""]',
            r'"([^"]{15,200})"',
        ]
        for pat in patterns:
            m = re.search(pat, titulo, re.IGNORECASE)
            if m:
                return m.group(1).strip().strip('"').strip("'")

        # Fallback: remove prefixos de fact-check do título
        titulo_limpo = re.sub(
            r'^(é\s+)?(falso|enganoso|verdadeiro|mentira|fake|checagem)[:\s—–-]+',
            '',
            titulo,
            flags=re.IGNORECASE,
        ).strip()
        return titulo_limpo if len(titulo_limpo) >= 15 else ""

    def _extrair_explicacao(self, resumo: str) -> str:
        """Extrai a explicação do fact-check do resumo."""
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", resumo)
        # Limita a 300 chars
        return clean[:300].strip()

    def _extrair_tags(self, texto: str) -> list[str]:
        texto_lower = texto.lower()
        return [p for p in VOCABULARIO_POLITICO if p in texto_lower][:8]

    def is_meme_politico(self, texto: str) -> tuple[bool, float]:
        """Interface pública para classificar um texto — threshold mais permissivo."""
        score, _ = self._classify(texto, "manual")
        return score >= 0.3, score  # threshold menor: classificação, não curadoria


def _hash_text(texto: str) -> str:
    import hashlib
    return hashlib.md5(texto.strip().lower().encode()).hexdigest()


def _parse_date(entry) -> datetime | None:
    published = getattr(entry, "published_parsed", None)
    if published:
        try:
            return datetime(*published[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return None
