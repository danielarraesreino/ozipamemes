"""
OrchestratorAgent — coordena o pipeline completo de forma autônoma.
Persiste estado no SQLite — retoma de onde parou entre execuções.

Estados da fila:
  discovered → fact_checking → enriching → generating → reviewing → approved|rejected

Cada transição é atômica no SQLite. Falhas incrementam tentativas e retomam.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import BaseAgent
from agents.enricher import DataEnricher
from agents.fact_checker import FactCheckAgent
from agents.generator import ContentGenerator
from agents.researcher import ResearchAgent
from agents.reviewer import QualityReviewer
from config import Config
from database.db import DatabaseManager
from skills.cache import SkillCache

logger = logging.getLogger(__name__)


@dataclass
class PipelineRunResult:
    run_id: int
    descobertos: int = 0
    aprovados: int = 0
    rejeitados: int = 0
    erros: int = 0
    status: str = "success"
    detalhes: list[str] = field(default_factory=list)


class OrchestratorAgent(BaseAgent):
    def __init__(
        self,
        db: DatabaseManager,
        config: Config,
        api_key: str | None = None,
        client=None,  # compat com testes antigos
    ) -> None:
        _key = api_key or (None if not isinstance(client, str) else client)
        super().__init__(name="orchestrator", api_key=_key, client=client)
        self.db = db
        self.config = config

        cache = SkillCache(config.data_cache_dir, config.cache_ttl_hours)
        self.researcher = ResearchAgent(
            sources=config.rss_sources,
            lookback_hours=config.rss_lookback_hours,
        )
        self.fact_checker = FactCheckAgent(api_key=_key, client=client)
        self.enricher = DataEnricher(config=config, cache=cache)
        self.generator = ContentGenerator(api_key=_key, model=config.claude_model, client=client)
        self.reviewer = QualityReviewer(db=db)

    def run(self, max_items: int | None = None, dry_run: bool = False) -> PipelineRunResult:
        """
        Executa um ciclo completo do pipeline.
        dry_run=True: descobre candidatos mas não salva nem gera conteúdo.
        """
        max_items = max_items or self.config.max_items_per_run
        run_id = self.db.start_run()
        result = PipelineRunResult(run_id=run_id)

        self.log(f"=== Pipeline run #{run_id} iniciado (max={max_items}, dry={dry_run}) ===")

        try:
            # 1. Pesquisa: descobre novos candidatos
            result.descobertos = self._fase_pesquisa(dry_run)

            if dry_run:
                self.log("dry-run: parando após pesquisa")
                result.status = "dry_run"
                return result

            # 2. Processa itens na fila (por estado)
            processados = 0
            for estado in ("discovered", "fact_checking", "enriching", "generating", "reviewing"):
                items = self.db.get_queue_by_estado(estado, limit=max_items - processados)
                for item in items:
                    if processados >= max_items:
                        break
                    sucesso = self._processar_item(item, result)
                    processados += 1
                    if sucesso:
                        result.aprovados += 1
                    else:
                        result.rejeitados += 1

        except Exception as exc:
            result.status = "failed"
            result.erros += 1
            self.log(f"Pipeline falhou: {exc}", "ERROR")
        finally:
            self.db.finish_run(run_id, {
                "descobertos": result.descobertos,
                "aprovados": result.aprovados,
                "rejeitados": result.rejeitados,
                "erros": result.erros,
                "status": result.status,
            })
            self.log(
                f"=== Run #{run_id} finalizado: "
                f"{result.descobertos} descobertos, "
                f"{result.aprovados} aprovados, "
                f"{result.rejeitados} rejeitados ==="
            )

        return result

    def _fase_pesquisa(self, dry_run: bool) -> int:
        """Executa ResearchAgent e insere candidatos na fila."""
        candidates = self.researcher.run()
        count = 0
        for c in candidates:
            self.db.upsert_queue_item({
                "meme_texto_raw": c.meme_texto,
                "estado": "discovered",
                "source_url": c.source_url,
                "source_rss": c.agencia,
                "metadados": c.to_dict(),
            })
            count += 1
        self.log(f"Pesquisa: {count} candidato(s) na fila")
        return count

    def _processar_item(self, item: dict, result: PipelineRunResult) -> bool:
        """
        Avança um item pelo pipeline completo.
        Retorna True se aprovado, False se rejeitado.
        """
        qid = item["id"]
        meme_texto = item["meme_texto_raw"]
        metadados: dict = item.get("metadados") or {}
        self.log(f"Processando item #{qid}: {meme_texto[:60]}...")

        try:
            # ── Fact Check ─────────────────────────────────────────────────
            self.db.update_queue_estado(qid, "fact_checking")
            from skills.rss_factcheck import MemeCandidate
            candidate = MemeCandidate(
                meme_texto=meme_texto,
                source_url=item.get("source_url", ""),
                agencia=item.get("source_rss", ""),
                titulo_original=metadados.get("titulo_original", ""),
                resumo=metadados.get("resumo", ""),
                status_verificacao=metadados.get("status_verificacao", ""),
                explicacao=metadados.get("explicacao", ""),
                score=metadados.get("score", 0.5),
            )
            fact_check = self.fact_checker.run(candidate)
            metadados["fact_check"] = fact_check

            # ── Salva meme no DB ────────────────────────────────────────────
            tags = metadados.get("tags_detectadas") or metadados.get("tags", [])
            meme_dict = {
                "meme_texto": meme_texto,
                "categoria": _infer_categoria(fact_check, tags),
                "origem": item.get("source_rss", "rss"),
                "tags": tags,
                "source_url": item.get("source_url"),
                "source_rss": item.get("source_rss"),
            }
            meme_id = self.db.insert_meme(meme_dict)
            self.db.link_queue_to_meme(qid, meme_id)
            self.db.insert_verificacao(meme_id, fact_check)

            # ── Enrichment ─────────────────────────────────────────────────
            self.db.update_queue_estado(qid, "enriching", metadados)
            data_points = self.enricher.run(meme_dict, tags)
            for dp in data_points:
                self.db.insert_data_point(meme_id, dp.to_dict() if hasattr(dp, 'to_dict') else dp)

            # ── Geração de conteúdo ─────────────────────────────────────────
            self.db.update_queue_estado(qid, "generating")
            conteudo = self.generator.run(
                meme={**meme_dict, "id": meme_id},
                fact_check=fact_check,
                data_points=data_points,
            )

            if not conteudo.get("contexto_oculto"):
                raise ValueError("ContentGenerator retornou conteúdo vazio")

            conteudo_id = self.db.insert_conteudo(meme_id, conteudo)
            conteudo["id"] = conteudo_id

            # ── Review de qualidade ─────────────────────────────────────────
            self.db.update_queue_estado(qid, "reviewing")
            review_result = self.reviewer.run(
                meme={**meme_dict, "id": meme_id},
                conteudo=conteudo,
                data_points=data_points,
            )

            # ── Decisão final ───────────────────────────────────────────────
            if review_result.aprovado:
                self.db.update_queue_estado(qid, "approved")
                self.log(f"✅ Aprovado: {meme_texto[:50]}...")
                result.detalhes.append(f"APROVADO: {meme_id}")
                return True
            else:
                # Tenta regenerar com feedback se primeira tentativa
                if item.get("tentativas", 0) < 2 and self.reviewer.precisa_regenerar(review_result):
                    feedback = self.reviewer.formatar_feedback(review_result)
                    conteudo_v2 = self.generator.run(
                        meme={**meme_dict, "id": meme_id},
                        fact_check=fact_check,
                        data_points=data_points,
                        feedback_anterior=feedback,
                    )
                    if conteudo_v2.get("contexto_oculto"):
                        conteudo_id_v2 = self.db.insert_conteudo(meme_id, conteudo_v2)
                        review_v2 = self.reviewer.run(
                            meme={**meme_dict, "id": meme_id},
                            conteudo={**conteudo_v2, "id": conteudo_id_v2},
                            data_points=data_points,
                        )
                        if review_v2.aprovado:
                            self.db.update_queue_estado(qid, "approved")
                            self.log(f"✅ Aprovado após regeneração: {meme_id}")
                            return True

                self.db.update_queue_estado(
                    qid, "rejected",
                    erro="; ".join(review_result.observacoes[:3])
                )
                self.log(f"❌ Rejeitado: {meme_id} — {review_result.observacoes[:1]}")
                result.detalhes.append(f"REJEITADO: {meme_id}")
                return False

        except Exception as exc:
            self.log(f"Erro no item #{qid}: {exc}", "ERROR")
            result.erros += 1
            self.db.update_queue_estado(qid, "discovered", erro=str(exc))
            return False

    def status(self) -> dict:
        """Retorna estatísticas atuais do pipeline."""
        return {
            "memes": self.db.count_memes(),
            "fila": self.db.get_queue_stats(),
        }


def _infer_categoria(fact_check: dict, tags: list[str]) -> str:
    """Infere categoria a partir do fact-check e das tags."""
    tags_lower = [t.lower() for t in tags]
    if any(t in tags_lower for t in ["conspiração", "conspiranismo", "globalismo"]):
        return "conspiracao"
    if any(t in tags_lower for t in ["voto", "eleição", "eleicao", "vereador", "câmara"]):
        return "apatia"
    if fact_check.get("status") in ("falso", "enganoso"):
        return "desinformacao"
    return "desinformacao"
