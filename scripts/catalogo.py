#!/usr/bin/env python3
"""
Catálogo de Memes — Cidadania Conectada: Vozes do Oziel
Grupo Diálogos / CriaLab / FEAC
Navega, filtra, busca e adiciona memes ao banco de dados.
"""

import json
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "../database/memes.json")


def carregar():
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def salvar(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def listar(memes, filtro_categoria=None, filtro_modulo=None, apenas_nao_usados=False):
    resultado = memes
    if filtro_categoria:
        resultado = [m for m in resultado if m["categoria"] == filtro_categoria]
    if filtro_modulo:
        resultado = [m for m in resultado if m["modulo"] == filtro_modulo]
    if apenas_nao_usados:
        resultado = [m for m in resultado if not m.get("usado_no_jogo")]
    return resultado


def imprimir_meme(m, verbose=False):
    status_jogo = "✅ no jogo" if m.get("usado_no_jogo") else "⬜ disponível"
    status_tiktok = "🎬 TikTok pronto" if m.get("roteiro_tiktok") else ""
    print(f"\n{'─'*60}")
    print(f"[{m['id']}] {m['categoria'].upper()} | módulo: {m['modulo']} | {status_jogo} {status_tiktok}")
    print(f"MEME: {m['meme']}")
    if verbose:
        print(f"\nVERIFICAÇÃO: {m['verificacao']['status'].upper()}")
        print(f"Fonte: {m['verificacao']['fonte']}")
        print(f"Explicação: {m['verificacao']['explicacao']}")
        print(f"\nCONTEXTO OCULTO (para o jogo):")
        print(f"  {m['contexto_oculto']}")
        print(f"\nPÍLULA DE SABEDORIA (TikTok):")
        print(f"  {m['pilula_sabedoria']}")
        print(f"\nTags: {', '.join(m['tags'])}")


def buscar(memes, termo):
    termo = termo.lower()
    return [
        m for m in memes
        if termo in m["meme"].lower()
        or termo in m.get("contexto_oculto", "").lower()
        or any(termo in t for t in m["tags"])
        or termo in m["categoria"]
        or termo in m["modulo"]
    ]


def proximo_id(memes):
    ids = [int(m["id"][1:]) for m in memes if m["id"].startswith("m")]
    return f"m{max(ids) + 1:03d}" if ids else "m001"


def adicionar_meme(db):
    memes = db["memes"]
    print("\n=== ADICIONAR NOVO MEME ===")
    print("(Pressione Ctrl+C para cancelar)\n")

    novo = {
        "id": proximo_id(memes),
        "meme": input("MEME (texto viral exato): ").strip(),
        "categoria": "",
        "formato": "texto_viral",
        "origem": input("Origem (WhatsApp, TikTok, etc): ").strip() or "WhatsApp",
        "viralizou": input("Quando viralizou? (ex: 2024, recorrente): ").strip() or "recorrente",
        "verificacao": {
            "status": "",
            "fonte": input("Fonte de verificação: ").strip(),
            "explicacao": input("Explicação (por que é enganoso/falso): ").strip()
        },
        "impacto_real": input("Impacto real (o que esse meme faz acontecer): ").strip(),
        "contexto_oculto": input("Contexto oculto (para o jogo — consequência real): ").strip(),
        "pilula_sabedoria": input("Pílula de sabedoria (para TikTok — mensagem final): ").strip(),
        "modulo": "",
        "dificuldade": 2,
        "usado_no_jogo": False,
        "card_gerado": False,
        "roteiro_tiktok": False,
        "tags": []
    }

    print("\nCATEGORIAS: apatia | desinformacao | critica_raza | conspiracao | preconceito")
    novo["categoria"] = input("Categoria: ").strip()

    print("MÓDULOS: eleicao | desinformacao | participacao | territorio")
    novo["modulo"] = input("Módulo: ").strip()

    print("STATUS verificação: falso | enganoso | contexto_ausente | verdadeiro")
    novo["verificacao"]["status"] = input("Status: ").strip()

    dif = input("Dificuldade (1=fácil, 2=médio, 3=difícil) [2]: ").strip()
    novo["dificuldade"] = int(dif) if dif else 2

    tags_raw = input("Tags (separadas por vírgula): ").strip()
    novo["tags"] = [t.strip() for t in tags_raw.split(",") if t.strip()]

    tiktok = input("Tem roteiro TikTok? (s/n) [n]: ").strip().lower()
    novo["roteiro_tiktok"] = tiktok == "s"

    memes.append(novo)
    salvar(db)
    print(f"\n✅ Meme {novo['id']} adicionado com sucesso!")
    return novo


def estatisticas(memes):
    total = len(memes)
    no_jogo = sum(1 for m in memes if m.get("usado_no_jogo"))
    disponiveis = total - no_jogo
    com_tiktok = sum(1 for m in memes if m.get("roteiro_tiktok"))

    cats = {}
    for m in memes:
        cats[m["categoria"]] = cats.get(m["categoria"], 0) + 1

    modulos = {}
    for m in memes:
        modulos[m["modulo"]] = modulos.get(m["modulo"], 0) + 1

    print(f"\n{'='*40}")
    print(f"BANCO DE MEMES — ESTATÍSTICAS")
    print(f"{'='*40}")
    print(f"Total de memes:     {total}")
    print(f"No jogo:            {no_jogo}")
    print(f"Disponíveis:        {disponiveis}")
    print(f"Com roteiro TikTok: {com_tiktok}")
    print(f"\nPor categoria:")
    for cat, n in sorted(cats.items()):
        print(f"  {cat:<20} {n}")
    print(f"\nPor módulo:")
    for mod, n in sorted(modulos.items()):
        print(f"  {mod:<20} {n}")


def menu_principal():
    db = carregar()
    memes = db["memes"]

    while True:
        print(f"\n{'='*40}")
        print(f"CATÁLOGO DE MEMES — VOZES DO OZIEL")
        print(f"{'='*40}")
        print(f"  1. Listar todos os memes")
        print(f"  2. Listar por categoria")
        print(f"  3. Listar por módulo")
        print(f"  4. Listar apenas disponíveis (não no jogo)")
        print(f"  5. Buscar por termo")
        print(f"  6. Ver meme completo")
        print(f"  7. Adicionar novo meme")
        print(f"  8. Estatísticas")
        print(f"  0. Sair")

        op = input("\nEscolha: ").strip()

        if op == "0":
            break

        elif op == "1":
            for m in memes:
                imprimir_meme(m)

        elif op == "2":
            print("Categorias: apatia | desinformacao | critica_raza | conspiracao | preconceito")
            cat = input("Categoria: ").strip()
            for m in listar(memes, filtro_categoria=cat):
                imprimir_meme(m)

        elif op == "3":
            print("Módulos: eleicao | desinformacao | participacao | territorio")
            mod = input("Módulo: ").strip()
            for m in listar(memes, filtro_modulo=mod):
                imprimir_meme(m)

        elif op == "4":
            for m in listar(memes, apenas_nao_usados=True):
                imprimir_meme(m)

        elif op == "5":
            termo = input("Buscar: ").strip()
            resultados = buscar(memes, termo)
            print(f"\n{len(resultados)} resultado(s):")
            for m in resultados:
                imprimir_meme(m)

        elif op == "6":
            mid = input("ID do meme (ex: m001): ").strip()
            encontrado = next((m for m in memes if m["id"] == mid), None)
            if encontrado:
                imprimir_meme(encontrado, verbose=True)
            else:
                print("Meme não encontrado.")

        elif op == "7":
            adicionar_meme(db)
            memes = db["memes"]

        elif op == "8":
            estatisticas(memes)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        db = carregar()
        memes = db["memes"]
        if cmd == "stats":
            estatisticas(memes)
        elif cmd == "listar":
            cat = sys.argv[2] if len(sys.argv) > 2 else None
            for m in listar(memes, filtro_categoria=cat):
                imprimir_meme(m, verbose=True)
        elif cmd == "buscar":
            termo = " ".join(sys.argv[2:])
            for m in buscar(memes, termo):
                imprimir_meme(m, verbose=True)
    else:
        menu_principal()
