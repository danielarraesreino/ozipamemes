"""
Testes dos agentes do OzielMemes Pipeline.
Usa mocks do Claude API para isolamento.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Helpers de mock ────────────────────────────────────────────────────────────

def make_gemini_response(text: str):
    """Cria um mock de resposta do Gemini API."""
    resp = MagicMock()
    resp.text = text
    return resp


# alias mantido para não quebrar referências abaixo
make_claude_response = make_gemini_response


# ── ResearchAgent ──────────────────────────────────────────────────────────────

class TestResearchAgent:
    def test_run_from_xml_retorna_candidatos(self, rss_lupa_xml):
        from agents.researcher import ResearchAgent
        agent = ResearchAgent(min_score=0.3)
        candidates = agent.run_from_xml(rss_lupa_xml, agencia="lupa")
        assert len(candidates) >= 2

    def test_candidatos_deduplicados(self, rss_lupa_xml):
        from agents.researcher import ResearchAgent
        agent = ResearchAgent(min_score=0.3)
        # Mesmo XML duas vezes — só deve contar uma vez cada
        c1 = agent.run_from_xml(rss_lupa_xml, agencia="lupa")
        c2 = agent.run_from_xml(rss_lupa_xml, agencia="lupa")
        assert len(c1) == len(c2)

    def test_candidato_tem_source_url(self, rss_lupa_xml):
        from agents.researcher import ResearchAgent
        agent = ResearchAgent(min_score=0.3)
        candidates = agent.run_from_xml(rss_lupa_xml, agencia="lupa")
        for c in candidates:
            assert c.source_url

    def test_candidato_tem_agencia(self, rss_lupa_xml):
        from agents.researcher import ResearchAgent
        agent = ResearchAgent(min_score=0.3)
        candidates = agent.run_from_xml(rss_lupa_xml, agencia="lupa")
        for c in candidates:
            assert c.agencia == "lupa"


# ── DataEnricher ───────────────────────────────────────────────────────────────

class TestDataEnricher:
    def test_run_com_tag_eleicao_retorna_tse(self):
        from agents.enricher import DataEnricher
        enricher = DataEnricher()
        meme = {"id": "m_test", "meme_texto": "Tanto faz votar", "categoria": "apatia"}
        dps = enricher.run(meme, tags=["eleicao", "voto"])
        assert len(dps) >= 1
        assert any(dp.skill == "tse_data" for dp in dps)

    def test_run_com_tag_violencia_retorna_ssp(self):
        from agents.enricher import DataEnricher
        enricher = DataEnricher()
        meme = {"id": "m_test", "meme_texto": "Meme violência", "categoria": "critica_raza"}
        dps = enricher.run(meme, tags=["violência", "segurança"])
        assert any(dp.skill == "ssp_violencia" for dp in dps)

    def test_run_sem_tags_usa_defaults(self):
        from agents.enricher import DataEnricher
        enricher = DataEnricher()
        meme = {"id": "m_test", "meme_texto": "Meme genérico", "categoria": "apatia"}
        dps = enricher.run(meme, tags=[])
        assert len(dps) >= 1

    def test_data_points_ordenados_por_localidade(self):
        from agents.enricher import DataEnricher
        enricher = DataEnricher()
        meme = {"id": "m_test", "meme_texto": "Meme", "categoria": "apatia"}
        dps = enricher.run(meme, tags=["eleicao"])
        if len(dps) > 1:
            niveis = [dp.localidade_nivel for dp in dps]
            assert niveis == sorted(niveis)

    def test_format_for_prompt_sem_dados(self):
        from agents.enricher import DataEnricher
        enricher = DataEnricher()
        resultado = enricher.format_for_prompt([])
        assert "Nenhum dado" in resultado or "sem dados" in resultado.lower()

    def test_format_for_prompt_com_dados(self, data_points_sample):
        from agents.enricher import DataEnricher
        from skills.base_skill import DataPoint
        enricher = DataEnricher()
        dps = [DataPoint(**d) for d in data_points_sample]
        resultado = enricher.format_for_prompt(dps)
        assert "480" in resultado  # valor do primeiro DataPoint
        assert "TSE" in resultado


# ── QualityReviewer ────────────────────────────────────────────────────────────

class TestQualityReviewer:
    def test_aprovado_conteudo_valido(self, meme_m001, data_points_sample):
        from agents.reviewer import QualityReviewer
        reviewer = QualityReviewer()
        conteudo = {
            "contexto_oculto": (
                "O vizinho da esquina não foi votar. "
                "O vereador passou com 480 votos — menos do que os jovens do bairro que ficaram em casa. "
                "A creche fechou."
            ),
            "pilula_sabedoria": "Quem decide por você quando você fica em casa?",
        }
        result = reviewer.run(
            meme=meme_m001,
            conteudo=conteudo,
            data_points=data_points_sample,
        )
        assert result.aprovado

    def test_reprovado_jargao(self, meme_m001, data_points_sample):
        from agents.reviewer import QualityReviewer
        reviewer = QualityReviewer()
        conteudo = {
            "contexto_oculto": "Portanto, consoante os dados apresentados, você deve participar.",
            "pilula_sabedoria": "Haja vista a situação, é mister que você vote.",
        }
        result = reviewer.run(meme=meme_m001, conteudo=conteudo, data_points=data_points_sample)
        assert not result.aprovado
        assert "R2" in result.regras_reprovadas

    def test_precisa_regenerar_com_regra_bloqueante(self, meme_m001, data_points_sample):
        from agents.reviewer import QualityReviewer
        reviewer = QualityReviewer()
        conteudo = {
            "contexto_oculto": "A política afeta todos de maneira significativa.",
            "pilula_sabedoria": "Você deve participar pois é obrigação.",
        }
        result = reviewer.run(meme=meme_m001, conteudo=conteudo, data_points=[])
        assert reviewer.precisa_regenerar(result)

    def test_formatar_feedback_estruturado(self, meme_m001):
        from agents.reviewer import QualityReviewer
        from golden_rules import ReviewResult
        reviewer = QualityReviewer()
        result = ReviewResult(
            aprovado=False,
            score=0.5,
            regras_reprovadas=["R2", "R5"],
            observacoes=["R2: jargão detectado", "R5: padrão de sermão"],
        )
        feedback = reviewer.formatar_feedback(result)
        assert "REJEIÇÃO" in feedback
        assert "R2" in feedback


# ── FactCheckAgent ─────────────────────────────────────────────────────────────

class TestFactCheckAgent:
    def test_extrair_de_rss_sem_claude(self, rss_lupa_xml):
        from agents.fact_checker import FactCheckAgent
        from skills.rss_factcheck import RSSFactCheckSkill
        agent = FactCheckAgent(client=None, use_claude=False)
        skill = RSSFactCheckSkill(min_score=0.3)
        candidates = skill.fetch_from_xml(rss_lupa_xml, agencia="lupa")
        if candidates:
            result = agent.run(candidates[0])
            assert result["status"] in ("falso", "enganoso", "contexto_ausente", "verdadeiro")
            assert result["fonte"]
            assert result["agencia"] == "lupa"

    def test_fallback_sem_claude_retorna_dict(self, rss_lupa_xml):
        from agents.fact_checker import FactCheckAgent
        from skills.rss_factcheck import MemeCandidate
        agent = FactCheckAgent(client=None, use_claude=False)
        candidate = MemeCandidate(
            meme_texto="O governo vai cortar o Bolsa Família",
            source_url="https://lupa.com/fake",
            agencia="lupa",
            titulo_original="É falso que o governo vai cortar o Bolsa Família",
            resumo="A informação é falsa.",
            status_verificacao="falso",
        )
        result = agent.run(candidate)
        assert result["status"] == "falso"

    def test_verificar_texto_heuristico(self):
        from agents.fact_checker import FactCheckAgent
        agent = FactCheckAgent(client=None, use_claude=False)
        result = agent.verificar_texto("Isso é falso — o governo não cortou o benefício")
        assert result["status"] == "falso"


# ── ContentGenerator (com mock Claude) ────────────────────────────────────────

class TestContentGenerator:
    RESPOSTA_CLAUDE_BOA = """
<contexto_oculto>
O vizinho da esquina não foi votar. O vereador passou com 480 votos — menos do que os jovens do bairro que ficaram em casa. A creche fechou.
</contexto_oculto>

<pilula_sabedoria>
Quem decide por você quando você fica em casa?
</pilula_sabedoria>

<roteiro_tiktok_cena3>
O vereador que fechou a creche foi eleito com 480 votos. Seu bairro tem mais jovens do que isso. Você estava em casa naquele dia?
</roteiro_tiktok_cena3>
"""

    def test_parse_response_extrai_campos(self):
        from agents.generator import ContentGenerator
        gen = ContentGenerator(client=MagicMock())  # client=MagicMock() ainda aceito
        parsed = gen._parse_response(self.RESPOSTA_CLAUDE_BOA)
        assert "vereador" in parsed["contexto_oculto"].lower()
        assert "casa" in parsed["pilula_sabedoria"].lower()
        assert parsed["roteiro_tiktok"]

    def test_run_com_mock_claude(self, meme_m001, data_points_sample):
        from agents.generator import ContentGenerator

        # Usa client=MagicMock() com .messages para acionar o caminho de compat
        mock_client = MagicMock()
        mock_client.messages.create.return_value = make_gemini_response(self.RESPOSTA_CLAUDE_BOA)
        # Ajusta retorno para formato Anthropic esperado pelo caminho de compat
        mock_client.messages.create.return_value.content = [MagicMock(text=self.RESPOSTA_CLAUDE_BOA)]

        gen = ContentGenerator(client=mock_client)
        fact_check = {
            "status": "enganoso",
            "fonte": "Agência Lupa",
            "explicacao": "Generalização que ignora diferenças.",
        }
        result = gen.run(
            meme=meme_m001,
            fact_check=fact_check,
            data_points=data_points_sample,
        )
        assert result["contexto_oculto"]
        assert result["pilula_sabedoria"]
        assert result["modelo_claude"]

    def test_build_prompt_inclui_dados_verificados(self, meme_m001, data_points_sample):
        from agents.generator import ContentGenerator
        from skills.base_skill import DataPoint

        gen = ContentGenerator(client=MagicMock())
        fact_check = {"status": "enganoso", "fonte": "Lupa", "explicacao": "Fake."}
        dps = [DataPoint(**d) for d in data_points_sample]
        prompt = gen._build_prompt(meme_m001, fact_check, dps, feedback=None)
        assert "<dados_verificados>" in prompt
        assert "480" in prompt  # valor do DataPoint TSE
        assert "GEMINI" not in prompt  # não deve vazar API key

    def test_run_retorna_fallback_se_claude_falha(self, meme_m001):
        from agents.generator import ContentGenerator

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API down")

        gen = ContentGenerator(client=mock_client, max_retries=0)  # client com .messages → caminho compat
        result = gen.run(meme=meme_m001, fact_check={}, data_points=[])
        # Não deve levantar exceção — deve retornar fallback
        assert "modelo_claude" in result
        assert "erro" in result

    def test_build_prompt_com_feedback(self, meme_m001, data_points_sample):
        from agents.generator import ContentGenerator
        gen = ContentGenerator(client=MagicMock())
        prompt = gen._build_prompt(
            meme_m001,
            {"status": "falso", "fonte": "Lupa", "explicacao": "Fake."},
            [],
            feedback="R2: jargão detectado",
        )
        assert "FEEDBACK" in prompt
        assert "R2" in prompt


# ── OrchestratorAgent ──────────────────────────────────────────────────────────

class TestOrchestratorAgent:
    def test_status_retorna_dict_completo(self, db_mem, config_test):
        from agents.orchestrator import OrchestratorAgent
        import os
        os.makedirs(config_test.data_cache_dir, exist_ok=True)
        orch = OrchestratorAgent(db=db_mem, config=config_test, client=None)
        status = orch.status()
        assert "memes" in status
        assert "fila" in status

    def test_dry_run_nao_processa_itens(self, db_mem, config_test):
        from agents.orchestrator import OrchestratorAgent
        os.makedirs(config_test.data_cache_dir, exist_ok=True)

        # Mock do researcher para não fazer requests reais
        orch = OrchestratorAgent(db=db_mem, config=config_test, client=None)
        orch.researcher.run = lambda: []

        result = orch.run(dry_run=True)
        assert result.status == "dry_run"
        assert result.aprovados == 0

    def test_import_json_popula_db(self, db_mem, config_test):
        json_path = str(ROOT.parent / "ozielmemes" / "database" / "memes.json")
        from pathlib import Path
        if not Path(json_path).exists():
            pytest.skip("memes.json não encontrado")
        count = db_mem.import_from_json(json_path)
        assert count > 0
        stats = db_mem.count_memes()
        assert stats["total"] == count


import os
ROOT = Path(__file__).parent.parent
