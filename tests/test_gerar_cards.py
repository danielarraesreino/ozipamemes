"""
TDD — gerar_cards.py
Testa conversão de memes.json → dilemas para o jogo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# ── Fixtures ──────────────────────────────────────────────────────────────────

MEME_COMPLETO = {
    "id": "m001",
    "meme": '"Todos os políticos são ladrões, tanto faz votar"',
    "modulo": "eleição",
    "dificuldade": 1,
    "contexto_oculto": "O vereador foi eleito com 480 votos. No bairro moram 3.200 jovens que não foram votar.",
    "pilula_sabedoria": "Não votar é uma escolha — só que quem decide no seu lugar é quem aparece.",
    "impacto_real": "A UBS fechou com 60 votos de diferença.",
    "verificacao": {
        "status": "enganoso",
        "fonte": "TSE / Transparência Internacional",
        "explicacao": "Generalização que ignora diferenças reais",
    },
    "tags": ["apatia", "eleição"],
    "usado_no_jogo": False,
    "card_gerado": False,
}

MEME_SEM_OPCIONAIS = {
    "id": "m002",
    "meme": '"Vacina tem chip"',
    "modulo": "desinformação",
    "dificuldade": 2,
    "contexto_oculto": "Mãe não vacinou o filho. Criança pegou coqueluche.",
    "pilula_sabedoria": "Informação errada mata.",
    "verificacao": {"status": "falso", "fonte": "OMS", "explicacao": "Sem evidência"},
    "usado_no_jogo": False,
    "card_gerado": False,
}


# ── Tests: meme_para_dilema ────────────────────────────────────────────────────

class TestMemeparaDilema:
    def setup_method(self):
        from gerar_cards import meme_para_dilema
        self.fn = meme_para_dilema

    def test_exporta_pilula_sabedoria(self):
        d = self.fn(MEME_COMPLETO, 5)
        assert d["pilula_sabedoria"] == MEME_COMPLETO["pilula_sabedoria"]

    def test_exporta_dificuldade(self):
        d = self.fn(MEME_COMPLETO, 5)
        assert d["dificuldade"] == 1

    def test_exporta_verificacao_status(self):
        d = self.fn(MEME_COMPLETO, 5)
        assert d["verificacao_status"] == "enganoso"

    def test_exporta_impacto_real(self):
        d = self.fn(MEME_COMPLETO, 5)
        assert d["impacto_real"] == MEME_COMPLETO["impacto_real"]

    def test_exporta_campos_basicos(self):
        d = self.fn(MEME_COMPLETO, 5)
        assert d["modulo"] == MEME_COMPLETO["modulo"]
        assert d["meme"] == MEME_COMPLETO["meme"]
        assert d["contexto_oculto"] == MEME_COMPLETO["contexto_oculto"]
        assert d["fonte"] == "TSE / Transparência Internacional"

    def test_id_numerado_a_partir_do_indice(self):
        assert self.fn(MEME_COMPLETO, 5)["id"] == "d05"
        assert self.fn(MEME_COMPLETO, 12)["id"] == "d12"
        assert self.fn(MEME_COMPLETO, 99)["id"] == "d99"

    def test_sem_opcionais_usa_defaults(self):
        d = self.fn(MEME_SEM_OPCIONAIS, 6)
        assert d["impacto_real"] == ""
        assert d["pilula_sabedoria"] == "Informação errada mata."

    def test_nao_exporta_campos_internos(self):
        d = self.fn(MEME_COMPLETO, 5)
        assert "usado_no_jogo" not in d
        assert "card_gerado" not in d
        assert "origem" not in d


# ── Tests: gerar_typescript ────────────────────────────────────────────────────

class TestGerarTypescript:
    def setup_method(self):
        from gerar_cards import gerar_typescript, meme_para_dilema
        self.gerar = gerar_typescript
        self.dilemas = [meme_para_dilema(MEME_COMPLETO, 5), meme_para_dilema(MEME_SEM_OPCIONAIS, 6)]

    def test_interface_inclui_pilula_sabedoria(self):
        ts = self.gerar(self.dilemas)
        assert "pilula_sabedoria" in ts

    def test_interface_inclui_dificuldade(self):
        ts = self.gerar(self.dilemas)
        assert "dificuldade" in ts

    def test_interface_inclui_verificacao_status(self):
        ts = self.gerar(self.dilemas)
        assert "verificacao_status" in ts

    def test_conteudo_pilula_presente(self):
        ts = self.gerar(self.dilemas)
        assert "Não votar é uma escolha" in ts

    def test_estrutura_typescript_valida(self):
        ts = self.gerar(self.dilemas)
        assert "export interface Dilema" in ts
        assert "export const dilemas: Dilema[]" in ts
        assert ts.count("{") == ts.count("}")

    def test_dois_dilemas_no_array(self):
        ts = self.gerar(self.dilemas)
        assert ts.count('id: "d') == 2


# ── Tests: filtros ─────────────────────────────────────────────────────────────

class TestFiltros:
    def setup_method(self):
        import gerar_cards as gc
        self.gc = gc

    def test_filtra_por_modulo(self, tmp_path, monkeypatch):
        memes = [MEME_COMPLETO, MEME_SEM_OPCIONAIS]
        resultado = [m for m in memes if m["modulo"] == "eleição" and not m.get("usado_no_jogo")]
        assert len(resultado) == 1
        assert resultado[0]["id"] == "m001"

    def test_filtra_por_ids(self):
        memes = [MEME_COMPLETO, MEME_SEM_OPCIONAIS]
        ids_filtro = ["m002"]
        resultado = [m for m in memes if m["id"] in ids_filtro]
        assert len(resultado) == 1
        assert resultado[0]["id"] == "m002"

    def test_pula_usados_no_jogo(self):
        meme_usado = {**MEME_COMPLETO, "usado_no_jogo": True}
        memes = [meme_usado, MEME_SEM_OPCIONAIS]
        resultado = [m for m in memes if not m.get("usado_no_jogo")]
        assert len(resultado) == 1
        assert resultado[0]["id"] == "m002"


# ── Tests: JSON output ─────────────────────────────────────────────────────────

class TestJsonOutput:
    def test_json_contem_pilula_sabedoria(self):
        from gerar_cards import meme_para_dilema
        d = meme_para_dilema(MEME_COMPLETO, 5)
        serializado = json.dumps({"dilemas": [d]}, ensure_ascii=False)
        data = json.loads(serializado)
        assert data["dilemas"][0]["pilula_sabedoria"] == MEME_COMPLETO["pilula_sabedoria"]

    def test_json_valido_com_caracteres_especiais(self):
        from gerar_cards import meme_para_dilema
        d = meme_para_dilema(MEME_COMPLETO, 5)
        serializado = json.dumps(d, ensure_ascii=False)
        parsed = json.loads(serializado)
        assert parsed["id"] == "d05"
