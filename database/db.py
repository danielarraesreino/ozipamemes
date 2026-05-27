"""
DatabaseManager — wrapper SQLite para o OzielMemes Pipeline.
Todas as operações são síncronas e thread-safe via check_same_thread=False.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _hash_meme(texto: str) -> str:
    normalizado = texto.strip().lower()
    return hashlib.sha256(normalizado.encode()).hexdigest()


class DatabaseManager:
    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def init_db(self) -> None:
        schema = SCHEMA_PATH.read_text()
        self.conn.executescript(schema)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Memes ─────────────────────────────────────────────────────────────────

    def insert_meme(self, meme: dict) -> str:
        """Insere ou ignora (já existe pelo hash). Retorna o ID."""
        hash_m = _hash_meme(meme["meme_texto"])
        self.conn.execute(
            """
            INSERT OR IGNORE INTO memes
              (id, hash_meme, meme_texto, categoria, formato, origem, viralizou,
               modulo, dificuldade, tags, usado_no_jogo, card_gerado, roteiro_tiktok,
               source_url, source_rss)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                meme.get("id") or f"m_{hash_m[:8]}",
                hash_m,
                meme["meme_texto"],
                meme.get("categoria", "desinformacao"),
                meme.get("formato", "texto_viral"),
                meme.get("origem"),
                meme.get("viralizou"),
                meme.get("modulo"),
                meme.get("dificuldade", 2),
                json.dumps(meme.get("tags", []), ensure_ascii=False),
                int(meme.get("usado_no_jogo", False)),
                int(meme.get("card_gerado", False)),
                int(meme.get("roteiro_tiktok", False)),
                meme.get("source_url"),
                meme.get("source_rss"),
            ),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM memes WHERE hash_meme = ?", (hash_m,)
        ).fetchone()
        return row["id"]

    def get_meme_by_hash(self, texto: str) -> dict | None:
        h = _hash_meme(texto)
        row = self.conn.execute(
            "SELECT * FROM memes WHERE hash_meme = ?", (h,)
        ).fetchone()
        return dict(row) if row else None

    def get_meme_by_id(self, meme_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM memes WHERE id = ?", (meme_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_memes(
        self,
        categoria: str | None = None,
        modulo: str | None = None,
        usado_no_jogo: bool | None = None,
    ) -> list[dict]:
        q = "SELECT * FROM memes WHERE 1=1"
        params: list[Any] = []
        if categoria:
            q += " AND categoria = ?"
            params.append(categoria)
        if modulo:
            q += " AND modulo = ?"
            params.append(modulo)
        if usado_no_jogo is not None:
            q += " AND usado_no_jogo = ?"
            params.append(int(usado_no_jogo))
        rows = self.conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def update_meme_field(self, meme_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [meme_id]
        self.conn.execute(
            f"UPDATE memes SET {sets}, updated_at = datetime('now') WHERE id = ?", vals
        )
        self.conn.commit()

    def count_memes(self) -> dict:
        row = self.conn.execute(
            """SELECT
               COUNT(*) as total,
               SUM(usado_no_jogo) as no_jogo,
               SUM(roteiro_tiktok) as com_tiktok
            FROM memes"""
        ).fetchone()
        return dict(row)

    # ── Verificações ──────────────────────────────────────────────────────────

    def insert_verificacao(self, meme_id: str, verif: dict) -> int:
        self.conn.execute(
            "UPDATE verificacoes SET is_current = 0 WHERE meme_id = ?", (meme_id,)
        )
        cur = self.conn.execute(
            """INSERT INTO verificacoes
               (meme_id, status, fonte, fonte_url, explicacao, data_verificacao, agencia, is_current)
               VALUES (?,?,?,?,?,?,?,1)""",
            (
                meme_id,
                verif["status"],
                verif["fonte"],
                verif.get("fonte_url"),
                verif.get("explicacao"),
                verif.get("data_verificacao"),
                verif.get("agencia"),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_verificacao_atual(self, meme_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM verificacoes WHERE meme_id = ? AND is_current = 1",
            (meme_id,),
        ).fetchone()
        return dict(row) if row else None

    # ── DataPoints ────────────────────────────────────────────────────────────

    def insert_data_point(self, meme_id: str, dp: dict) -> int:
        cur = self.conn.execute(
            """INSERT INTO data_points
               (meme_id, skill, indicador, valor, unidade, fonte, fonte_url,
                localidade_nome, localidade_nivel, ano_referencia)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                meme_id,
                dp["skill"],
                dp["indicador"],
                str(dp["valor"]),
                dp.get("unidade"),
                dp["fonte"],
                dp.get("fonte_url"),
                dp["localidade_nome"],
                dp["localidade_nivel"],
                dp.get("ano_referencia"),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_data_points(self, meme_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM data_points WHERE meme_id = ? ORDER BY localidade_nivel",
            (meme_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Conteúdo gerado ───────────────────────────────────────────────────────

    def insert_conteudo(self, meme_id: str, conteudo: dict) -> int:
        self.conn.execute(
            "UPDATE conteudo_gerado SET is_current = 0 WHERE meme_id = ?", (meme_id,)
        )
        cur = self.conn.execute(
            """INSERT INTO conteudo_gerado
               (meme_id, contexto_oculto, pilula_sabedoria, roteiro_tiktok,
                modelo_claude, prompt_version, tokens_input, tokens_output, is_current)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (
                meme_id,
                conteudo["contexto_oculto"],
                conteudo["pilula_sabedoria"],
                conteudo.get("roteiro_tiktok"),
                conteudo["modelo_claude"],
                conteudo["prompt_version"],
                conteudo.get("tokens_input"),
                conteudo.get("tokens_output"),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_conteudo_atual(self, meme_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM conteudo_gerado WHERE meme_id = ? AND is_current = 1",
            (meme_id,),
        ).fetchone()
        return dict(row) if row else None

    # ── Pipeline Queue ────────────────────────────────────────────────────────

    def upsert_queue_item(self, item: dict) -> int:
        h = _hash_meme(item["meme_texto_raw"])
        existing = self.conn.execute(
            "SELECT id, estado FROM pipeline_queue WHERE meme_hash = ?", (h,)
        ).fetchone()

        if existing:
            # Só atualiza se não estiver em estado terminal
            if existing["estado"] not in ("approved", "archived"):
                self.conn.execute(
                    """UPDATE pipeline_queue
                       SET estado = ?, metadados = ?, estado_atualizado_em = datetime('now')
                       WHERE id = ?""",
                    (item.get("estado", existing["estado"]),
                     json.dumps(item.get("metadados", {}), ensure_ascii=False),
                     existing["id"]),
                )
                self.conn.commit()
            return existing["id"]

        cur = self.conn.execute(
            """INSERT INTO pipeline_queue
               (meme_hash, meme_texto_raw, estado, source_url, source_rss, metadados, max_tentativas)
               VALUES (?,?,?,?,?,?,?)""",
            (
                h,
                item["meme_texto_raw"],
                item.get("estado", "discovered"),
                item.get("source_url"),
                item.get("source_rss"),
                json.dumps(item.get("metadados", {}), ensure_ascii=False),
                item.get("max_tentativas", 3),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_queue_by_estado(self, estado: str, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            """SELECT * FROM pipeline_queue
               WHERE estado = ? AND tentativas < max_tentativas
               ORDER BY candidato_criado_em
               LIMIT ?""",
            (estado, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["metadados"] = json.loads(d["metadados"] or "{}")
            result.append(d)
        return result

    def update_queue_estado(
        self,
        queue_id: int,
        novo_estado: str,
        metadados: dict | None = None,
        erro: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {"estado": novo_estado}
        if erro:
            updates["erro_ultimo"] = erro[:2000]
        if novo_estado in ("approved", "rejected", "archived"):
            updates["processado_em"] = "datetime('now')"

        # Incrementa tentativas quando vai para estado de processamento
        if novo_estado in ("fact_checking", "enriching", "generating", "reviewing"):
            self.conn.execute(
                "UPDATE pipeline_queue SET tentativas = tentativas + 1 WHERE id = ?",
                (queue_id,),
            )

        set_clause = ", ".join(
            f"{k} = {v}" if v == "datetime('now')" else f"{k} = ?"
            for k, v in updates.items()
        )
        vals = [v for v in updates.values() if v != "datetime('now')"]
        self.conn.execute(
            f"""UPDATE pipeline_queue
                SET {set_clause},
                    estado_atualizado_em = datetime('now')
                    {', metadados = ?' if metadados is not None else ''}
                WHERE id = ?""",
            vals + ([json.dumps(metadados, ensure_ascii=False)] if metadados is not None else []) + [queue_id],
        )
        self.conn.commit()

    def link_queue_to_meme(self, queue_id: int, meme_id: str) -> None:
        self.conn.execute(
            "UPDATE pipeline_queue SET meme_id = ? WHERE id = ?", (meme_id, queue_id)
        )
        self.conn.commit()

    def get_queue_stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT estado, COUNT(*) as n FROM pipeline_queue GROUP BY estado"
        ).fetchall()
        return {r["estado"]: r["n"] for r in rows}

    def reset_failed(self) -> int:
        self.conn.execute(
            """UPDATE pipeline_queue
               SET tentativas = 0, erro_ultimo = NULL, estado = 'discovered'
               WHERE estado IN ('rejected', 'discovered')
               AND tentativas >= max_tentativas"""
        )
        self.conn.commit()
        n = self.conn.execute("SELECT changes()").fetchone()[0]
        return n

    # ── Pipeline Runs ─────────────────────────────────────────────────────────

    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO pipeline_runs DEFAULT VALUES")
        self.conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, stats: dict) -> None:
        self.conn.execute(
            """UPDATE pipeline_runs
               SET finalizado_em = datetime('now'),
                   memes_descobertos = ?,
                   memes_aprovados = ?,
                   memes_rejeitados = ?,
                   erros = ?,
                   status = ?
               WHERE id = ?""",
            (
                stats.get("descobertos", 0),
                stats.get("aprovados", 0),
                stats.get("rejeitados", 0),
                stats.get("erros", 0),
                stats.get("status", "success"),
                run_id,
            ),
        )
        self.conn.commit()

    # ── Import do memes.json ──────────────────────────────────────────────────

    def import_from_json(self, json_path: str) -> int:
        """
        Importa memes do memes.json existente para o SQLite.
        Marca todos como approved na fila (curados manualmente).
        Retorna quantidade importada.
        """
        import json as json_mod

        data = json_mod.loads(Path(json_path).read_text())
        memes_raw = data.get("memes", [])
        count = 0

        for m in memes_raw:
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
                self.insert_verificacao(
                    meme_id,
                    {
                        "status": verif.get("status", "enganoso"),
                        "fonte": verif.get("fonte", "manual"),
                        "fonte_url": verif.get("url"),
                        "explicacao": verif.get("explicacao"),
                        "agencia": "curado_manual",
                    },
                )

            conteudo = {
                "contexto_oculto": m.get("contexto_oculto", ""),
                "pilula_sabedoria": m.get("pilula_sabedoria", ""),
                "roteiro_tiktok": None,
                "modelo_claude": "manual",
                "prompt_version": "v0_manual",
            }
            if conteudo["contexto_oculto"]:
                self.insert_conteudo(meme_id, conteudo)

            # Marca como approved na fila (já curado)
            queue_id = self.upsert_queue_item(
                {
                    "meme_texto_raw": meme_dict["meme_texto"],
                    "estado": "approved",
                    "source_rss": "curado_manual",
                }
            )
            self.link_queue_to_meme(queue_id, meme_id)
            count += 1

        return count
