#!/usr/bin/env python3
"""
Gerador de Cards — Cidadania Conectada: Vozes do Oziel
Converte memes do banco de dados para o formato dilemas.ts do jogo.

Uso:
  python3 gerar_cards.py                    → gera todos disponíveis
  python3 gerar_cards.py --modulo eleicao   → apenas um módulo
  python3 gerar_cards.py --ids m004,m005    → memes específicos
  python3 gerar_cards.py --preview          → só mostra, não grava
"""

import json
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skills.video_fetcher import web_url_for

DB_PATH = os.path.join(os.path.dirname(__file__), "../database/memes.json")
OUTPUT_TS = os.path.join(os.path.dirname(__file__), "../output/dilemas/dilemas_gerados.ts")
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), "../output/dilemas/dilemas_gerados.json")

JOGO_PATH = "/home/dan/Área de Trabalho/jogo_ozipa/src/lib/dilemas.ts"


def carregar():
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def meme_para_dilema(m, idx):
    return {
        "id": f"d{idx:02d}",
        "modulo": m["modulo"],
        "meme": m["meme"],
        "contexto_oculto": m["contexto_oculto"],
        "pilula_sabedoria": m.get("pilula_sabedoria", ""),
        "fonte": m["verificacao"]["fonte"],
        "verificacao_status": m["verificacao"]["status"],
        "dificuldade": m.get("dificuldade", 2),
        "impacto_real": m.get("impacto_real", ""),
        # video_url explícito do meme tem prioridade; senão usa o banco de vídeos local.
        "video_url": m.get("video_url") or web_url_for(m["id"]),
    }


def gerar_typescript(dilemas):
    linhas = [
        "// GERADO AUTOMATICAMENTE por gerar_cards.py",
        "// Fonte: banco de memes ozielmemes/database/memes.json",
        "// Grupo Diálogos / CriaLab / FEAC — Cidadania Conectada: Vozes do Oziel",
        "",
        "export interface Dilema {",
        "  id: string",
        "  modulo: string",
        "  meme: string",
        "  contexto_oculto: string",
        "  pilula_sabedoria: string",
        "  fonte: string",
        "  verificacao_status: string",
        "  dificuldade: number",
        "  impacto_real?: string",
        "  video_url?: string",
        "}",
        "",
        "export const dilemas: Dilema[] = ["
    ]

    for d in dilemas:
        linhas.append("  {")
        linhas.append(f'    id: "{d["id"]}",')
        linhas.append(f'    modulo: "{d["modulo"]}",')
        linhas.append(f'    meme: {json.dumps(d["meme"], ensure_ascii=False)},')
        linhas.append(f'    contexto_oculto:')
        linhas.append(f'      {json.dumps(d["contexto_oculto"], ensure_ascii=False)},')
        linhas.append(f'    pilula_sabedoria:')
        linhas.append(f'      {json.dumps(d["pilula_sabedoria"], ensure_ascii=False)},')
        linhas.append(f'    fonte: {json.dumps(d["fonte"], ensure_ascii=False)},')
        linhas.append(f'    verificacao_status: "{d["verificacao_status"]}",')
        linhas.append(f'    dificuldade: {d["dificuldade"]},')
        if d.get("impacto_real"):
            linhas.append(f'    impacto_real: {json.dumps(d["impacto_real"], ensure_ascii=False)},')
        if d.get("video_url"):
            linhas.append(f'    video_url: {json.dumps(d["video_url"], ensure_ascii=False)},')
        linhas.append("  },")

    linhas.append("]")
    return "\n".join(linhas)


def main():
    parser = argparse.ArgumentParser(description="Gera dilemas para o jogo a partir do banco de memes")
    parser.add_argument("--modulo", help="Filtrar por módulo (eleicao, desinformacao, participacao, territorio)")
    parser.add_argument("--ids", help="IDs específicos separados por vírgula (ex: m004,m012)")
    parser.add_argument("--preview", action="store_true", help="Apenas exibe, não grava")
    parser.add_argument("--copiar-para-jogo", action="store_true", help="Copia o arquivo para o projeto do jogo")
    args = parser.parse_args()

    db = carregar()
    memes = db["memes"]

    # Filtros
    if args.ids:
        ids_filtro = [i.strip() for i in args.ids.split(",")]
        selecionados = [m for m in memes if m["id"] in ids_filtro]
    elif args.modulo:
        selecionados = [m for m in memes if m["modulo"] == args.modulo and not m.get("usado_no_jogo")]
    else:
        selecionados = [m for m in memes if not m.get("usado_no_jogo")]

    if not selecionados:
        print("Nenhum meme encontrado com os filtros especificados.")
        sys.exit(1)

    # Converte para formato dilema
    # Começa a partir do índice 5 (os 4 primeiros já estão hardcoded no jogo)
    dilemas = [meme_para_dilema(m, i + 5) for i, m in enumerate(selecionados)]

    print(f"\n{'='*50}")
    print(f"CARDS GERADOS: {len(dilemas)}")
    print(f"{'='*50}")
    for d in dilemas:
        print(f"\n[{d['id']}] módulo: {d['modulo']}")
        print(f"MEME: {d['meme'][:80]}...")
        print(f"CONTEXTO: {d['contexto_oculto'][:80]}...")

    ts_content = gerar_typescript(dilemas)

    if args.preview:
        print(f"\n{'='*50}")
        print("PREVIEW TypeScript:")
        print(f"{'='*50}")
        print(ts_content)
        return

    # Garante diretório de output
    os.makedirs(os.path.dirname(OUTPUT_TS), exist_ok=True)

    # Grava TS
    with open(OUTPUT_TS, "w", encoding="utf-8") as f:
        f.write(ts_content)
    print(f"\n✅ TypeScript gravado em: {OUTPUT_TS}")

    # Grava JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"dilemas": dilemas}, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON gravado em: {OUTPUT_JSON}")

    # Opcionalmente copia para o jogo
    if args.copiar_para_jogo:
        # Lê o dilemas.ts original do jogo para manter os dilemas hardcoded
        try:
            with open(JOGO_PATH, encoding="utf-8") as f:
                original = f.read()
            # Extrai dilemas já existentes no jogo
            print(f"\n⚠️  ATENÇÃO: Esta operação vai MESCLAR os novos cards com o dilemas.ts do jogo.")
            print(f"Arquivo alvo: {JOGO_PATH}")
            confirma = input("Confirmar? (s/n): ").strip().lower()
            if confirma == "s":
                # Estratégia: gera um arquivo completo com todos os dilemas
                # (os 4 originais + os novos)
                with open(JOGO_PATH, "w", encoding="utf-8") as f:
                    f.write(ts_content)
                print(f"✅ Copiado para: {JOGO_PATH}")
                print("⚠️  Verifique se os IDs não conflitam com os dilemas existentes no jogo!")
            else:
                print("Cancelado.")
        except FileNotFoundError:
            print(f"❌ Arquivo do jogo não encontrado: {JOGO_PATH}")

    print(f"\n📋 Próximos passos:")
    print(f"  1. Revise os cards em: {OUTPUT_TS}")
    print(f"  2. Valide o contexto_oculto com o grupo (linguagem do bairro)")
    print(f"  3. Copie para o jogo com: python3 gerar_cards.py --copiar-para-jogo")


if __name__ == "__main__":
    main()
