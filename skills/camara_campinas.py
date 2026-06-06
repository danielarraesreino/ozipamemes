"""
Câmara Municipal de Campinas — SAPL (Sistema de Apoio ao Processo Legislativo).
API aberta: https://sapl.campinas.sp.leg.br/api/

Puxa matérias legislativas (requerimentos, indicações, projetos de lei) que
mencionam o Parque/Jardim Oziel na ementa. É a matéria-prima de "prometeram/
pediram X pro bairro" — base para os memes e para a etapa de coautoria com os
jovens do território. Cada item é uma demanda real, com fonte rastreável (R8).
"""
from __future__ import annotations

import logging

import requests

from skills.base_skill import DataPoint
from skills.cache import SkillCache

logger = logging.getLogger(__name__)
SKILL_NAME = "camara_campinas"
BASE_URL = "https://sapl.campinas.sp.leg.br"
API_MATERIAS = f"{BASE_URL}/api/materia/materialegislativa/"
TIMEOUT = 25

# Termo de busca: pega "Parque Oziel", "Jardim Oziel", "EMEF Oziel" etc.
TERMO_BAIRRO = "Oziel"
LOCALIDADE = "Parque/Jardim Oziel"


class CamaraCampinasSkill:
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

    def get_demandas_oziel(self, limit: int = 8) -> list[DataPoint]:
        """Demandas registradas na Câmara que citam o Oziel na ementa."""
        cached = self._cached("demandas_oziel")
        if cached:
            return [DataPoint(**d) for d in cached]

        try:
            resp = requests.get(
                API_MATERIAS,
                params={
                    "ementa__icontains": TERMO_BAIRRO,
                    "ordering": "-ano",
                    "format": "json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            registros = data.get("results", []) or data.get("pagination", {}).get("results", [])
            dps: list[DataPoint] = []
            for item in registros[: limit * 3]:  # filtra depois, pega folga
                ementa = (item.get("ementa") or "").strip()
                if not ementa or TERMO_BAIRRO.lower() not in ementa.lower():
                    continue
                pk = item.get("id") or item.get("pk")
                ano = item.get("ano") or ""
                em_tram = item.get("em_tramitacao")
                status = "em tramitação" if em_tram else "encerrada/arquivada"
                dps.append(
                    DataPoint(
                        skill=SKILL_NAME,
                        indicador="Demanda na Câmara p/ o Oziel",
                        valor=f"{ementa[:220]} [{status}]",
                        unidade="",
                        fonte="Câmara Municipal de Campinas (SAPL)",
                        fonte_url=f"{BASE_URL}/materia/{pk}" if pk else BASE_URL,
                        localidade_nome=LOCALIDADE,
                        localidade_nivel=1,  # bairro — mais local possível
                        ano_referencia=str(ano),
                    )
                )
                if len(dps) >= limit:
                    break
            if dps:
                self._store("demandas_oziel", [d.to_dict() for d in dps])
                return dps
        except Exception as exc:
            logger.warning("Câmara Campinas SAPL falhou: %s", exc)

        return self._fallback()

    def _fallback(self) -> list[DataPoint]:
        """Demandas reais do Oziel já verificadas na API (uso offline)."""
        fonte = "Câmara Municipal de Campinas (SAPL)"
        exemplos = [
            "Solicita implantação de academia ao ar livre no Centro de Lazer do "
            "Parque Oziel, na Rua José Pereira Santos.",
            "Solicita substituição de poste de iluminação pública em frente à Praça "
            "João da Cruz Prates, no Parque Oziel/Jardim Monte Cristo.",
            "Solicita instalação de horta comunitária em parceria com a EMEF Oziel "
            "Alves Pereira, entre as Ruas Fauze Selhe e Arlindo Catusso.",
            "Solicita tapa-buraco na Rua Nova em toda a sua extensão, no Parque Oziel.",
            "Solicita reparos na ponte de pedestres da Rua Cabo Rubens Zimmermman, "
            "no Jardim Monte Cristo/Parque Oziel.",
            "Solicita manilhas para construção de fossa coletiva na Rua Hum, no "
            "Parque Oziel, atrás do campo de futebol.",
        ]
        return [
            DataPoint(
                skill=SKILL_NAME,
                indicador="Demanda na Câmara p/ o Oziel",
                valor=ementa,
                unidade="",
                fonte=fonte,
                fonte_url=f"{BASE_URL}/atividade-legislativa/pesquisa-de-proposicoes-1",
                localidade_nome=LOCALIDADE,
                localidade_nivel=1,
                ano_referencia="2026",
            )
            for ementa in exemplos
        ]

    def run(self, tags: list[str] | None = None) -> list[DataPoint]:
        return self.get_demandas_oziel()
