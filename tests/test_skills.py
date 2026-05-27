"""
Testes das skills de dados abertos e RSS.
Usa mocks HTTP para isolar das APIs externas.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Cache ─────────────────────────────────────────────────────────────────────

class TestSkillCache:
    def test_miss_retorna_none(self, tmp_path):
        from skills.cache import SkillCache
        c = SkillCache(str(tmp_path / "cache"))
        assert c.get("ibge", {"k": "v"}) is None

    def test_set_e_get(self, tmp_path):
        from skills.cache import SkillCache
        c = SkillCache(str(tmp_path / "cache"))
        data = [{"indicador": "pop", "valor": "1000000"}]
        c.set("ibge", {"k": "v"}, data)
        assert c.get("ibge", {"k": "v"}) == data

    def test_ttl_expirado_retorna_none(self, tmp_path):
        from skills.cache import SkillCache
        import time
        c = SkillCache(str(tmp_path / "cache"), ttl_hours=0)
        c.set("ibge", {"k": "v"}, [{"x": "y"}])
        # ttl=0 → já expirado
        assert c.get("ibge", {"k": "v"}) is None

    def test_invalidate_limpa_skill(self, tmp_path):
        from skills.cache import SkillCache
        c = SkillCache(str(tmp_path / "cache"))
        c.set("tse", {"k": "1"}, [{"x": "y"}])
        c.set("tse", {"k": "2"}, [{"a": "b"}])
        count = c.invalidate("tse")
        assert count == 2
        assert c.get("tse", {"k": "1"}) is None


# ── DataPoint ─────────────────────────────────────────────────────────────────

class TestDataPoint:
    def test_to_dict_preserva_campos(self):
        from skills.base_skill import DataPoint
        dp = DataPoint(
            skill="ibge", indicador="pop", valor="1213792", unidade="hab",
            fonte="IBGE", localidade_nome="Campinas", localidade_nivel=2,
            fonte_url="https://ibge.gov.br", ano_referencia="2022",
        )
        d = dp.to_dict()
        assert d["valor"] == "1213792"
        assert d["localidade_nivel"] == 2

    def test_para_prompt_formatado(self):
        from skills.base_skill import DataPoint
        dp = DataPoint(
            skill="tse", indicador="Votos mínimos vereador", valor="480",
            unidade="votos", fonte="TSE 2024", localidade_nome="Campinas",
            localidade_nivel=2, ano_referencia="2024",
        )
        prompt = dp.para_prompt()
        assert "480" in prompt
        assert "TSE 2024" in prompt
        assert "Campinas" in prompt


# ── TSE ───────────────────────────────────────────────────────────────────────

class TestTSESkill:
    def test_fallback_retorna_dados_campinas(self):
        from skills.tse_data import TSESkill
        skill = TSESkill()
        dps = skill.run()
        assert len(dps) >= 3
        assert all(dp.localidade_nome == "Campinas" for dp in dps)

    def test_fallback_contem_votos_minimos(self):
        from skills.tse_data import TSESkill
        skill = TSESkill()
        dps = skill.run()
        indicadores = [dp.indicador for dp in dps]
        assert any("votos" in ind.lower() or "vereador" in ind.lower() for ind in indicadores)

    def test_fallback_valores_sao_strings(self):
        from skills.tse_data import TSESkill
        skill = TSESkill()
        for dp in skill.run():
            assert isinstance(dp.valor, str)
            assert dp.valor  # não vazio

    def test_skill_name_correto(self):
        from skills.tse_data import SKILL_NAME
        assert SKILL_NAME == "tse_data"

    def test_nivelidade_2_campinas(self):
        from skills.tse_data import TSESkill
        skill = TSESkill()
        for dp in skill.run():
            assert dp.localidade_nivel == 2

    def test_fallback_comparecimento(self):
        from skills.tse_data import TSESkill
        skill = TSESkill()
        dps = skill.get_comparecimento_campinas(2024)
        assert len(dps) >= 1
        assert "%" in dps[0].unidade


# ── SSP Violência ─────────────────────────────────────────────────────────────

class TestSSPViolenciaSkill:
    def test_retorna_homicidios_campinas(self):
        from skills.ssp_violencia import SSPViolenciaSkill
        skill = SSPViolenciaSkill()
        dps = skill.run()
        assert len(dps) >= 1
        assert any("homicídio" in dp.indicador.lower() for dp in dps)

    def test_localidade_campinas(self):
        from skills.ssp_violencia import SSPViolenciaSkill
        skill = SSPViolenciaSkill()
        for dp in skill.run():
            assert dp.localidade_nome == "Campinas"
            assert dp.localidade_nivel == 2

    def test_fonte_ssp(self):
        from skills.ssp_violencia import SSPViolenciaSkill
        skill = SSPViolenciaSkill()
        for dp in skill.run():
            assert "SSP" in dp.fonte or "ssp" in dp.fonte_url


# ── Transparência Federal ─────────────────────────────────────────────────────

class TestTransparenciaSkill:
    def test_retorna_bolsa_familia_campinas(self):
        from skills.transparencia_federal import TransparenciaFederalSkill
        skill = TransparenciaFederalSkill()
        dps = skill.get_beneficiarios_bolsa_familia()
        assert len(dps) >= 1
        assert any("bolsa" in dp.indicador.lower() for dp in dps)

    def test_sem_api_key_usa_fallback(self):
        from skills.transparencia_federal import TransparenciaFederalSkill
        skill = TransparenciaFederalSkill(api_key="")
        dps = skill.run(tags=["bolsa familia"])
        assert len(dps) >= 1

    def test_run_com_tag_saude(self):
        from skills.transparencia_federal import TransparenciaFederalSkill
        skill = TransparenciaFederalSkill()
        dps = skill.run(tags=["saúde"])
        assert any("sus" in dp.indicador.lower() or "sus" in dp.fonte_url.lower() for dp in dps)


# ── RSS Fact-Check ─────────────────────────────────────────────────────────────

class TestRSSFactCheckSkill:
    def test_parse_xml_fixture_retorna_candidatos(self, rss_lupa_xml):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill(min_score=0.3)
        candidates = skill.fetch_from_xml(rss_lupa_xml, agencia="lupa")
        assert len(candidates) >= 2

    def test_candidato_tem_meme_texto(self, rss_lupa_xml):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill(min_score=0.3)
        candidates = skill.fetch_from_xml(rss_lupa_xml, agencia="lupa")
        for c in candidates:
            assert c.meme_texto
            assert len(c.meme_texto) >= 10

    def test_candidato_tem_status(self, rss_lupa_xml):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill(min_score=0.3)
        candidates = skill.fetch_from_xml(rss_lupa_xml, agencia="lupa")
        for c in candidates:
            assert c.status_verificacao in ("falso", "enganoso", "contexto_ausente", "verdadeiro", "")

    def test_candidato_tem_source_url(self, rss_lupa_xml):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill(min_score=0.3)
        candidates = skill.fetch_from_xml(rss_lupa_xml, agencia="lupa")
        for c in candidates:
            assert c.source_url.startswith("http")

    def test_filtro_noticia_nao_politica_score_baixo(self):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill()
        # Item sem gatilho de meme nem vocabulário político
        xml = """<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Receita de bolo de chocolate</title>
        <link>https://exemplo.com</link>
        <description>Como fazer bolo de chocolate em casa.</description>
        </item></channel></rss>"""
        candidates = skill.fetch_from_xml(xml, agencia="lupa")
        assert len(candidates) == 0

    def test_is_meme_politico_positivo(self):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill()
        texto = 'Compartilha aí — o governo vai cortar o Bolsa Família semana que vem!'
        passou, score = skill.is_meme_politico(texto)
        assert passou, f"Score {score} deveria passar no threshold 0.3"
        assert score >= 0.3

    def test_is_meme_politico_negativo(self):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill()
        texto = 'Veja as novidades do mundo da moda verão 2025'
        passou, score = skill.is_meme_politico(texto)
        assert not passou
        assert score < 0.4

    def test_extrair_meme_de_titulo_com_aspas(self):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill()
        xml = """<?xml version="1.0"?><rss version="2.0"><channel>
        <item>
          <title>É falso que "todos os vereadores são ladrões e tanto faz votar"</title>
          <link>https://lupa.com/fake123</link>
          <description>A afirmação é falsa. Generalização que ignora diferenças entre mandatos.</description>
        </item></channel></rss>"""
        candidates = skill.fetch_from_xml(xml, agencia="lupa")
        assert len(candidates) == 1
        assert "vereador" in candidates[0].meme_texto.lower()

    def test_score_fact_checker_maior_que_fonte_desconhecida(self):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill()
        # _classify retorna (score, status) — score primeiro
        score_lupa, _ = skill._classify("É falso que o governo vai cortar o Bolsa Família", "lupa")
        score_manual, _ = skill._classify("É falso que o governo vai cortar o Bolsa Família", "manual")
        assert score_lupa > score_manual

    def test_to_dict_completo(self, rss_lupa_xml):
        from skills.rss_factcheck import RSSFactCheckSkill
        skill = RSSFactCheckSkill(min_score=0.3)
        candidates = skill.fetch_from_xml(rss_lupa_xml, agencia="lupa")
        if candidates:
            d = candidates[0].to_dict()
            assert "meme_texto" in d
            assert "source_url" in d
            assert "source_rss" in d


# ── DatabaseManager ────────────────────────────────────────────────────────────

class TestDatabaseManager:
    def test_init_db_cria_tabelas(self, db_mem):
        cur = db_mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tabelas = {row["name"] for row in cur.fetchall()}
        assert "memes" in tabelas
        assert "pipeline_queue" in tabelas
        assert "data_points" in tabelas

    def test_insert_e_get_meme(self, db_mem):
        db_mem.insert_meme({
            "id": "m999",
            "meme_texto": "Teste de meme",
            "categoria": "apatia",
        })
        m = db_mem.get_meme_by_id("m999")
        assert m is not None
        assert m["meme_texto"] == "Teste de meme"

    def test_insert_meme_idempotente(self, db_mem):
        db_mem.insert_meme({"id": "m001", "meme_texto": "Texto X", "categoria": "apatia"})
        db_mem.insert_meme({"id": "m001", "meme_texto": "Texto X", "categoria": "apatia"})
        memes = db_mem.list_memes()
        assert len(memes) == 1

    def test_insert_verificacao_atualiza_is_current(self, db_mem):
        db_mem.insert_meme({"id": "m001", "meme_texto": "Texto", "categoria": "apatia"})
        db_mem.insert_verificacao("m001", {"status": "falso", "fonte": "Lupa"})
        db_mem.insert_verificacao("m001", {"status": "enganoso", "fonte": "AosFatos"})
        verif = db_mem.get_verificacao_atual("m001")
        assert verif["status"] == "enganoso"
        assert verif["is_current"] == 1

    def test_insert_data_point(self, db_mem, data_points_sample):
        db_mem.insert_meme({"id": "m001", "meme_texto": "Texto", "categoria": "apatia"})
        for dp in data_points_sample:
            db_mem.insert_data_point("m001", dp)
        dps = db_mem.get_data_points("m001")
        assert len(dps) == len(data_points_sample)

    def test_pipeline_queue_upsert(self, db_mem):
        qid = db_mem.upsert_queue_item({
            "meme_texto_raw": "Texto do meme",
            "estado": "discovered",
        })
        assert qid > 0
        # Duplicata não cria novo item
        qid2 = db_mem.upsert_queue_item({
            "meme_texto_raw": "Texto do meme",
            "estado": "fact_checking",
        })
        assert qid == qid2

    def test_get_queue_by_estado(self, db_mem):
        db_mem.upsert_queue_item({"meme_texto_raw": "Meme A", "estado": "discovered"})
        db_mem.upsert_queue_item({"meme_texto_raw": "Meme B", "estado": "approved"})
        discovered = db_mem.get_queue_by_estado("discovered")
        assert len(discovered) == 1
        assert discovered[0]["meme_texto_raw"] == "Meme A"

    def test_count_memes(self, db_mem):
        db_mem.insert_meme({"id": "m001", "meme_texto": "A", "categoria": "apatia"})
        db_mem.insert_meme({"id": "m002", "meme_texto": "B", "categoria": "desinformacao"})
        stats = db_mem.count_memes()
        assert stats["total"] == 2
