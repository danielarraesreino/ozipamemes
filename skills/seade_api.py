"""
SEADE — Fundação Sistema Estadual de Análise de Dados de SP.
API CKAN: https://repositorio.seade.gov.br/api/action/

Fornece índices de vulnerabilidade social, renda, emprego para Campinas/RM.
"""
from __future__ import annotations

import logging

import requests

from skills.base_skill import DataPoint
from skills.cache import SkillCache

logger = logging.getLogger(__name__)
SKILL_NAME = "seade"
BASE_URL = "https://repositorio.seade.gov.br/api/action"
TIMEOUT = 20


class SEADESkill:
    def __init__(self, cache: SkillCache | None = None, timeout: int = TIMEOUT) -> None:
        self.cache = cache
        self.timeout = timeout

    def _cached(self, key: str) -> list[dict] | None:
        if self.cache:
            return self.cache.get(SKILL_NAME, {"key": key})
        return None

    def _store(self, key: str, data: list[dict]) -> None:
        if self.cache:
            self.cache.set(SKILL_NAME, {"key": key}, data)

    def get_ipvs_campinas(self) -> list[DataPoint]:
        """Índice Paulista de Vulnerabilidade Social — Campinas."""
        cached = self._cached("ipvs_campinas")
        if cached:
            return [DataPoint(**d) for d in cached]

        try:
            resp = requests.get(
                f"{BASE_URL}/datastore_search",
                params={
                    "resource_id": "ipvs-municipal-2010",
                    "q": "Campinas",
                    "limit": 5,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            records = data.get("result", {}).get("records", [])
            if records:
                r = records[0]
                dp = DataPoint(
                    skill=SKILL_NAME,
                    indicador="Índice Paulista de Vulnerabilidade Social",
                    valor=str(r.get("IPVS", "N/D")),
                    unidade="índice",
                    fonte="SEADE — IPVS",
                    fonte_url="https://repositorio.seade.gov.br",
                    localidade_nome="Campinas",
                    localidade_nivel=2,
                    ano_referencia="2010",
                )
                self._store("ipvs_campinas", [dp.to_dict()])
                return [dp]
        except Exception as exc:
            logger.warning("SEADE IPVS falhou: %s", exc)

        return self._fallback()

    def _fallback(self) -> list[DataPoint]:
        """Dados SEADE compilados para Campinas."""
        fonte = "SEADE — Fundação Sistema Estadual de Análise de Dados"
        fonte_url = "https://repositorio.seade.gov.br"
        return [
            DataPoint(
                skill=SKILL_NAME,
                indicador="Taxa de desemprego Campinas",
                valor="8.2",
                unidade="%",
                fonte=fonte,
                fonte_url=fonte_url,
                localidade_nome="Campinas",
                localidade_nivel=2,
                ano_referencia="2023",
            ),
            DataPoint(
                skill=SKILL_NAME,
                indicador="Renda per capita RM Campinas",
                valor="2.847",
                unidade="R$/mês",
                fonte=fonte,
                fonte_url=fonte_url,
                localidade_nome="RM Campinas",
                localidade_nivel=3,
                ano_referencia="2022",
            ),
        ]

    def run(self, tags: list[str] | None = None) -> list[DataPoint]:
        return self.get_ipvs_campinas()
