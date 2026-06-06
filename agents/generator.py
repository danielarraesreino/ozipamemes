"""
ContentGenerator — gera contexto_oculto, pílula_sabedoria e roteiro TikTok via Claude API.

Protocolo anti-alucinação:
  - Prompt fornece bloco <dados_verificados> fechado com DataPoints reais
  - Instrução explícita: NÃO inventar números
  - Parsing via delimitadores XML determinísticos
  - Fallback gracioso se parsing falhar
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from agents.base_agent import BaseAgent
from skills.base_skill import DataPoint

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v3_oziel_2026"

SYSTEM_GENERATOR = """Você é um especialista em comunicação periférica para o projeto Cidadania Conectada: Vozes do Oziel.
Cria conteúdo educativo para adolescentes de 12-17 anos do Jardim Oziel, Campinas-SP.

CONCEITO CENTRAL — O DADO OCULTO (lógica Freakonomics):
Todo meme viral e polarizante funciona como uma cortina: ele oferece uma explicação simples e emocional
para esconder uma realidade econômica ou social inconveniente para quem concentra poder.
O contexto_oculto é exatamente esse dado que o meme suprime.

Pergunta que guia todo o conteúdo:
"Qual realidade concreta esse meme impede esse jovem de enxergar?"

Estrutura do dado oculto:
  → Quem se beneficia quando o jovem acredita nesse meme?
  → Qual número ou fato concreto contraria a narrativa do meme?
  → Qual consequência direta isso tem no Oziel, na escola, no bairro?

REGRAS ABSOLUTAS — violação invalida o conteúdo:
1. Use SOMENTE dados do bloco <dados_verificados>. Nunca invente números.
2. Linguagem do bairro: direta, sem jargão acadêmico, sem sermão.
3. contexto_oculto: máximo 3 frases. Personagem concreto (vizinha, irmão, a creche, o bairro) + dado que o meme esconde.
4. pilula_sabedoria: fala COM o jovem, não PARA ele. Empoderamento, não julgamento.
5. Sem menção a partidos políticos específicos. Foco em estruturas, mecanismos e consequências reais.
6. Se não houver número verificável, use narrativa qualitativa com personagem — nunca invente cifras.
7. objetivo_meme: 1-2 frases diretas — o que o meme quer que o jovem acredite E quem ganha quando ele acredita nisso.
8. As DUAS alternativas da pílula seguem TODAS as regras acima (mesmos dados, linguagem do bairro). São versões para a equipe escolher no vídeo da campanha:
   - pilula_alternativa_1: ângulo EMOCIONAL/PESSOAL (fala do sentimento, do cotidiano, de quem é do bairro).
   - pilula_alternativa_2: ângulo FACTUAL/CHAMADA-PRA-AÇÃO (aponta o dado e convida a fazer algo concreto).
   As alternativas dizem a MESMA ideia da pílula principal, mudando só a abordagem.

Responda EXCLUSIVAMENTE no formato XML abaixo, sem texto fora das tags:

<objetivo_meme>
[1-2 frases: o que o meme quer que o jovem acredite + quem se beneficia quando ele acredita]
</objetivo_meme>

<contexto_oculto>
[O dado que o meme esconde: personagem concreto + o que a narrativa rasa oculta + consequência real no bairro]
</contexto_oculto>

<pilula_sabedoria>
[1 frase curta — o empoderamento que nasce ao ver o dado oculto]
</pilula_sabedoria>

<pilula_alternativa_1>
[Mesma ideia, ângulo emocional/pessoal — para o vídeo da campanha]
</pilula_alternativa_1>

<pilula_alternativa_2>
[Mesma ideia, ângulo factual/chamada-pra-ação — para o vídeo da campanha]
</pilula_alternativa_2>

<roteiro_tiktok_cena3>
[A revelação do dado oculto em 3-4 linhas, linguagem direta, sem sermão]
</roteiro_tiktok_cena3>"""


class ContentGenerator(BaseAgent):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-1.5-flash",
        max_retries: int = 2,
        client=None,  # compat com testes antigos
    ) -> None:
        super().__init__(name="generator", api_key=api_key, model=model, client=client)
        self.max_retries = max_retries

    def run(
        self,
        meme: dict,
        fact_check: dict,
        data_points: list[DataPoint | dict],
        feedback_anterior: str | None = None,
    ) -> dict:
        """
        Gera conteúdo para um meme usando Claude API.
        data_points devem ser DataPoints já coletados pelo DataEnricher.
        feedback_anterior é usado em regenerações após reprovação da golden rule.
        Retorna dict com contexto_oculto, pilula_sabedoria, roteiro_tiktok, metadata.
        """
        if not self.client:
            raise RuntimeError("ContentGenerator requer GEMINI_API_KEY configurada")

        prompt = self._build_prompt(meme, fact_check, data_points, feedback_anterior)
        self.log(f"Gerando conteúdo para meme {meme.get('id', '?')}...")

        for attempt in range(self.max_retries + 1):
            try:
                resposta = self._call_claude(
                    messages=[{"role": "user", "content": prompt}],
                    system=SYSTEM_GENERATOR,
                    max_tokens=1024,
                )
                parsed = self._parse_response(resposta)
                if parsed.get("contexto_oculto") and parsed.get("pilula_sabedoria"):
                    parsed.update({
                        "modelo_claude": self.model,  # campo mantido no DB
                        "prompt_version": PROMPT_VERSION,
                        "meme_id": meme.get("id"),
                    })
                    return parsed
                self.log(f"Parse incompleto na tentativa {attempt+1}", "WARNING")
            except Exception as exc:
                self.log(f"Geração falhou (tentativa {attempt+1}): {exc}", "ERROR")

        # Fallback: retorna estrutura vazia para não quebrar o pipeline
        return {
            "objetivo_meme": "",
            "contexto_oculto": "",
            "pilula_sabedoria": "",
            "pilula_alt1": "",
            "pilula_alt2": "",
            "roteiro_tiktok": "",
            "modelo_claude": self.model,
            "prompt_version": PROMPT_VERSION,
            "erro": "Geração falhou após todas as tentativas",
        }

    def _build_prompt(
        self,
        meme: dict,
        fact_check: dict,
        data_points: list[DataPoint | dict],
        feedback: str | None,
    ) -> str:
        # Formata DataPoints para o bloco fechado
        dps_linhas = []
        for i, dp in enumerate(data_points, 1):
            if isinstance(dp, DataPoint):
                dps_linhas.append(f"{i}. {dp.para_prompt()}")
            else:
                loc = f"{dp.get('localidade_nome', '')} ({dp.get('ano_referencia', '')})"
                dps_linhas.append(
                    f"{i}. {dp.get('indicador', '')}: {dp.get('valor', '')} "
                    f"{dp.get('unidade', '')} — {loc} [Fonte: {dp.get('fonte', '')}]"
                )

        dados_bloco = "\n".join(dps_linhas) if dps_linhas else "(sem dados abertos disponíveis)"

        # Reconstrói tags como lista simples
        tags = meme.get("tags", [])
        if isinstance(tags, str):
            import json
            try:
                tags = json.loads(tags)
            except Exception:
                tags = [tags]

        prompt_parts = [
            f"MEME: {meme.get('meme_texto', '')}",
            f"CATEGORIA: {meme.get('categoria', '')}",
            f"MÓDULO DO JOGO: {meme.get('modulo', '')}",
            f"VERIFICAÇÃO: {fact_check.get('status', '').upper()} — Fonte: {fact_check.get('fonte', '')}",
            f"EXPLICAÇÃO DO FACT-CHECK: {fact_check.get('explicacao', '')}",
            f"TAGS: {', '.join(tags) if tags else 'sem tags'}",
            "",
            "<dados_verificados>",
            dados_bloco,
            "</dados_verificados>",
        ]

        if feedback:
            prompt_parts += [
                "",
                "FEEDBACK DA REVISÃO ANTERIOR (corrija estes pontos):",
                feedback,
            ]

        return "\n".join(prompt_parts)

    def _parse_response(self, texto: str) -> dict:
        """Extrai campos do XML retornado pelo Claude."""
        def extract(tag: str) -> str:
            pattern = rf"<{tag}>(.*?)</{tag}>"
            m = re.search(pattern, texto, re.DOTALL)
            return m.group(1).strip() if m else ""

        return {
            "objetivo_meme": extract("objetivo_meme"),
            "contexto_oculto": extract("contexto_oculto"),
            "pilula_sabedoria": extract("pilula_sabedoria"),
            "pilula_alt1": extract("pilula_alternativa_1"),
            "pilula_alt2": extract("pilula_alternativa_2"),
            "roteiro_tiktok": extract("roteiro_tiktok_cena3"),
        }

    def _prompt_version_hash(self) -> str:
        return hashlib.md5(SYSTEM_GENERATOR.encode()).hexdigest()[:8]
