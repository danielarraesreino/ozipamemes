#!/usr/bin/env python3
"""
Gerador de Roteiros TikTok — Cidadania Conectada: Vozes do Oziel
Gera pílulas de sabedoria no formato Reels/TikTok para cada meme.

Formato de cada vídeo (60-90s):
  CENA 1 (0-4s):   O meme aparece — texto na tela, alarme visual
  CENA 2 (4-8s):   "Mas o que isso ESCONDE?" — pausa dramática
  CENA 3 (8-45s):  Contexto oculto revelado — narração direta
  CENA 4 (45-60s): A pílula de sabedoria — mensagem final
  CENA 5 (60-70s): CTA — "Compartilha pra quem precisa ver isso"

Uso:
  python3 roteiro_tiktok.py                   → gera todos com roteiro_tiktok=True
  python3 roteiro_tiktok.py --id m002         → roteiro de um meme específico
  python3 roteiro_tiktok.py --todos           → gera todos os memes
  python3 roteiro_tiktok.py --formato markdown → saída em markdown
"""

import json
import sys
import os
import argparse

DB_PATH = os.path.join(os.path.dirname(__file__), "../database/memes.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../output/tiktok")

EMOJIS_CATEGORIA = {
    "apatia": "😶",
    "desinformacao": "⚠️",
    "critica_raza": "🤔",
    "conspiracao": "🕵️",
    "preconceito": "✊"
}

HASHTAGS_FIXAS = "#VozesDoOziel #CidadaniaConectada #PílulaDeSabedoria #JardimOziel #Campinas #PolíticaNaVeia #JovemQueParticipa"

HASHTAGS_CATEGORIA = {
    "apatia": "#VotoImporta #SuaVozImporta #ParticipacaoPopular",
    "desinformacao": "#FakeNews #FactCheck #Desinformação #Verifica",
    "critica_raza": "#PensaCritico #Democracia #DireitosSociais",
    "conspiracao": "#Checagem #Realidade #FakeNews",
    "preconceito": "#DireitosHumanos #Igualdade #Dignidade"
}

TRILHA_SUGERIDA = {
    "apatia": "Beat urbano leve — não agressivo, pensativo",
    "desinformacao": "Som de alerta / notificação distorcida → vira algo calmo",
    "critica_raza": "Beat de pensamento — algo que convida reflexão",
    "conspiracao": "Suspense leve → resolução clara",
    "preconceito": "Instrumental emotivo mas não sentimental — direto"
}


def carregar():
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def gerar_roteiro(m, formato="texto"):
    emoji = EMOJIS_CATEGORIA.get(m["categoria"], "💡")
    hashtags = f"{HASHTAGS_FIXAS} {HASHTAGS_CATEGORIA.get(m['categoria'], '')}"
    trilha = TRILHA_SUGERIDA.get(m["categoria"], "Beat urbano")

    # Formata o meme sem aspas externas para o visual do TikTok
    meme_limpo = m["meme"].strip('"').strip("'")

    linhas = []

    if formato == "markdown":
        linhas = [
            f"# Roteiro TikTok — {m['id']}",
            f"**Categoria:** {m['categoria']} {emoji}",
            f"**Módulo:** {m['modulo']}",
            f"**Verificação:** {m['verificacao']['status'].upper()} — {m['verificacao']['fonte']}",
            "",
            "---",
            "",
            "## DADOS DE PRODUÇÃO",
            f"- **Duração estimada:** 60-75 segundos",
            f"- **Trilha sugerida:** {trilha}",
            f"- **Formato:** Vertical 9:16 (TikTok/Reels)",
            f"- **Hashtags:**",
            f"  `{hashtags}`",
            "",
            "---",
            "",
            "## ROTEIRO CENA A CENA",
            "",
            "### CENA 1 — O MEME (0 a 4s)",
            "**Visual:** Fundo escuro. Texto grande centralizado aparece letra por letra.",
            f"**Texto na tela:**",
            f'> "{meme_limpo}"',
            "**Áudio:** Silêncio ou beat muito baixo. Som de digitação ou notificação.",
            "**Narração:** *(sem fala — deixa o meme falar)*",
            "",
            "### CENA 2 — A PERGUNTA (4 a 8s)",
            "**Visual:** Corte rápido. Fundo muda. Texto aparece com destaque.",
            "**Texto na tela:** MAS O QUE ISSO ESCONDE?",
            "**Áudio:** Som de alerta — depois silêncio dramático de 1 segundo.",
            "**Narração:** *(pausa)*",
            "",
            "### CENA 3 — O CONTEXTO REAL (8 a 50s)",
            "**Visual:** Câmera no narrador ou texto animado. Linguagem direta, sem academia.",
            "**Narração (adaptar para linguagem do bairro):**",
            f"> {m['contexto_oculto']}",
            "",
            f"**Dado de verificação (aparece na tela):** {m['verificacao']['fonte']}",
            f"**Explicação rápida:** {m['verificacao']['explicacao'][:150]}...",
            "",
            "### CENA 4 — A PÍLULA (50 a 65s)",
            "**Visual:** Destaque total. Texto grande. Fundo muda de cor.",
            "**Texto na tela:** 💊 PÍLULA DE SABEDORIA",
            f"**Narração:**",
            f"> {m['pilula_sabedoria']}",
            "",
            "### CENA 5 — CTA (65 a 75s)",
            "**Visual:** Logo do projeto. Chamada final.",
            "**Narração:** \"Compartilha isso com quem precisa ver. Política é do dia a dia — do seu bairro, da sua escola, do seu futuro.\"",
            "**Texto na tela:** Vozes do Oziel — Grupo Diálogos / CriaLab / FEAC",
            "",
            "---",
            "",
            "## CHECKLIST DE PRODUÇÃO",
            "- [ ] Roteiro revisado com linguagem do bairro",
            "- [ ] Validado com jovens do Oziel antes de gravar",
            "- [ ] Fonte de verificação conferida e atualizada",
            "- [ ] Narrador/narradora do próprio território (se possível)",
            "- [ ] Closed caption adicionado",
            "- [ ] Hashtags inseridas",
            "",
            f"**Impacto real para adicionar à narração:**",
            f"> {m['impacto_real']}",
        ]
    else:
        # Formato texto simples
        separador = "─" * 60
        linhas = [
            separador,
            f"ROTEIRO TIKTOK — {m['id']} | {m['categoria'].upper()} {emoji}",
            f"Módulo: {m['modulo']} | Verificação: {m['verificacao']['status'].upper()}",
            separador,
            "",
            "DADOS DE PRODUÇÃO:",
            f"  Duração: 60-75 segundos",
            f"  Trilha sugerida: {trilha}",
            f"  Formato: Vertical 9:16",
            "",
            "CENA 1 — O MEME (0 a 4s)",
            f"  TELA: \"{meme_limpo}\"",
            "  ÁUDIO: Silêncio / som de notificação",
            "  SEM NARRAÇÃO",
            "",
            "CENA 2 — A PERGUNTA (4 a 8s)",
            "  TELA: MAS O QUE ISSO ESCONDE?",
            "  ÁUDIO: Som de alerta → 1s de silêncio",
            "",
            "CENA 3 — CONTEXTO REAL (8 a 50s)",
            "  NARRAÇÃO:",
            "",
        ]
        # Quebra o contexto em linhas curtas para facilitar leitura no set
        contexto = m["contexto_oculto"]
        palavras = contexto.split()
        linha_atual = "  "
        for palavra in palavras:
            if len(linha_atual) + len(palavra) > 70:
                linhas.append(linha_atual)
                linha_atual = "  " + palavra + " "
            else:
                linha_atual += palavra + " "
        if linha_atual.strip():
            linhas.append(linha_atual)

        linhas += [
            "",
            f"  FONTE NA TELA: {m['verificacao']['fonte']}",
            "",
            "CENA 4 — PÍLULA DE SABEDORIA (50 a 65s)",
            "  TELA: 💊 PÍLULA DE SABEDORIA",
            "  NARRAÇÃO:",
            f"  \"{m['pilula_sabedoria']}\"",
            "",
            "CENA 5 — CTA (65 a 75s)",
            "  NARRAÇÃO: \"Compartilha com quem precisa ver. Política é do seu bairro.\"",
            "  TELA: Vozes do Oziel — Grupo Diálogos / CriaLab / FEAC",
            "",
            "HASHTAGS:",
            f"  {hashtags}",
            separador
        ]

    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description="Gera roteiros TikTok a partir do banco de memes")
    parser.add_argument("--id", help="ID de um meme específico (ex: m002)")
    parser.add_argument("--todos", action="store_true", help="Gerar roteiros para todos os memes")
    parser.add_argument("--formato", choices=["texto", "markdown"], default="texto", help="Formato de saída")
    parser.add_argument("--preview", action="store_true", help="Só exibe, não grava")
    args = parser.parse_args()

    db = carregar()
    memes = db["memes"]

    if args.id:
        selecionados = [m for m in memes if m["id"] == args.id]
        if not selecionados:
            print(f"Meme {args.id} não encontrado.")
            sys.exit(1)
    elif args.todos:
        selecionados = memes
    else:
        selecionados = [m for m in memes if m.get("roteiro_tiktok")]

    print(f"\n🎬 Gerando {len(selecionados)} roteiro(s) TikTok...\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for m in selecionados:
        roteiro = gerar_roteiro(m, formato=args.formato)

        if args.preview:
            print(roteiro)
            print()
            continue

        # Salva arquivo individual
        ext = "md" if args.formato == "markdown" else "txt"
        nome = f"roteiro_{m['id']}_{m['categoria']}.{ext}"
        caminho = os.path.join(OUTPUT_DIR, nome)

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(roteiro)

        print(f"✅ {nome}")

    if not args.preview:
        print(f"\n📁 Roteiros salvos em: {OUTPUT_DIR}")
        print(f"\n📋 Próximos passos:")
        print(f"  1. Revise a linguagem com jovens do Oziel — deve soar natural, não acadêmico")
        print(f"  2. Escolha narradoras/narradores do próprio território")
        print(f"  3. Grave cena por cena seguindo o script")
        print(f"  4. Adicione closed caption antes de publicar")
        print(f"  5. Use as hashtags sugeridas em cada roteiro")


if __name__ == "__main__":
    main()
