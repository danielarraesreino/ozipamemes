"""
QualityReviewer — valida conteúdo gerado contra as 8 golden rules.
NÃO usa Claude API — todas as validações são determinísticas e testáveis.
"""
from __future__ import annotations

import json
import logging

from agents.base_agent import BaseAgent
from database.db import DatabaseManager
from golden_rules import ReviewResult, formatar_resultado, revisar
from skills.base_skill import DataPoint

logger = logging.getLogger(__name__)


class QualityReviewer(BaseAgent):
    def __init__(self, db: DatabaseManager | None = None) -> None:
        super().__init__(name="reviewer", client=None)
        self.db = db

    def run(
        self,
        meme: dict,
        conteudo: dict,
        data_points: list[DataPoint | dict],
    ) -> ReviewResult:
        """
        Aplica as 8 golden rules ao conteúdo gerado.
        Salva resultado no DB se disponível.
        Retorna ReviewResult.
        """
        contexto = conteudo.get("contexto_oculto", "")
        pilula = conteudo.get("pilula_sabedoria", "")

        # Normaliza DataPoints para dict
        dps_dict = [
            dp.to_dict() if isinstance(dp, DataPoint) else dp
            for dp in data_points
        ]

        resultado = revisar(meme, contexto, pilula, dps_dict)

        self.log(
            f"Meme {meme.get('id', '?')}: {formatar_resultado(resultado)}"
        )

        if self.db and meme.get("id"):
            self._salvar_resultado(meme["id"], conteudo, resultado)

        return resultado

    def _salvar_resultado(
        self,
        meme_id: str,
        conteudo: dict,
        resultado: ReviewResult,
    ) -> None:
        conteudo_id = conteudo.get("id")
        self.db.conn.execute(
            """INSERT INTO revisoes_qualidade
               (meme_id, conteudo_id, aprovado, score,
                regras_aprovadas, regras_reprovadas, flags, observacoes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                meme_id,
                conteudo_id,
                int(resultado.aprovado),
                resultado.score,
                json.dumps(resultado.regras_aprovadas),
                json.dumps(resultado.regras_reprovadas),
                json.dumps(resultado.flags),
                "\n".join(resultado.observacoes),
            ),
        )
        self.db.conn.commit()

    def precisa_regenerar(self, resultado: ReviewResult) -> bool:
        """Retorna True se o conteúdo deve ser regenerado (há regras bloqueantes reprovadas)."""
        from golden_rules import REGRAS_BLOQUEANTES
        return bool(set(resultado.regras_reprovadas) & REGRAS_BLOQUEANTES)

    def formatar_feedback(self, resultado: ReviewResult) -> str:
        """Feedback estruturado para enviar ao ContentGenerator em caso de regeneração."""
        if resultado.aprovado:
            return "CONTEÚDO APROVADO"

        linhas = ["REJEIÇÃO — ajuste o conteúdo:"]
        for obs in resultado.observacoes:
            linhas.append(f"• {obs}")
        if resultado.flags:
            for flag, val in resultado.flags.items():
                if val:
                    linhas.append(f"⚠️  {flag}")
        return "\n".join(linhas)
