# OzielMemes Pipeline — Plano de Implementação

**Projeto:** Cidadania Conectada: Vozes do Oziel
**Público:** Adolescentes 12-17 anos, Jardim Oziel, Campinas-SP
**Objetivo:** Pipeline autônomo que pesquisa, verifica, enriquece e gera conteúdo editorial
para o serious game e TikToks de cidadania.

---

## Arquitetura

```
RSS Fact-checkers          Dados Abertos
(Lupa, AosFatos…)          (IBGE, TSE, SSP…)
        │                        │
        ▼                        ▼
  ResearchAgent          Skills (DataEnricher)
        │                        │
        ▼                        ▼
  FactCheckAgent ──────► ContentGenerator ──► QualityReviewer
                                                    │
                              SQLite ◄─────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
              dilemas.ts             roteiros TikTok
           (jogo Next.js)
```

### Estado da fila (SQLite — atômico)

```
discovered → fact_checking → enriching → generating → reviewing → approved | rejected
```

Falhas incrementam `tentativas`. Execuções retomam de onde pararam.

---

## Fases de Implementação

### Fase 1 — Base de dados curada ✅
- `database/memes.json` — 30 memes em 5 categorias, 4 módulos
- `database/schema.sql` — schema SQLite completo
- `database/db.py` — DatabaseManager com todas as operações

### Fase 2 — Scripts utilitários ✅
- `scripts/catalogo.py` — catálogo interativo CLI
- `scripts/gerar_cards.py` — exporta para `dilemas.ts` (Next.js)
- `scripts/roteiro_tiktok.py` — gera roteiros de 5 cenas, 60-75s

### Fase 3 — Golden Rules + Skills ✅
- `golden_rules.py` — 8 regras editoriais determinísticas (sem Claude)
  - R1: dado verificável ou personagem concreto
  - R2: sem jargão acadêmico
  - R3: sem viés de partido
  - R4: ancoragem local (Campinas/Oziel)
  - R5: empoderamento, sem sermão
  - R6: evidência de viralização
  - R7: formato correto (≤3 frases + personagem)
  - R8: números com fonte verificável
- `skills/` — 6 skills com fallback compilado:
  - `ibge_api.py` — SIDRA API (população, renda)
  - `tse_data.py` — dados eleitorais Campinas 2024
  - `seade_api.py` — desemprego, renda RM Campinas
  - `ssp_violencia.py` — homicídios Campinas 2024
  - `transparencia_federal.py` — Bolsa Família Campinas
  - `rss_factcheck.py` — classificador two-gate + parsing RSS

### Fase 4 — Agentes ✅
- `agents/base_agent.py` — retry/backoff, `_call_claude()`
- `agents/researcher.py` — RSS paralelo, deduplicação MD5
- `agents/enricher.py` — resolve tags→skills, ordena por localidade_nivel
- `agents/reviewer.py` — delega para golden_rules, salva histórico no DB
- `agents/fact_checker.py` — extrai status; Claude apenas para normalizar HTML
- `agents/generator.py` — protocolo anti-alucinação com `<dados_verificados>` fechado

### Fase 5 — Orquestração + Testes ✅
- `agents/orchestrator.py` — pipeline completo, suporte a regeneração com feedback
- `run.py` — entry point com argparse (8 comandos)
- `tests/` — 111 testes, 100% passando

---

## Protocolo Anti-Alucinação

1. DataEnricher coleta DataPoints reais de APIs abertas
2. ContentGenerator encapsula todos os números em `<dados_verificados>`
3. Prompt instrui Claude: "Use SOMENTE dados do bloco acima. Nunca invente números."
4. QualityReviewer (R8) verifica que todos os números no texto gerado têm DataPoint correspondente
5. Se R8 falha → rejeição + feedback → regeneração (até 2 tentativas)

---

## Execução

```bash
# Setup
pip install -r requirements.txt
export ANTHROPIC_API_KEY='sk-ant-...'

# Importa base curada
python run.py --from-json

# Pipeline completo
python run.py

# Pesquisa sem processar
python run.py --dry-run

# Estado atual
python run.py --status

# Exporta cards para o jogo
python run.py --gerar-cards

# Gera roteiros TikTok
python run.py --gerar-tiktok

# Testes
pytest tests/ -v
```

---

## Fontes de Dados Abertos

| Skill | Fonte | Endpoint |
|-------|-------|----------|
| IBGESkill | IBGE SIDRA | `https://servicodados.ibge.gov.br/api/v3/agregados/` |
| TSESkill | TSE Dados Abertos | `https://cdn.tse.jus.br/estatistica/sead/odsele/` |
| SEADESkill | SEADE CKAN | `https://repositorio.seade.gov.br/api/3/` |
| SSPViolenciaSkill | SSP-SP | `https://www.ssp.sp.gov.br/estatistica/` |
| TransparenciaFederal | Portal Transparência | `https://api.portaldatransparencia.gov.br/api-de-dados/` |
| RSSFactCheckSkill | Lupa, AosFatos, Boatos, E-Farsas | RSS feeds |

Todas as skills têm dados compilados como fallback — o pipeline funciona offline.

---

## Testes: cobertura por módulo

| Módulo | Testes | Status |
|--------|--------|--------|
| golden_rules | 50 | ✅ |
| skills | 36 | ✅ |
| agents | 25 | ✅ |
| **Total** | **111** | **✅** |
