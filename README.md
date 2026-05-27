# Banco de Memes — Cidadania Conectada: Vozes do Oziel
**Grupo Diálogos / CriaLab / Minha Campinas / FEAC**
Jardim Oziel, Campinas-SP | 2026

---

## O que é isso

Banco de dados de memes políticos categorizados para alimentar:
1. **Cards do jogo** (dilemas de swipe — *Vozes do Oziel*)
2. **Roteiros TikTok** (pílulas de sabedoria, formato Reels 60-90s)

Cada meme tem: verificação de fatos, contexto oculto (para o jogo) e pílula de sabedoria (para o TikTok).

---

## Estrutura

```
ozielmemes/
├── database/
│   └── memes.json           ← banco principal (30 memes)
├── scripts/
│   ├── catalogo.py          ← navegar, buscar, adicionar memes
│   ├── gerar_cards.py       ← exportar para dilemas.ts do jogo
│   └── roteiro_tiktok.py    ← gerar roteiros de vídeo
└── output/
    ├── dilemas/             ← cards prontos para o jogo
    └── tiktok/              ← roteiros de vídeo prontos
```

---

## Status atual

| Total de memes | No jogo | Disponíveis | Com TikTok |
|---------------|---------|-------------|------------|
| 30            | 4       | 26          | 17         |

---

## Como usar

### Ver estatísticas
```bash
python3 scripts/catalogo.py stats
```

### Navegar pelo catálogo (menu interativo)
```bash
python3 scripts/catalogo.py
```

### Buscar por tema
```bash
python3 scripts/catalogo.py buscar "bolsa família"
python3 scripts/catalogo.py buscar "urna"
python3 scripts/catalogo.py buscar "apatia"
```

### Gerar cards para o jogo
```bash
# Ver preview antes de gravar
python3 scripts/gerar_cards.py --preview

# Gerar por módulo
python3 scripts/gerar_cards.py --modulo eleicao

# Gerar cards específicos
python3 scripts/gerar_cards.py --ids m004,m012,m013
```

### Gerar roteiros TikTok
```bash
# Todos os memes com roteiro marcado
python3 scripts/roteiro_tiktok.py

# Um meme específico
python3 scripts/roteiro_tiktok.py --id m002

# Em formato markdown (para o Canva ou Notion)
python3 scripts/roteiro_tiktok.py --formato markdown
```

---

## Categorias

| Categoria | Descrição | Exemplos |
|-----------|-----------|---------|
| `apatia` | Descrença e afastamento da política | "tanto faz votar", "não muda nada" |
| `desinformacao` | Fake news verificáveis com fontes | urna fraudada, vacina com chip |
| `critica_raza` | Críticas que fecham o debate | "todos políticos são iguais", "greve é vagabundagem" |
| `conspiracao` | Teorias sem base factual | Venezuela, globalismo, kit gay |
| `preconceito` | Discriminação como arma política | cotas, LGBTQ+, Bolsa Família = compra de voto |

## Módulos do jogo

| Módulo | Cor |
|--------|-----|
| `eleicao` | Coral |
| `desinformacao` | Verde escuro |
| `participacao` | Âmbar |
| `territorio` | Índigo |

---

## Como adicionar novo meme

Pelo menu interativo:
```bash
python3 scripts/catalogo.py
# Escolha opção 7 — Adicionar novo meme
```

Ou diretamente no JSON (`database/memes.json`), seguindo a estrutura:
```json
{
  "id": "m031",
  "meme": "\"Texto exato do meme viral\"",
  "categoria": "apatia",
  "formato": "texto_viral",
  "origem": "WhatsApp",
  "viralizou": "recorrente",
  "verificacao": {
    "status": "enganoso",
    "fonte": "Agência Lupa",
    "explicacao": "Por que é falso ou enganoso"
  },
  "impacto_real": "O que esse meme faz acontecer na prática",
  "contexto_oculto": "Para o jogo — consequência concreta no território",
  "pilula_sabedoria": "Mensagem final — curta, direta, do jeito do bairro",
  "modulo": "eleicao",
  "dificuldade": 2,
  "usado_no_jogo": false,
  "card_gerado": false,
  "roteiro_tiktok": false,
  "tags": ["tag1", "tag2"]
}
```

---

## Fontes de verificação utilizadas

- **Agência Lupa** — lupa.uol.com.br
- **Aos Fatos** — aosfatos.org
- **G1 Fato ou Fake** — g1.globo.com/fato-ou-fake
- **Agência Pública** — apublica.org
- **Portal da Transparência** — transparencia.gov.br
- **TSE** — tse.jus.br
- **IBGE** — ibge.gov.br
- **Câmara Municipal de Campinas** — campinas.sp.leg.br

---

## Protocolo editorial

Todo meme adicionado ao banco deve ter:
- [ ] Verificação com fonte confiável e identificável
- [ ] Contexto oculto em **linguagem do bairro** (12-17 anos, Oziel)
- [ ] Consequência **concreta e local** sempre que possível (Campinas, Oziel, DIC...)
- [ ] Pílula de sabedoria **sem tom professoral** — direta, sem julgamento
- [ ] Validação com pelo menos um jovem do território antes de entrar no jogo

---

*Projeto financiado pelo Fundo Semente CriaLab — Minha Campinas / FEAC*
