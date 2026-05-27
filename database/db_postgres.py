"""
DatabaseManager — PostgreSQL (Supabase).
Interface idêntica ao db.py (SQLite) — troca transparente via DATABASE_URL.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

SCHEMA_PATH = Path(__file__).parent / "schema_postgres.sql"


def _hash_meme(texto: str) -> str:
    return hashlib.sha256(texto.strip().lower().encode()).hexdigest()


def _row(cur: psycopg2.extensions.cursor) -> dict | None:
    row = cur.fetchone()
    return dict(row) if row else None


def _rows(cur: psycopg2.extensions.cursor) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


class DatabaseManager:
    def __init__(self, db_path: str = "") -> None:
        self.db_path = db_path  # ignorado — usa DATABASE_URL do env
        self._conn: psycopg2.extensions.connection | None = None

    @property
    def conn(self) -> psycopg2.extensions.connection:
        if self._conn is None or self._conn.closed:
            import os
            url = os.environ["DATABASE_URL"]
            self._conn = psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
            self._conn.autocommit = False
        return self._conn

    def _cur(self) -> psycopg2.extensions.cursor:
        return self.conn.cursor()

    def init_db(self) -> None:
        schema = SCHEMA_PATH.read_text()
        with self._cur() as cur:
            for stmt in schema.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
        self.conn.commit()

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    # ── Memes ─────────────────────────────────────────────────────────────────

    def insert_meme(self, meme: dict) -> str:
        hash_m = _hash_meme(meme["meme_texto"])
        meme_id = meme.get("id") or f"m_{hash_m[:8]}"
        with self._cur() as cur:
            cur.execute(
                """
                INSERT INTO memes
                  (id, hash_meme, meme_texto, categoria, formato, origem, viralizou,
                   modulo, dificuldade, tags, usado_no_jogo, card_gerado, roteiro_tiktok,
                   source_url, source_rss)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (hash_meme) DO NOTHING
                """,
                (
                    meme_id, hash_m, meme["meme_texto"],
                    meme.get("categoria", "desinformacao"),
                    meme.get("formato", "texto_viral"),
                    meme.get("origem"), meme.get("viralizou"),
                    meme.get("modulo"), meme.get("dificuldade", 2),
                    json.dumps(meme.get("tags", []), ensure_ascii=False),
                    int(meme.get("usado_no_jogo", False)),
                    int(meme.get("card_gerado", False)),
                    int(meme.get("roteiro_tiktok", False)),
                    meme.get("source_url"), meme.get("source_rss"),
                ),
            )
            cur.execute("SELECT id FROM memes WHERE hash_meme = %s", (hash_m,))
            row = _row(cur)
        self.conn.commit()
        return row["id"]

    def get_meme_by_hash(self, texto: str) -> dict | None:
        with self._cur() as cur:
            cur.execute("SELECT * FROM memes WHERE hash_meme = %s", (_hash_meme(texto),))
            return _row(cur)

    def get_meme_by_id(self, meme_id: str) -> dict | None:
        with self._cur() as cur:
            cur.execute("SELECT * FROM memes WHERE id = %s", (meme_id,))
            return _row(cur)

    def list_memes(
        self,
        categoria: str | None = None,
        modulo: str | None = None,
        usado_no_jogo: bool | None = None,
    ) -> list[dict]:
        q = "SELECT * FROM memes WHERE 1=1"
        params: list[Any] = []
        if categoria:
            q += " AND categoria = %s"; params.append(categoria)
        if modulo:
            q += " AND modulo = %s"; params.append(modulo)
        if usado_no_jogo is not None:
            q += " AND usado_no_jogo = %s"; params.append(int(usado_no_jogo))
        with self._cur() as cur:
            cur.execute(q, params)
            return _rows(cur)

    def update_meme_field(self, meme_id: str, **kwargs: Any) -> None:
        if not kwargs:
            return
        sets = ", ".join(f"{k} = %s" for k in kwargs)
        vals = list(kwargs.values()) + [meme_id]
        with self._cur() as cur:
            cur.execute(
                f"UPDATE memes SET {sets}, updated_at = NOW() WHERE id = %s", vals
            )
        self.conn.commit()

    def count_memes(self) -> dict:
        with self._cur() as cur:
            cur.execute(
                """SELECT COUNT(*) as total,
                          SUM(usado_no_jogo) as no_jogo,
                          SUM(roteiro_tiktok) as com_tiktok
                   FROM memes"""
            )
            return _row(cur) or {}

    # ── Verificações ──────────────────────────────────────────────────────────

    def insert_verificacao(self, meme_id: str, verif: dict) -> int:
        with self._cur() as cur:
            cur.execute(
                "UPDATE verificacoes SET is_current = 0 WHERE meme_id = %s", (meme_id,)
            )
            cur.execute(
                """INSERT INTO verificacoes
                   (meme_id, status, fonte, fonte_url, explicacao, data_verificacao, agencia, is_current)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,1) RETURNING id""",
                (meme_id, verif["status"], verif["fonte"], verif.get("fonte_url"),
                 verif.get("explicacao"), verif.get("data_verificacao"), verif.get("agencia")),
            )
            row_id = cur.fetchone()["id"]
        self.conn.commit()
        return row_id

    def get_verificacao_atual(self, meme_id: str) -> dict | None:
        with self._cur() as cur:
            cur.execute(
                "SELECT * FROM verificacoes WHERE meme_id = %s AND is_current = 1",
                (meme_id,),
            )
            return _row(cur)

    # ── DataPoints ────────────────────────────────────────────────────────────

    def insert_data_point(self, meme_id: str, dp: dict) -> int:
        with self._cur() as cur:
            cur.execute(
                """INSERT INTO data_points
                   (meme_id, skill, indicador, valor, unidade, fonte, fonte_url,
                    localidade_nome, localidade_nivel, ano_referencia)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (meme_id, dp["skill"], dp["indicador"], str(dp["valor"]),
                 dp.get("unidade"), dp["fonte"], dp.get("fonte_url"),
                 dp["localidade_nome"], dp["localidade_nivel"], dp.get("ano_referencia")),
            )
            row_id = cur.fetchone()["id"]
        self.conn.commit()
        return row_id

    def get_data_points(self, meme_id: str) -> list[dict]:
        with self._cur() as cur:
            cur.execute(
                "SELECT * FROM data_points WHERE meme_id = %s ORDER BY localidade_nivel",
                (meme_id,),
            )
            return _rows(cur)

    # ── Conteúdo gerado ───────────────────────────────────────────────────────

    def insert_conteudo(self, meme_id: str, conteudo: dict) -> int:
        with self._cur() as cur:
            cur.execute(
                "UPDATE conteudo_gerado SET is_current = 0 WHERE meme_id = %s", (meme_id,)
            )
            cur.execute(
                """INSERT INTO conteudo_gerado
                   (meme_id, contexto_oculto, pilula_sabedoria, roteiro_tiktok,
                    modelo_claude, prompt_version, tokens_input, tokens_output, is_current)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1) RETURNING id""",
                (meme_id, conteudo["contexto_oculto"], conteudo["pilula_sabedoria"],
                 conteudo.get("roteiro_tiktok"), conteudo["modelo_claude"],
                 conteudo["prompt_version"], conteudo.get("tokens_input"),
                 conteudo.get("tokens_output")),
            )
            row_id = cur.fetchone()["id"]
        self.conn.commit()
        return row_id

    def get_conteudo_atual(self, meme_id: str) -> dict | None:
        with self._cur() as cur:
            cur.execute(
                "SELECT * FROM conteudo_gerado WHERE meme_id = %s AND is_current = 1",
                (meme_id,),
            )
            return _row(cur)

    # ── Pipeline Queue ────────────────────────────────────────────────────────

    def upsert_queue_item(self, item: dict) -> int:
        h = _hash_meme(item["meme_texto_raw"])
        with self._cur() as cur:
            cur.execute(
                "SELECT id, estado FROM pipeline_queue WHERE meme_hash = %s", (h,)
            )
            existing = _row(cur)
            if existing:
                if existing["estado"] not in ("approved", "archived"):
                    cur.execute(
                        """UPDATE pipeline_queue
                           SET estado = %s, metadados = %s, estado_atualizado_em = NOW()
                           WHERE id = %s""",
                        (item.get("estado", existing["estado"]),
                         json.dumps(item.get("metadados", {}), ensure_ascii=False),
                         existing["id"]),
                    )
                self.conn.commit()
                return existing["id"]

            cur.execute(
                """INSERT INTO pipeline_queue
                   (meme_hash, meme_texto_raw, estado, source_url, source_rss, metadados, max_tentativas)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (h, item["meme_texto_raw"], item.get("estado", "discovered"),
                 item.get("source_url"), item.get("source_rss"),
                 json.dumps(item.get("metadados", {}), ensure_ascii=False),
                 item.get("max_tentativas", 3)),
            )
            row_id = cur.fetchone()["id"]
        self.conn.commit()
        return row_id

    def get_queue_by_estado(self, estado: str, limit: int = 50) -> list[dict]:
        with self._cur() as cur:
            cur.execute(
                """SELECT * FROM pipeline_queue
                   WHERE estado = %s AND tentativas < max_tentativas
                   ORDER BY candidato_criado_em LIMIT %s""",
                (estado, limit),
            )
            result = []
            for r in cur.fetchall():
                d = dict(r)
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
        with self._cur() as cur:
            if novo_estado in ("fact_checking", "enriching", "generating", "reviewing"):
                cur.execute(
                    "UPDATE pipeline_queue SET tentativas = tentativas + 1 WHERE id = %s",
                    (queue_id,),
                )

            extra_sets = ""
            extra_vals: list[Any] = []
            if erro:
                extra_sets += ", erro_ultimo = %s"
                extra_vals.append(erro[:2000])
            if novo_estado in ("approved", "rejected", "archived"):
                extra_sets += ", processado_em = NOW()"
            if metadados is not None:
                extra_sets += ", metadados = %s"
                extra_vals.append(json.dumps(metadados, ensure_ascii=False))

            cur.execute(
                f"""UPDATE pipeline_queue
                    SET estado = %s, estado_atualizado_em = NOW() {extra_sets}
                    WHERE id = %s""",
                [novo_estado] + extra_vals + [queue_id],
            )
        self.conn.commit()

    def link_queue_to_meme(self, queue_id: int, meme_id: str) -> None:
        with self._cur() as cur:
            cur.execute(
                "UPDATE pipeline_queue SET meme_id = %s WHERE id = %s", (meme_id, queue_id)
            )
        self.conn.commit()

    def get_queue_stats(self) -> dict:
        with self._cur() as cur:
            cur.execute(
                "SELECT estado, COUNT(*) as n FROM pipeline_queue GROUP BY estado"
            )
            return {r["estado"]: r["n"] for r in cur.fetchall()}

    # ── Pipeline Runs ─────────────────────────────────────────────────────────

    def start_run(self) -> int:
        with self._cur() as cur:
            cur.execute("INSERT INTO pipeline_runs DEFAULT VALUES RETURNING id")
            row_id = cur.fetchone()["id"]
        self.conn.commit()
        return row_id

    def finish_run(self, run_id: int, stats: dict) -> None:
        with self._cur() as cur:
            cur.execute(
                """UPDATE pipeline_runs
                   SET finalizado_em = NOW(),
                       memes_descobertos = %s,
                       memes_aprovados = %s,
                       memes_rejeitados = %s,
                       erros = %s,
                       status = %s
                   WHERE id = %s""",
                (stats.get("descobertos", 0), stats.get("aprovados", 0),
                 stats.get("rejeitados", 0), stats.get("erros", 0),
                 stats.get("status", "success"), run_id),
            )
        self.conn.commit()

    # ── Import do memes.json ──────────────────────────────────────────────────

    def import_from_json(self, json_path: str) -> int:
        data = json.loads(Path(json_path).read_text())
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
