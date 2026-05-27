#!/usr/bin/env python3
"""
OzielMemes Pipeline — Entry Point Autônomo

Uso:
  python run.py                   # executa pipeline completo
  python run.py --dry-run         # descobre candidatos mas não grava
  python run.py --max 5           # processa no máximo 5 itens
  python run.py --from-json       # importa memes.json para o SQLite
  python run.py --status          # mostra estado da fila atual
  python run.py --retry-failed    # retenta itens rejeitados por erro
  python run.py --gerar-cards     # exporta dilemas.ts para o jogo
  python run.py --gerar-tiktok    # gera roteiros TikTok de novos memes

Requer: export GEMINI_API_KEY='AIza...'  (gratuito em aistudio.google.com)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Adiciona raiz ao path para imports
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OzielMemes Pipeline — Cidadania Conectada: Vozes do Oziel"
    )
    parser.add_argument("--dry-run", action="store_true", help="Pesquisa mas não processa")
    parser.add_argument("--max", type=int, default=None, help="Máximo de itens por execução")
    parser.add_argument("--from-json", action="store_true", help="Importa memes.json para SQLite")
    parser.add_argument("--status", action="store_true", help="Mostra estado atual do pipeline")
    parser.add_argument("--retry-failed", action="store_true", help="Retenta itens rejeitados")
    parser.add_argument("--gerar-cards", action="store_true", help="Exporta cards para o jogo")
    parser.add_argument("--gerar-tiktok", action="store_true", help="Gera roteiros TikTok")
    parser.add_argument("--verbose", "-v", action="store_true", help="Log detalhado")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        from config import get_config
        config = get_config()
    except ValueError as exc:
        print(f"❌ Configuração inválida: {exc}", file=sys.stderr)
        return 1

    from database.db import DatabaseManager
    db = DatabaseManager(config.db_path)
    db.init_db()

    # ── Comandos de informação (sem Claude) ───────────────────────────────────

    if args.status:
        return _cmd_status(db)

    if args.from_json:
        return _cmd_import_json(db, config)

    if args.retry_failed:
        return _cmd_retry_failed(db)

    if args.gerar_cards:
        return _cmd_gerar_cards(db, config)

    if args.gerar_tiktok:
        return _cmd_gerar_tiktok(db, config)

    # ── Pipeline principal (requer Gemini API) ────────────────────────────────

    from agents.orchestrator import OrchestratorAgent
    orchestrator = OrchestratorAgent(db=db, config=config, api_key=config.gemini_api_key)

    result = orchestrator.run(max_items=args.max, dry_run=args.dry_run)

    print(f"\n{'='*50}")
    print(f"PIPELINE RUN #{result.run_id}")
    print(f"{'='*50}")
    print(f"  Descobertos: {result.descobertos}")
    print(f"  Aprovados:   {result.aprovados}")
    print(f"  Rejeitados:  {result.rejeitados}")
    print(f"  Erros:       {result.erros}")
    print(f"  Status:      {result.status}")
    if result.detalhes:
        print(f"\nDetalhes:")
        for d in result.detalhes[:10]:
            print(f"  {d}")

    db.close()
    return 0 if result.status != "failed" else 1


def _cmd_status(db: DatabaseManager) -> int:
    stats = db.count_memes()
    fila = db.get_queue_stats()
    print(f"\n{'='*40}")
    print("ESTADO DO PIPELINE")
    print(f"{'='*40}")
    print(f"Memes no banco: {stats.get('total', 0)}")
    print(f"  No jogo:      {stats.get('no_jogo', 0)}")
    print(f"  Com TikTok:   {stats.get('com_tiktok', 0)}")
    print(f"\nFila:")
    for estado, n in sorted(fila.items()):
        print(f"  {estado:<20} {n}")
    db.close()
    return 0


def _cmd_import_json(db: DatabaseManager, config) -> int:
    json_path = config.memes_json_path
    if not Path(json_path).exists():
        print(f"❌ Arquivo não encontrado: {json_path}")
        return 1
    count = db.import_from_json(json_path)
    print(f"✅ {count} memes importados de {json_path}")
    db.close()
    return 0


def _cmd_retry_failed(db: DatabaseManager) -> int:
    # Reseta itens travados (rejected ou discovered com tentativas esgotadas) para retry
    db.conn.execute(
        """UPDATE pipeline_queue
           SET tentativas = 0, erro_ultimo = NULL, estado = 'discovered'
           WHERE estado IN ('rejected', 'discovered')
           AND tentativas >= max_tentativas"""
    )
    db.conn.commit()
    n = db.conn.execute("SELECT changes()").fetchone()[0]
    print(f"✅ {n} itens resetados para retry")
    db.close()
    return 0


def _cmd_gerar_cards(db: DatabaseManager, config) -> int:
    """Exporta memes aprovados para dilemas.ts do jogo."""
    memes = db.list_memes(usado_no_jogo=False)
    # Busca aprovados sem filtrar tentativas (itens que passaram por retry também são válidos)
    aprovados_ids = {
        row[0] for row in db.conn.execute(
            "SELECT meme_id FROM pipeline_queue WHERE estado = 'approved' AND meme_id IS NOT NULL"
        ).fetchall()
    }
    para_exportar = [m for m in memes if m["id"] in aprovados_ids]

    if not para_exportar:
        print("Nenhum meme aprovado novo para exportar.")
        db.close()
        return 0

    print(f"Exportando {len(para_exportar)} meme(s)...")
    db.close()

    from scripts.gerar_cards import main as gerar_main
    import sys
    sys.argv = ["gerar_cards.py"]
    gerar_main()
    return 0


def _cmd_gerar_tiktok(db: DatabaseManager, config) -> int:
    """Gera roteiros TikTok para memes com conteúdo gerado."""
    from scripts.roteiro_tiktok import main as tiktok_main
    import sys
    sys.argv = ["roteiro_tiktok.py"]
    tiktok_main()
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
