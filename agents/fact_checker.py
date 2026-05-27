"""
FactCheckAgent — extrai status de verificação de conteúdo HTML/texto.
Usa Claude API APENAS para normalizar/extrair status de HTML bruto.
Não gera conteúdo editorial — apenas estrutura o que já foi verificado.
"""
from __future__ import annotations

import logging
import re

from agents.base_agent import BaseAgent
from skills.rss_factcheck import MemeCandidate, STATUS_MAP

logger = logging.getLogger(__name__)

SYSTEM_FACT_CHECK = """Você extrai informações de fact-check de textos de agências de verificação.
Responda SOMENTE com um JSON no formato:
{"status": "falso|enganoso|contexto_ausente|verdadeiro", "fonte": "nome da agência", "explicacao": "resumo em 1 frase"}

Não invente informações. Extraia apenas o que está explicitamente no texto."""


class FactCheckAgent(BaseAgent):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-flash",
        use_claude: bool = True,
        client=None,  # compat com testes antigos
    ) -> None:
        super().__init__(name="fact_checker", api_key=api_key, model=model, client=client)
        self.use_claude = use_claude

    def run(self, candidate: MemeCandidate) -> dict:
        """
        Verifica e estrutura o resultado de fact-check de um candidato.
        Se o candidato já veio de RSS de fact-checker, extrai diretamente.
        Se não, tenta extrair via Claude do texto disponível.
        Retorna dict com status, fonte, fonte_url, explicacao, agencia.
        """
        # Candidatos vindos de agências confiáveis: extrai diretamente
        if candidate.agencia in ("lupa", "aosfatos", "boatos", "efarsas"):
            result = self._extrair_de_rss(candidate)
            if result["status"]:
                return result

        # Fallback: usa Claude para extrair do resumo
        if self.use_claude and self.client and candidate.resumo:
            return self._extrair_via_claude(candidate)

        # Sem Claude disponível: retorna o que temos
        return self._extrair_de_rss(candidate)

    def _extrair_de_rss(self, candidate: MemeCandidate) -> dict:
        """Extrai status diretamente dos metadados do RSS."""
        status = candidate.status_verificacao
        # Normaliza status
        if not status:
            status = _detectar_status_heuristico(
                f"{candidate.titulo_original} {candidate.resumo}"
            )

        return {
            "status": status or "enganoso",
            "fonte": _nome_agencia(candidate.agencia),
            "fonte_url": candidate.source_url,
            "explicacao": candidate.explicacao or candidate.resumo[:200],
            "agencia": candidate.agencia,
            "data_verificacao": candidate.data_publicacao,
        }

    def _extrair_via_claude(self, candidate: MemeCandidate) -> dict:
        """Usa Claude (haiku) para extrair status estruturado do resumo."""
        prompt = f"""Texto do fact-check:
Título: {candidate.titulo_original}
Resumo: {candidate.resumo}

Extrai o resultado de verificação desse texto."""

        try:
            resposta = self._call_claude(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM_FACT_CHECK,
                max_tokens=200,
            )
            import json
            data = json.loads(resposta.strip())
            return {
                "status": data.get("status", "enganoso"),
                "fonte": data.get("fonte") or _nome_agencia(candidate.agencia),
                "fonte_url": candidate.source_url,
                "explicacao": data.get("explicacao", ""),
                "agencia": candidate.agencia,
                "data_verificacao": candidate.data_publicacao,
            }
        except Exception as exc:
            self.log(f"Claude fact-check falhou: {exc}", "WARNING")
            return self._extrair_de_rss(candidate)

    def verificar_texto(self, texto: str) -> dict:
        """Interface para verificar um texto arbitrário sem candidate."""
        status = _detectar_status_heuristico(texto)
        return {
            "status": status or "enganoso",
            "fonte": "verificação heurística",
            "fonte_url": "",
            "explicacao": "Classificado automaticamente por heurística",
            "agencia": "auto",
        }


def _detectar_status_heuristico(texto: str) -> str:
    texto_lower = texto.lower()
    for termo, status in STATUS_MAP.items():
        if termo in texto_lower:
            return status
    return ""


def _nome_agencia(agencia_id: str) -> str:
    nomes = {
        "lupa": "Agência Lupa",
        "aosfatos": "Aos Fatos",
        "boatos": "Boatos.org",
        "efarsas": "E-Farsas",
    }
    return nomes.get(agencia_id, agencia_id)
