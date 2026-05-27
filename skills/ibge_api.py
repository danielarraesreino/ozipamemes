"""
IBGE SIDRA API — skill para dados demográficos, educação e renda.
API pública: https://servicodados.ibge.gov.br/api/v3/

Localidades usadas:
  N6[3509502] = Campinas (código IBGE)
  N3[35]      = Estado de SP
  N1[1]       = Brasil
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from skills.base_skill import DataPoint
from skills.cache import SkillCache

logger = logging.getLogger(__name__)

SKILL_NAME = "ibge_demografico"
BASE_URL = "https://servicodados.ibge.gov.br/api/v3"
CAMPINAS_CODE = "3509502"

# Agregados IBGE SIDRA usados
# Formato: (agregado_id, variavel_id, descrição, unidade)
INDICADORES = {
    "populacao": (9514, 93, "População residente", "habitantes"),
    "renda_media": (7358, 5928, "Rendimento médio mensal", "R$"),
    "taxa_analfabetismo": (9543, 1640, "Taxa de analfabetismo (15+ anos)", "%"),
    "domicilios_sem_esgoto": (9514, 10112, "Domicílios sem esgotamento adequado", "%"),
}


def _get(url: str, params: dict | None = None, timeout: int = 30) -> Any:
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _fetch_indicador(
    agregado_id: int,
    variavel_id: int,
    localidade_cod: str,
    localidade_nivel_sigla: str,  # N6, N3, N1
    localidade_nome: str,
    localidade_nivel: int,
    periodo: str = "2022",
    timeout: int = 30,
) -> DataPoint | None:
    url = (
        f"{BASE_URL}/agregados/{agregado_id}"
        f"/periodos/{periodo}"
        f"/variaveis/{variavel_id}"
    )
    params = {"localidades": f"{localidade_nivel_sigla}[{localidade_cod}]"}
    try:
        data = _get(url, params=params, timeout=timeout)
        if not data:
            return None
        resultado = data[0].get("resultados", [])
        if not resultado:
            return None
        series = resultado[0].get("series", [])
        if not series:
            return None
        valor = series[0].get("serie", {}).get(periodo)
        if not valor:
            return None
        return DataPoint(
            skill=SKILL_NAME,
            indicador=data[0].get("variavel", f"Variável {variavel_id}"),
            valor=str(valor),
            unidade="",  # preenchido pelo caller
            fonte=f"IBGE SIDRA — Agregado {agregado_id}",
            fonte_url=f"https://sidra.ibge.gov.br/tabela/{agregado_id}",
            localidade_nome=localidade_nome,
            localidade_nivel=localidade_nivel,
            ano_referencia=periodo,
        )
    except Exception as exc:
        logger.warning("IBGE fetch falhou para agregado=%s: %s", agregado_id, exc)
        return None


class IBGESkill:
    def __init__(
        self,
        cache: SkillCache | None = None,
        campinas_code: str = CAMPINAS_CODE,
        timeout: int = 30,
    ) -> None:
        self.cache = cache
        self.campinas_code = campinas_code
        self.timeout = timeout

    def _with_cache(self, key: str, fn) -> list[DataPoint]:
        params = {"key": key}
        if self.cache:
            cached = self.cache.get(SKILL_NAME, params)
            if cached is not None:
                return [DataPoint(**{k: v for k, v in d.items()}) for d in cached]
        result = fn()
        if self.cache and result:
            self.cache.set(SKILL_NAME, params, [dp.to_dict() for dp in result])
        return result

    def get_populacao_campinas(self) -> list[DataPoint]:
        def fetch():
            dp = _fetch_indicador(
                9514, 93,
                self.campinas_code, "N6",
                "Campinas", 2,
                periodo="2022",
                timeout=self.timeout,
            )
            if dp:
                dp.unidade = "habitantes"
            return [dp] if dp else []
        return self._with_cache("populacao_campinas", fetch)

    def get_renda_media_campinas(self) -> list[DataPoint]:
        def fetch():
            dp = _fetch_indicador(
                7358, 5928,
                self.campinas_code, "N6",
                "Campinas", 2,
                periodo="2022",
                timeout=self.timeout,
            )
            if dp:
                dp.unidade = "R$/mês"
            return [dp] if dp else []
        return self._with_cache("renda_campinas", fetch)

    def get_populacao_sp_estado(self) -> list[DataPoint]:
        def fetch():
            dp = _fetch_indicador(
                9514, 93,
                "35", "N3",
                "São Paulo (estado)", 4,
                periodo="2022",
                timeout=self.timeout,
            )
            if dp:
                dp.unidade = "habitantes"
            return [dp] if dp else []
        return self._with_cache("populacao_sp", fetch)

    def get_indicador_generico(
        self,
        agregado_id: int,
        variavel_id: int,
        periodo: str = "2022",
        localidade_nivel: int = 2,
    ) -> list[DataPoint]:
        """Interface genérica para qualquer agregado."""
        loc_map = {
            2: (self.campinas_code, "N6", "Campinas"),
            4: ("35", "N3", "São Paulo (estado)"),
            5: ("1", "N1", "Brasil"),
        }
        if localidade_nivel not in loc_map:
            return []
        cod, sigla, nome = loc_map[localidade_nivel]

        def fetch():
            dp = _fetch_indicador(
                agregado_id, variavel_id,
                cod, sigla, nome, localidade_nivel,
                periodo=periodo,
                timeout=self.timeout,
            )
            return [dp] if dp else []

        return self._with_cache(
            f"generico_{agregado_id}_{variavel_id}_{periodo}_{localidade_nivel}", fetch
        )

    def run(self, tags: list[str] | None = None) -> list[DataPoint]:
        """Coleta conjunto básico de indicadores para Campinas."""
        results: list[DataPoint] = []
        for fn in [self.get_populacao_campinas, self.get_renda_media_campinas]:
            results.extend(fn())
        return results
