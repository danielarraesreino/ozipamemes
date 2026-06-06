"""
DatabaseManager — Supabase via HTTP (supabase-py / PostgREST).
Interface idêntica ao db.py (SQLite). Funciona de qualquer rede via HTTPS.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _hash_meme(texto: str) -> str:
    return hashlib.sha256(texto.strip().lower().encode()).hexdigest()


def _client():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


class DatabaseManager:
    def __init__(self, db_path: str = "") -> None:
        self.db_path = db_path
        self._sb = None

    @property
    def sb(self):
        if self._sb is None:
            self._sb = _client()
        return self._sb

    def init_db(self) -> None:
        # Tabelas já criadas via schema_postgres.sql — noop aqui
        pass

    def close(self) -> None:
        self._sb = None

    # ── Memes ─────────────────────────────────────────────────────────────────

    def insert_meme(self, meme: dict) -> str:
        hash_m = _hash_meme(meme["meme_texto"])
        meme_id = meme.get("id") or f"m_{hash_m[:8]}"
        data = {
            "id": meme_id,
            "hash_meme": hash_m,
            "meme_texto": meme["meme_texto"],
            "categoria": meme.get("categoria", "desinformacao"),
            "formato": meme.get("formato", "texto_viral"),
            "origem": meme.get("origem"),
            "viralizou": meme.get("viralizou"),
            "modulo": meme.get("modulo"),
            "dificuldade": meme.get("dificuldade", 2),
            "tags": json.dumps(meme.get("tags", []), ensure_ascii=False),
            "usado_no_jogo": int(meme.get("usado_no_jogo", False)),
            "card_gerado": int(meme.get("card_gerado", False)),
            "roteiro_tiktok": int(meme.get("roteiro_tiktok", False)),
            "source_url": meme.get("source_url"),
            "source_rss": meme.get("source_rss"),
        }
        self.sb.from_("memes").upsert(data, on_conflict="hash_meme", ignore_duplicates=True).execute()
        row = self.sb.from_("memes").select("id").eq("hash_meme", hash_m).execute()
        return row.data[0]["id"]

    def get_meme_by_hash(self, texto: str) -> dict | None:
        h = _hash_meme(texto)
        r = self.sb.from_("memes").select("*").eq("hash_meme", h).execute()
        return r.data[0] if r.data else None

    def get_meme_by_id(self, meme_id: str) -> dict | None:
        r = self.sb.from_("memes").select("*").eq("id", meme_id).execute()
        return r.data[0] if r.data else None

    def list_memes(
        self,
        categoria: str | None = None,
        modulo: str | None = None,
        usado_no_jogo: bool | None = None,
    ) -> list[dict]:
        q = self.sb.from_("memes").select("*")
        if categoria:
            q = q.eq("categoria", categoria)
        if modulo:
            q = q.eq("modulo", modulo)
        if usado_no_jogo is not None:
            q = q.eq("usado_no_jogo", int(usado_no_jogo))
        return q.execute().data or []

    def update_meme_field(self, meme_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        self.sb.from_("memes").update(kwargs).eq("id", meme_id).execute()

    def count_memes(self) -> dict:
        rows = self.sb.from_("memes").select("usado_no_jogo,roteiro_tiktok").execute().data or []
        return {
            "total": len(rows),
            "no_jogo": sum(1 for r in rows if r.get("usado_no_jogo")),
            "com_tiktok": sum(1 for r in rows if r.get("roteiro_tiktok")),
        }

    # ── Verificações ──────────────────────────────────────────────────────────

    def insert_verificacao(self, meme_id: str, verif: dict) -> int:
        self.sb.from_("verificacoes").update({"is_current": 0}).eq("meme_id", meme_id).execute()
        r = self.sb.from_("verificacoes").insert({
            "meme_id": meme_id,
            "status": verif["status"],
            "fonte": verif["fonte"],
            "fonte_url": verif.get("fonte_url"),
            "explicacao": verif.get("explicacao"),
            "data_verificacao": verif.get("data_verificacao"),
            "agencia": verif.get("agencia"),
            "is_current": 1,
        }).execute()
        return r.data[0]["id"]

    def get_verificacao_atual(self, meme_id: str) -> dict | None:
        r = self.sb.from_("verificacoes").select("*").eq("meme_id", meme_id).eq("is_current", 1).execute()
        return r.data[0] if r.data else None

    # ── DataPoints ────────────────────────────────────────────────────────────

    def insert_data_point(self, meme_id: str, dp: dict) -> int:
        r = self.sb.from_("data_points").insert({
            "meme_id": meme_id,
            "skill": dp["skill"],
            "indicador": dp["indicador"],
            "valor": str(dp["valor"]),
            "unidade": dp.get("unidade"),
            "fonte": dp["fonte"],
            "fonte_url": dp.get("fonte_url"),
            "localidade_nome": dp["localidade_nome"],
            "localidade_nivel": dp["localidade_nivel"],
            "ano_referencia": dp.get("ano_referencia"),
        }).execute()
        return r.data[0]["id"]

    def get_data_points(self, meme_id: str) -> list[dict]:
        r = self.sb.from_("data_points").select("*").eq("meme_id", meme_id).order("localidade_nivel").execute()
        return r.data or []

    # ── Conteúdo gerado ───────────────────────────────────────────────────────

    def insert_conteudo(self, meme_id: str, conteudo: dict) -> int:
        self.sb.from_("conteudo_gerado").update({"is_current": 0}).eq("meme_id", meme_id).execute()
        r = self.sb.from_("conteudo_gerado").insert({
            "meme_id": meme_id,
            "contexto_oculto": conteudo["contexto_oculto"],
            "pilula_sabedoria": conteudo["pilula_sabedoria"],
            "objetivo_meme": conteudo.get("objetivo_meme"),
            "pilula_alt1": conteudo.get("pilula_alt1"),
            "pilula_alt2": conteudo.get("pilula_alt2"),
            "roteiro_tiktok": conteudo.get("roteiro_tiktok"),
            "modelo_claude": conteudo["modelo_claude"],
            "prompt_version": conteudo["prompt_version"],
            "tokens_input": conteudo.get("tokens_input"),
            "tokens_output": conteudo.get("tokens_output"),
            "is_current": 1,
        }).execute()
        return r.data[0]["id"]

    def get_conteudo_atual(self, meme_id: str) -> dict | None:
        r = self.sb.from_("conteudo_gerado").select("*").eq("meme_id", meme_id).eq("is_current", 1).execute()
        return r.data[0] if r.data else None

    # ── Pipeline Queue ────────────────────────────────────────────────────────

    def upsert_queue_item(self, item: dict) -> int:
        h = _hash_meme(item["meme_texto_raw"])
        existing = self.sb.from_("pipeline_queue").select("id,estado").eq("meme_hash", h).execute()
        if existing.data:
            row = existing.data[0]
            if row["estado"] not in ("approved", "archived"):
                self.sb.from_("pipeline_queue").update({
                    "estado": item.get("estado", row["estado"]),
                    "metadados": json.dumps(item.get("metadados", {}), ensure_ascii=False),
                }).eq("id", row["id"]).execute()
            return row["id"]

        r = self.sb.from_("pipeline_queue").insert({
            "meme_hash": h,
            "meme_texto_raw": item["meme_texto_raw"],
            "estado": item.get("estado", "discovered"),
            "source_url": item.get("source_url"),
            "source_rss": item.get("source_rss"),
            "metadados": json.dumps(item.get("metadados", {}), ensure_ascii=False),
            "max_tentativas": item.get("max_tentativas", 3),
        }).execute()
        return r.data[0]["id"]

    def get_queue_by_estado(self, estado: str, limit: int = 50) -> list[dict]:
        r = (self.sb.from_("pipeline_queue")
             .select("*")
             .eq("estado", estado)
             .lt("tentativas", 3)
             .order("candidato_criado_em")
             .limit(limit)
             .execute())
        result = []
        for row in (r.data or []):
            d = dict(row)
            d["metadados"] = json.loads(d.get("metadados") or "{}")
            result.append(d)
        return result

    def update_queue_estado(
        self,
        queue_id: int,
        novo_estado: str,
        metadados: dict | None = None,
        erro: str | None = None,
    ) -> None:
        if novo_estado in ("fact_checking", "enriching", "generating", "reviewing"):
            row = self.sb.from_("pipeline_queue").select("tentativas").eq("id", queue_id).execute()
            if row.data:
                self.sb.from_("pipeline_queue").update({
                    "tentativas": row.data[0]["tentativas"] + 1
                }).eq("id", queue_id).execute()

        update: dict[str, Any] = {"estado": novo_estado}
        if erro:
            update["erro_ultimo"] = erro[:2000]
        if novo_estado in ("approved", "rejected", "archived"):
            update["processado_em"] = "now()"
        if metadados is not None:
            update["metadados"] = json.dumps(metadados, ensure_ascii=False)
        self.sb.from_("pipeline_queue").update(update).eq("id", queue_id).execute()

    def link_queue_to_meme(self, queue_id: int, meme_id: str) -> None:
        self.sb.from_("pipeline_queue").update({"meme_id": meme_id}).eq("id", queue_id).execute()

    def get_approved_meme_ids(self) -> set:
        r = (self.sb.from_("pipeline_queue")
             .select("meme_id")
             .eq("estado", "approved")
             .not_.is_("meme_id", "null")
             .execute())
        return {row["meme_id"] for row in (r.data or [])}

    def reset_failed(self) -> int:
        rows = (self.sb.from_("pipeline_queue")
                .select("id")
                .in_("estado", ["rejected", "discovered"])
                .gte("tentativas", 3)
                .execute().data or [])
        ids = [r["id"] for r in rows]
        if ids:
            self.sb.from_("pipeline_queue").update({
                "tentativas": 0,
                "erro_ultimo": None,
                "estado": "discovered",
            }).in_("id", ids).execute()
        return len(ids)

    def get_queue_stats(self) -> dict:
        rows = self.sb.from_("pipeline_queue").select("estado").execute().data or []
        stats: dict[str, int] = {}
        for r in rows:
            e = r["estado"]
            stats[e] = stats.get(e, 0) + 1
        return stats

    # ── Pipeline Runs ─────────────────────────────────────────────────────────

    def start_run(self) -> int:
        r = self.sb.from_("pipeline_runs").insert({"status": "running"}).execute()
        return r.data[0]["id"]

    def finish_run(self, run_id: int, stats: dict) -> None:
        self.sb.from_("pipeline_runs").update({
            "memes_descobertos": stats.get("descobertos", 0),
            "memes_aprovados": stats.get("aprovados", 0),
            "memes_rejeitados": stats.get("rejeitados", 0),
            "erros": stats.get("erros", 0),
            "status": stats.get("status", "success"),
        }).eq("id", run_id).execute()

    # ── Import do memes.json ──────────────────────────────────────────────────

    def import_from_json(self, json_path: str) -> int:
        data = json.loads(Path(json_path).read_text())
        count = 0
        for m in data.get("memes", []):
            meme_dict = {
                "id": m["id"],
                "meme_texto": m["meme"].strip('"').strip("'"),
                "categoria": m.get("categoria", "desinformacao"),
                "formato": m.get("formato", "texto_viral"),
                "origem": m.get("origem"),
                "viralizou": m.get("viralizou"),
                "modulo": m.get("modulo"),
                "dificuldade": m.get("dificuldade", 2),
                "tags": m.get("tags", []),
                "usado_no_jogo": m.get("usado_no_jogo", False),
                "card_gerado": m.get("card_gerado", False),
                "roteiro_tiktok": m.get("roteiro_tiktok", False),
            }
            meme_id = self.insert_meme(meme_dict)
            verif = m.get("verificacao", {})
            if verif:
                self.insert_verificacao(meme_id, {
                    "status": verif.get("status", "enganoso"),
                    "fonte": verif.get("fonte", "manual"),
                    "fonte_url": verif.get("url"),
                    "explicacao": verif.get("explicacao"),
                    "agencia": "curado_manual",
                })
            conteudo = {
                "contexto_oculto": m.get("contexto_oculto", ""),
                "pilula_sabedoria": m.get("pilula_sabedoria", ""),
                "roteiro_tiktok": None,
                "modelo_claude": "manual",
                "prompt_version": "v0_manual",
            }
            if conteudo["contexto_oculto"]:
                self.insert_conteudo(meme_id, conteudo)
            queue_id = self.upsert_queue_item({
                "meme_texto_raw": meme_dict["meme_texto"],
                "estado": "approved",
                "source_rss": "curado_manual",
            })
            self.link_queue_to_meme(queue_id, meme_id)
            count += 1
        return count
