"""
Fixtures compartilhadas entre todos os testes do OzielMemes Pipeline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def fake_api_key(monkeypatch):
    """Garante que GEMINI_API_KEY existe em todos os testes."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-fake-key-for-tests")


@pytest.fixture
def config_test(tmp_path, monkeypatch):
    """Config com paths temporários e API key fake."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-fake-key-for-tests")
    from config import Config
    return Config(
        db_path=str(tmp_path / "test.db"),
        data_cache_dir=str(tmp_path / "data"),
        memes_json_path=str(FIXTURES_DIR / "../../../database/memes.json"),
    )


@pytest.fixture
def db(config_test):
    """DatabaseManager inicializado com schema em arquivo temporário."""
    from database.db import DatabaseManager
    manager = DatabaseManager(config_test.db_path)
    manager.init_db()
    yield manager
    manager.close()


@pytest.fixture
def db_mem():
    """DatabaseManager em memória — mais rápido para testes unitários."""
    from database.db import DatabaseManager
    manager = DatabaseManager(":memory:")
    manager.init_db()
    yield manager
    manager.close()


@pytest.fixture
def meme_m001():
    """Meme de apatia completo para testes."""
    return json.loads((FIXTURES_DIR / "meme_m001.json").read_text())


@pytest.fixture
def data_points_sample():
    """DataPoints de exemplo para testes de reviewer e generator."""
    return json.loads((FIXTURES_DIR / "data_points_sample.json").read_text())


@pytest.fixture
def data_points_vazios():
    return []


@pytest.fixture
def rss_lupa_xml():
    return (FIXTURES_DIR / "rss_lupa_sample.xml").read_text()


@pytest.fixture
def contexto_bom():
    # Usa 480 (está em data_points_sample) sem inventar outros números
    return (
        "O vizinho da esquina acreditou e não foi votar. "
        "O vereador foi eleito com 480 votos — menos do que a quantidade de jovens do bairro que ficaram em casa. "
        "A creche fechou e agora a família precisa pegar dois ônibus."
    )


@pytest.fixture
def contexto_ruim_jargao():
    return (
        "Consoante os dados apresentados, evidencia-se que a participação política "
        "é mister para a manutenção da democracia no âmbito municipal."
    )


@pytest.fixture
def contexto_ruim_muitas_frases():
    return (
        "Primeira frase. Segunda frase. Terceira frase. Quarta frase que repova a regra."
    )


@pytest.fixture
def pilula_boa():
    return "Quem fica em casa deixa o outro escolher por você. Você decide ou deixa?"


@pytest.fixture
def pilula_sermao():
    return "Você deve participar da política pois é seu dever como cidadão."
