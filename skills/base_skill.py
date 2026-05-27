"""
BaseSkill — interface comum para todas as skills de dados abertos.
Cada skill retorna list[DataPoint] com fonte rastreável.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DataPoint:
    skill: str
    indicador: str
    valor: str
    unidade: str
    fonte: str
    localidade_nome: str
    localidade_nivel: int          # 1=bairro, 2=Campinas, 3=RM, 4=SP, 5=Brasil
    fonte_url: str = ""
    ano_referencia: str = ""

    def to_dict(self) -> dict:
        return {
            "skill": self.skill,
            "indicador": self.indicador,
            "valor": self.valor,
            "unidade": self.unidade,
            "fonte": self.fonte,
            "fonte_url": self.fonte_url,
            "localidade_nome": self.localidade_nome,
            "localidade_nivel": self.localidade_nivel,
            "ano_referencia": self.ano_referencia,
        }

    def para_prompt(self) -> str:
        """Formatação para inserção no prompt do ContentGenerator."""
        loc = f"{self.localidade_nome} ({self.ano_referencia})" if self.ano_referencia else self.localidade_nome
        return f"• {self.indicador}: {self.valor} {self.unidade} — {loc} [Fonte: {self.fonte}]"
