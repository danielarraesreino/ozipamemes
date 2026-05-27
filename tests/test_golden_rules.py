"""
Testes exaustivos das 8 golden rules.
TDD: todos estes testes foram escritos ANTES da implementação final das regras.
"""
from __future__ import annotations

import pytest
from golden_rules import (
    check_r1_dado_verificavel,
    check_r2_linguagem_bairro,
    check_r3_sem_vies_partido,
    check_r4_ancoragem_local,
    check_r5_empoderamento,
    check_r6_evidencia_viralizacao,
    check_r7_formato_contexto,
    check_r8_numeros_com_fonte,
    revisar,
    ReviewResult,
)


# ── Fixtures locais ────────────────────────────────────────────────────────────

@pytest.fixture
def dp_campinas():
    return [
        {
            "skill": "tse_data",
            "indicador": "Mínimo votos vereador",
            "valor": "480",
            "unidade": "votos",
            "fonte": "TSE 2024",
            "localidade_nome": "Campinas",
            "localidade_nivel": 2,
        }
    ]


@pytest.fixture
def dp_brasil():
    return [
        {
            "skill": "ibge_demografico",
            "indicador": "População Brasil",
            "valor": "203062512",
            "unidade": "habitantes",
            "fonte": "IBGE Censo 2022",
            "localidade_nome": "Brasil",
            "localidade_nivel": 5,
        }
    ]


@pytest.fixture
def meme_com_fonte(meme_m001):
    return meme_m001


@pytest.fixture
def meme_sem_fonte():
    return {
        "id": "m_test",
        "meme_texto": "Política não presta",
        "categoria": "apatia",
    }


# ── R1: Dado verificável ───────────────────────────────────────────────────────

class TestR1DadoVerificavel:
    def test_aprovado_numero_no_texto_corresponde_ao_dp(self, dp_campinas):
        ctx = "O vereador foi eleito com 480 votos. Seu bairro tem mais jovens do que isso."
        r = check_r1_dado_verificavel(ctx, dp_campinas)
        assert r.passed, r.message

    def test_aprovado_com_ancoragem_local_sem_numero(self, data_points_vazios):
        ctx = "No Oziel, a creche fechou porque ninguém foi à audiência pública."
        r = check_r1_dado_verificavel(ctx, data_points_vazios)
        assert r.passed, r.message

    def test_reprovado_sem_numero_sem_local(self, data_points_vazios):
        ctx = "A política afeta a vida das pessoas de maneira significativa."
        r = check_r1_dado_verificavel(ctx, data_points_vazios)
        assert not r.passed

    def test_reprovado_numero_sem_dp_correspondente(self, dp_campinas):
        ctx = "99% das pessoas acredita nisso."  # 99 não está no dp (480)
        r = check_r1_dado_verificavel(ctx, dp_campinas)
        assert not r.passed

    def test_aprovado_personagem_concreto_sem_numero(self, data_points_vazios):
        ctx = "Sua vizinha não foi votar e o posto fechou."
        r = check_r1_dado_verificavel(ctx, data_points_vazios)
        assert r.passed, r.message

    def test_aprovado_numero_percentual(self):
        dp = [{"skill": "tse", "indicador": "comparecimento", "valor": "76.3",
               "unidade": "%", "fonte": "TSE", "localidade_nome": "Campinas",
               "localidade_nivel": 2}]
        ctx = "Apenas 76.3% dos eleitores compareceram nas últimas eleições de Campinas."
        r = check_r1_dado_verificavel(ctx, dp)
        assert r.passed


# ── R2: Linguagem do bairro ────────────────────────────────────────────────────

class TestR2LinguagemBairro:
    def test_aprovado_sem_jargao(self, contexto_bom, pilula_boa):
        r = check_r2_linguagem_bairro(contexto_bom, pilula_boa)
        assert r.passed

    def test_reprovado_portanto(self):
        ctx = "A creche fechou. Portanto, os moradores precisam buscar alternativas."
        r = check_r2_linguagem_bairro(ctx, "Pensa nisso.")
        assert not r.passed
        assert "portanto" in r.message.lower()

    def test_reprovado_consoante(self, contexto_ruim_jargao, pilula_boa):
        r = check_r2_linguagem_bairro(contexto_ruim_jargao, pilula_boa)
        assert not r.passed

    def test_reprovado_mister(self):
        ctx = "É mister que todos participem da política municipal."
        r = check_r2_linguagem_bairro(ctx, "Vote.")
        assert not r.passed

    def test_reprovado_na_pilula(self):
        ctx = "O bairro perdeu a quadra."
        pilula = "Haja vista a situação exposta, você deve agir."
        r = check_r2_linguagem_bairro(ctx, pilula)
        assert not r.passed

    def test_case_insensitive(self):
        ctx = "PORTANTO você precisa votar."
        r = check_r2_linguagem_bairro(ctx, "ok")
        assert not r.passed


# ── R3: Sem viés de partido ────────────────────────────────────────────────────

class TestR3SemVies:
    def test_aprovado_sem_partido(self, contexto_bom, pilula_boa):
        r = check_r3_sem_vies_partido(contexto_bom, pilula_boa)
        assert r.passed

    def test_reprovado_PT(self):
        ctx = "O PT ganhou a eleição e a creche abriu."
        r = check_r3_sem_vies_partido(ctx, "Vote.")
        assert not r.passed

    def test_reprovado_PL(self):
        ctx = "O PL aprovou o corte da verba."
        r = check_r3_sem_vies_partido(ctx, "Vote.")
        assert not r.passed

    def test_reprovado_nome_politico(self):
        ctx = "Lula assinou o decreto que fechou as creches."
        r = check_r3_sem_vies_partido(ctx, "ok")
        assert not r.passed

    def test_aprovado_menciona_esquerda_direita(self):
        # Conceitos políticos gerais não são viés de partido
        ctx = "Esquerda e direita votam diferente no orçamento."
        r = check_r3_sem_vies_partido(ctx, "ok")
        assert r.passed

    def test_aprovado_vereador_generico(self):
        ctx = "O vereador votou pelo fechamento da creche."
        r = check_r3_sem_vies_partido(ctx, "Vote.")
        assert r.passed


# ── R4: Ancoragem local ────────────────────────────────────────────────────────

class TestR4AncoragemLocal:
    def test_aprovado_dp_campinas(self, dp_campinas):
        r = check_r4_ancoragem_local("O bairro perdeu recursos.", dp_campinas)
        assert r.passed
        assert r.flag is None  # sem warning quando tem dado local

    def test_aprovado_menciona_oziel(self, data_points_vazios):
        r = check_r4_ancoragem_local("No Oziel, a escola fechou.", data_points_vazios)
        assert r.passed

    def test_aprovado_menciona_campinas(self, data_points_vazios):
        r = check_r4_ancoragem_local("Em Campinas isso acontece todo ano.", data_points_vazios)
        assert r.passed

    def test_warning_dado_nacional(self, dp_brasil):
        r = check_r4_ancoragem_local("A política afeta todos.", dp_brasil)
        # Passa mas com flag de aviso
        assert r.passed
        assert r.flag == "baixa_ancoragem_local"

    def test_aprovado_menciona_dic(self, data_points_vazios):
        r = check_r4_ancoragem_local("No DIC, o ônibus passou a custar mais.", data_points_vazios)
        assert r.passed


# ── R5: Empoderamento ──────────────────────────────────────────────────────────

class TestR5Empoderamento:
    def test_aprovado_pilula_boa(self, pilula_boa):
        r = check_r5_empoderamento(pilula_boa)
        assert r.passed

    def test_reprovado_voce_deve(self, pilula_sermao):
        r = check_r5_empoderamento(pilula_sermao)
        assert not r.passed

    def test_reprovado_voce_precisa(self):
        r = check_r5_empoderamento("Você precisa ir votar toda eleição.")
        assert not r.passed

    def test_reprovado_e_obrigacao(self):
        r = check_r5_empoderamento("É obrigação do cidadão participar.")
        assert not r.passed

    def test_reprovado_todo_cidadao_deve(self):
        r = check_r5_empoderamento("Todo cidadão deve exercer o voto.")
        assert not r.passed

    def test_aprovado_pergunta_retórica(self):
        r = check_r5_empoderamento("Quem decide por você quando você fica em casa?")
        assert r.passed


# ── R6: Evidência de viralização ──────────────────────────────────────────────

class TestR6Viralizacao:
    def test_aprovado_com_source_url(self, meme_com_fonte):
        r = check_r6_evidencia_viralizacao(meme_com_fonte)
        assert r.passed

    def test_reprovado_sem_fonte(self, meme_sem_fonte):
        r = check_r6_evidencia_viralizacao(meme_sem_fonte)
        assert not r.passed

    def test_aprovado_com_source_rss(self):
        meme = {"source_rss": "lupa", "source_url": None}
        r = check_r6_evidencia_viralizacao(meme)
        assert r.passed

    def test_aprovado_com_verificacao(self):
        meme = {"source_url": None, "source_rss": None, "verificacao": {"status": "falso"}}
        r = check_r6_evidencia_viralizacao(meme)
        assert r.passed


# ── R7: Formato contexto ───────────────────────────────────────────────────────

class TestR7FormatoContexto:
    def test_aprovado_3_frases_com_personagem(self, contexto_bom):
        r = check_r7_formato_contexto(contexto_bom)
        assert r.passed

    def test_reprovado_4_frases(self, contexto_ruim_muitas_frases):
        r = check_r7_formato_contexto(contexto_ruim_muitas_frases)
        assert not r.passed
        assert "4" in r.message

    def test_reprovado_sem_personagem(self):
        ctx = "A política decide o orçamento. O orçamento define os serviços. Os serviços importam."
        r = check_r7_formato_contexto(ctx)
        assert not r.passed
        assert "personagem" in r.message.lower()

    def test_aprovado_1_frase_com_voce(self):
        ctx = "O vereador que fechou a creche foi eleito com menos votos do que você tem amigos."
        r = check_r7_formato_contexto(ctx)
        assert r.passed

    def test_aprovado_personagem_familia(self):
        ctx = "A família da esquina perdeu o posto de saúde. A câmara votou. Ninguém foi."
        r = check_r7_formato_contexto(ctx)
        assert r.passed

    def test_aprovado_personagem_bairro(self):
        ctx = "O bairro perdeu 40% da verba de educação. A audiência foi marcada. 3 moradores foram."
        r = check_r7_formato_contexto(ctx)
        assert r.passed


# ── R8: Números com fonte ──────────────────────────────────────────────────────

class TestR8NumerosComFonte:
    def test_aprovado_sem_numero(self, data_points_sample):
        ctx = "O bairro perdeu o posto de saúde depois da votação."
        r = check_r8_numeros_com_fonte(ctx, "Pensa nisso.", data_points_sample)
        assert r.passed

    def test_aprovado_numero_no_dp(self, data_points_sample):
        ctx = "O vereador foi eleito com 480 votos. Seu bairro tem mais jovens do que isso."
        r = check_r8_numeros_com_fonte(ctx, "ok", data_points_sample)
        assert r.passed

    def test_reprovado_numero_inventado(self, data_points_sample):
        ctx = "Apenas 12% dos jovens votaram. Isso é pouco demais."
        r = check_r8_numeros_com_fonte(ctx, "ok", data_points_sample)
        assert not r.passed
        assert "12" in r.message or "12%" in r.message

    def test_reprovado_numero_com_dp_vazio(self):
        ctx = "O bairro tem 5.000 famílias em risco."
        r = check_r8_numeros_com_fonte(ctx, "ok", [])
        assert not r.passed

    def test_aprovado_numero_populacao(self, data_points_sample):
        # 1213792 está no data_points_sample
        ctx = "Em Campinas moram 1213792 pessoas. Seu voto conta."
        r = check_r8_numeros_com_fonte(ctx, "ok", data_points_sample)
        assert r.passed


# ── revisar() integradora ──────────────────────────────────────────────────────

class TestRevisar:
    def test_aprovado_conteudo_perfeito(
        self, meme_m001, contexto_bom, pilula_boa, data_points_sample
    ):
        # contexto_bom tem "480" que está em data_points_sample
        resultado = revisar(meme_m001, contexto_bom, pilula_boa, data_points_sample)
        assert resultado.aprovado
        assert resultado.score >= 0.75

    def test_reprovado_jargao_academico(
        self, meme_m001, contexto_ruim_jargao, pilula_boa, data_points_sample
    ):
        resultado = revisar(meme_m001, contexto_ruim_jargao, pilula_boa, data_points_sample)
        assert not resultado.aprovado
        assert "R2" in resultado.regras_reprovadas

    def test_reprovado_pilula_sermao(
        self, meme_m001, contexto_bom, pilula_sermao, data_points_sample
    ):
        resultado = revisar(meme_m001, contexto_bom, pilula_sermao, data_points_sample)
        assert not resultado.aprovado
        assert "R5" in resultado.regras_reprovadas

    def test_reprovado_muitas_frases(
        self, meme_m001, contexto_ruim_muitas_frases, pilula_boa, data_points_sample
    ):
        resultado = revisar(meme_m001, contexto_ruim_muitas_frases, pilula_boa, data_points_sample)
        assert not resultado.aprovado
        assert "R7" in resultado.regras_reprovadas

    def test_score_calculado_corretamente(
        self, meme_m001, contexto_bom, pilula_boa, data_points_sample
    ):
        resultado = revisar(meme_m001, contexto_bom, pilula_boa, data_points_sample)
        n_total = 8
        assert resultado.score == round(len(resultado.regras_aprovadas) / n_total, 2)

    def test_flag_baixa_ancoragem_local_nao_rejeita(self, data_points_sample):
        meme = {
            "id": "m_test",
            "meme_texto": "Tudo é fraude",
            "source_url": "https://lupa.com/fake",
        }
        # Contexto sem menção a Campinas/Oziel
        ctx = "Sua vizinha acreditou e não foi votar. O vereador passou com 480 votos."
        pilula = "Quem decide por você quando você fica em casa?"
        dp_nacional = [
            {
                "skill": "ibge",
                "indicador": "pop",
                "valor": "480",  # mesmo número do contexto
                "unidade": "votos",
                "fonte": "IBGE",
                "localidade_nome": "Brasil",
                "localidade_nivel": 5,
            }
        ]
        resultado = revisar(meme, ctx, pilula, dp_nacional)
        # Deve aprovar (flag não rejeita) mas registrar a flag
        assert resultado.flags.get("baixa_ancoragem_local") is True
