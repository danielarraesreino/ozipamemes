"""
DataEnricher — coleta dados abertos relevantes para contextualizar um meme.
NÃO usa Claude API — é determinístico.
Resolve skills via mapeamento tag → skill e aplica hierarquia de localidade.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, as_completed

from agents.base_agent import BaseAgent
from config import Config
from skills.base_skill import DataPoint
from skills.cache import SkillCache
from skills.ibge_api import IBGESkill
from skills.seade_api import SEADESkill
from skills.ssp_violencia import SSPViolenciaSkill
from skills.tse_data import TSESkill
from skills.transparencia_federal import TransparenciaFederalSkill

logger = logging.getLogger(__name__)

SKILL_TIMEOUT = 30  # segundos por skill


class DataEnricher(BaseAgent):
    def __init__(
        self,
        config: Config | None = None,
        cache: SkillCache | None = None,
    ) -> None:
        super().__init__(name="enricher", client=None)
        self.config = config
        self.cache = cache
        self._skills = self._build_skills()

    def _build_skills(self) -> dict:
        return {
            "ibge_demografico": IBGESkill(cache=self.cache),
            "ibge_educacao": IBGESkill(cache=self.cache),  # mesma skill, subconjunto diferente
            "tse_data": TSESkill(cache=self.cache),
            "seade": SEADESkill(cache=self.cache),
            "ssp_violencia": SSPViolenciaSkill(cache=self.cache),
            "transparencia_federal": TransparenciaFederalSkill(
                cache=self.cache,
                api_key=self.config.transparencia_api_key if self.config else "",
            ),
        }

    def run(self, meme: dict, tags: list[str]) -> list[DataPoint]:
        """
        Coleta DataPoints para o meme com base nas suas tags.
        Prioriza dados de Campinas (nível 2) sobre dados nacionais.
        """
        skill_names = self._resolve_skills(tags)
        self.log(f"Tags: {tags} → skills: {skill_names}")

        if not skill_names:
            # Sem mapeamento específico: coleta dados gerais de Campinas
            skill_names = ["tse_data", "ibge_demografico"]

        all_dps: list[DataPoint] = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(self._invoke_skill, sn, tags): sn
                for sn in skill_names
            }
            for future in as_completed(futures, timeout=SKILL_TIMEOUT * len(skill_names)):
                skill_name = futures[future]
                try:
                    dps = future.result(timeout=SKILL_TIMEOUT)
                    all_dps.extend(dps)
                    self.log(f"{skill_name}: {len(dps)} DataPoint(s)")
                except FutureTimeout:
                    self.log(f"{skill_name}: timeout após {SKILL_TIMEOUT}s", "WARNING")
                except Exception as exc:
                    self.log(f"{skill_name}: erro — {exc}", "WARNING")

        return self._rank_by_localidade(all_dps)

    def _resolve_skills(self, tags: list[str]) -> list[str]:
        """Mapeia tags para nomes de skills usando config.tag_to_skills."""
        tag_map = {}
        if self.config:
            tag_map = self.config.tag_to_skills
        else:
            # Mapeamento padrão sem config
            tag_map = {
                "eleicao": ["tse_data"],
                "eleição": ["tse_data"],
                "voto": ["tse_data"],
                "vereador": ["tse_data"],
                "saúde": ["ibge_demografico"],
                "violencia": ["ssp_violencia"],
                "violência": ["ssp_violencia"],
                "educacao": ["ibge_educacao"],
                "bolsa família": ["transparencia_federal"],
                "bolsa familia": ["transparencia_federal"],
            }

        resolved: set[str] = set()
        for tag in tags:
            tag_lower = tag.lower()
            for pattern, skills in tag_map.items():
                if pattern.lower() in tag_lower or tag_lower in pattern.lower():
                    resolved.update(skills)
        return list(resolved)

    def _invoke_skill(self, skill_name: str, tags: list[str]) -> list[DataPoint]:
        skill = self._skills.get(skill_name)
        if skill is None:
            self.log(f"Skill '{skill_name}' não encontrada", "WARNING")
            return []
        return skill.run(tags=tags)

    def _rank_by_localidade(self, data_points: list[DataPoint]) -> list[DataPoint]:
        """Ordena DataPoints por proximidade geográfica (menor nível = mais local)."""
        return sorted(data_points, key=lambda dp: dp.localidade_nivel)

    def format_for_prompt(self, data_points: list[DataPoint]) -> str:
        """Formata DataPoints para inserção no prompt do ContentGenerator."""
        if not data_points:
            return "(Nenhum dado aberto disponível para este tema)"
        lines = []
        for i, dp in enumerate(data_points, 1):
            lines.append(f"{i}. {dp.para_prompt()}")
        return "\n".join(lines)
