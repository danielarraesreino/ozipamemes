# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**OzielMemes Pipeline** ("Cidadania Conectada: Vozes do Oziel") is an autonomous editorial pipeline that discovers, fact-checks, enriches, generates, and reviews political-meme content for two outputs: swipe-dilemma cards for a serious game (`dilemas.ts`, Next.js) and TikTok scripts. Target audience is teens (12–17) in Jardim Oziel, Campinas-SP. **The codebase and all content are in Brazilian Portuguese** — match that language in code comments, content, and user-facing strings.

## Commands

```bash
pip install -r requirements.txt
export GEMINI_API_KEY='AIza...'    # required for the LLM pipeline; free at aistudio.google.com

# Pipeline (run.py is the CLI entry point)
python run.py                 # full pipeline run (requires GEMINI_API_KEY)
python run.py --dry-run       # discover candidates only, no DB writes / no LLM
python run.py --from-json     # import database/memes.json into the DB
python run.py --status        # show queue + meme counts (no LLM)
python run.py --retry-failed  # reset rejected/errored items for retry
python run.py --gerar-cards   # export approved memes to the game's dilemas.ts
python run.py --gerar-tiktok  # generate TikTok scripts
python run.py --max 5         # cap items processed this run

# Dashboard (Streamlit UI; shells out to run.py via subprocess)
streamlit run app.py

# Tests (no pytest config file — pass paths explicitly)
pytest tests/ -v
pytest tests/test_golden_rules.py -v          # single file
pytest tests/test_agents.py::test_name -v     # single test
```

There is no lint/format tooling configured.

## Critical naming gotcha

Despite the project name and identifiers, **the LLM is Google Gemini, not Claude.** `BaseAgent._call_claude()`, `Config.claude_model`, and similar names are legacy aliases kept for internal compatibility — they all call the Gemini API (`google.genai`). The env var is `GEMINI_API_KEY`. Don't "fix" these names assuming Anthropic.

## Architecture

The pipeline is a **persistent state machine**. Each candidate moves through DB-backed states, one atomic transition at a time, so runs resume where they left off:

```
discovered → fact_checking → enriching → generating → reviewing → approved | rejected
```

`OrchestratorAgent` (`agents/orchestrator.py`) drives this. `run.py` builds it; `_processar_item()` walks one item through every stage. On error, an item is returned to `discovered` and its `tentativas` counter increments. Rejected items can be regenerated once with reviewer feedback before final rejection.

**Agents** (`agents/`), each a `BaseAgent` subclass:
- `researcher.py` — pulls RSS fact-check feeds (Lupa, Aos Fatos, Boatos, E-Farsas) in parallel, dedups by MD5. The only stage that needs no LLM.
- `fact_checker.py` — extracts verification status; uses Gemini only to normalize HTML.
- `enricher.py` (`DataEnricher`) — maps meme tags → skills via `Config.tag_to_skills`, collects real `DataPoint`s, orders by `localidade_nivel` (most local first).
- `generator.py` (`ContentGenerator`) — generates `contexto_oculto` (game) and `pilula_sabedoria` (TikTok).
- `reviewer.py` (`QualityReviewer`) — delegates to `golden_rules.py`, persists review history.

**Anti-hallucination protocol** — the core editorial guarantee. Enricher gathers verified numbers as `DataPoint`s; the generator wraps them in a closed `<dados_verificados>` block and instructs Gemini to use only those numbers; reviewer rule **R8** rejects any number in generated text that lacks a matching `DataPoint`. Failure → feedback → regeneration (max 2 attempts). When touching generation or review, preserve this loop.

**Golden Rules** (`golden_rules.py`) — 8 pure, deterministic editorial rules (no LLM), e.g. no academic jargon, no party bias, local anchoring (Campinas/Oziel), ≤3 sentences, numbers must have a verifiable source. These are heavily unit-tested; changing a rule means updating `tests/test_golden_rules.py`.

**Skills** (`skills/`) — open-data fetchers (IBGE/SIDRA, TSE, SEADE, SSP, Portal da Transparência) plus `rss_factcheck.py`. All subclass `base_skill.py` and return `list[DataPoint]` with traceable sources. **Every skill has compiled offline fallback data, so the whole pipeline runs without network.** `cache.py` provides TTL caching under `data/`.

**Database** — `database/factory.get_db()` picks the backend by environment, all three exposing the same `DatabaseManager` interface:
1. `SUPABASE_URL` set → `db_supabase.py` (supabase-py over HTTPS)
2. `DATABASE_URL` set → `db_postgres.py` (psycopg2)
3. neither → `db.py` (local SQLite at `database/oziel_pipeline.db`)

When adding a DB operation, **implement it in all three backends** — recent commit history shows divergence between them is a recurring bug source. Never reach into `db.conn` directly from outside the manager; add a method instead. Schemas: `database/schema.sql` (SQLite), `database/schema_postgres.sql`. A Supabase MCP server is configured in `.mcp.json`.

**Output** lands in `output/dilemas/` (game cards) and `output/tiktok/` (scripts). The export scripts in `scripts/` (`gerar_cards.py`, `roteiro_tiktok.py`, `catalogo.py`) are standalone CLIs that `run.py` also invokes.

## Config

`config.py` builds a singleton `Config` via `get_config()`. It auto-loads `.env` and Streamlit Cloud secrets. `Config.__post_init__` raises `ValueError` if `GEMINI_API_KEY` is missing, and seeds defaults for `rss_sources` and `tag_to_skills`. Tests inject a fake key via the `fake_api_key` autouse fixture in `tests/conftest.py`.

## Editorial protocol (from README)

Content quality is the product. Every meme added to the bank must have: a verification with an identifiable trusted source; `contexto_oculto` in neighborhood language (teens, Oziel); a concrete, local consequence (Campinas/Oziel/DIC) where possible; a `pilula_sabedoria` that is direct and non-preachy. The meme schema (id, categoria, verificacao, contexto_oculto, pilula_sabedoria, modulo, etc.) is documented in `README.md`.
