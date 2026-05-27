"""
ResearchAgent — descobre novos memes políticos via RSS e fact-checkers.
NÃO usa Claude API — é puramente determinístico.
Resultado: lista de MemeCandidate deduplicados por hash.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.base_agent import BaseAgent
from skills.rss_factcheck import MemeCandidate, RSSFactCheckSkill

logger = logging.getLogger(__name__)


class ResearchAgent(BaseAgent):
    def __init__(
        self,
        sources: list[dict] | None = None,
        lookback_hours: int = 72,
        min_score: float = 0.4,
        timeout: int = 20,
        max_workers: int = 4,
    ) -> None:
        super().__init__(name="researcher", client=None)
        self.skill = RSSFactCheckSkill(
            sources=sources,
            lookback_hours=lookback_hours,
            min_score=min_score,
            timeout=timeout,
        )
        self.max_workers = max_workers

    def run(self) -> list[MemeCandidate]:
        """Executa todas as fontes RSS em paralelo. Retorna candidatos deduplicados."""
        self.log(f"Iniciando pesquisa em {len(self.skill.sources)} fontes RSS...")
        all_candidates: list[MemeCandidate] = []
        seen: set[str] = set()

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self._fetch_source, src): src["agencia"]
                for src in self.skill.sources
            }
            for future in as_completed(futures):
                agencia = futures[future]
                try:
                    candidates = future.result()
                    for c in candidates:
                        h = _hash(c.meme_texto)
                        if h not in seen:
                            seen.add(h)
                            all_candidates.append(c)
                    self.log(f"{agencia}: {len(candidates)} candidato(s)")
                except Exception as exc:
                    self.log(f"{agencia}: falhou — {exc}", "WARNING")

        sorted_candidates = sorted(all_candidates, key=lambda c: c.score, reverse=True)
        self.log(f"Total de candidatos únicos: {len(sorted_candidates)}")
        return sorted_candidates

    def _fetch_source(self, source: dict) -> list[MemeCandidate]:
        return self.skill._fetch_source(source)

    def run_from_xml(self, xml_content: str, agencia: str = "lupa") -> list[MemeCandidate]:
        """Para testes: parseia XML diretamente sem network."""
        return self.skill.fetch_from_xml(xml_content, agencia)


def _hash(texto: str) -> str:
    import hashlib
    return hashlib.md5(texto.strip().lower().encode()).hexdigest()
