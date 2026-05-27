"""
Golden Rules — validação editorial do conteúdo gerado.
Todas as funções são puras e determinísticas (sem Claude API).
8 regras obrigatórias, auditáveis e testáveis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Vocabulário controlado ─────────────────────────────────────────────────────

JARGAO_ACADEMICO: list[str] = [
    "portanto", "outrossim", "todavia", "consoante", "supracitado",
    "doravante", "dessarte", "conforme exposto", "à luz de", "no âmbito",
    "mediante análise", "corrobora", "infere-se", "evidencia-se",
    "constata-se", "depreende-se", "mister", "cabe destacar", "destarte",
    "haja vista", "cumpre salientar", "em suma", "nesse diapasão",
]

# Nomes de partidos e figuras que indicam viés
PARTIDOS_E_FIGURAS: list[str] = [
    r"\bPT\b", r"\bPL\b", r"\bMDB\b", r"\bPSDB\b", r"\bPDT\b",
    r"\bRepublicanos\b", r"\bUnião Brasil\b", r"\bPSD\b", r"\bPP\b",
    r"\bLula\b", r"\bBolsonaro\b", r"\bTemer\b", r"\bDilma\b",
    r"\bCiro\b", r"\bDória\b", r"\bHaddad\b",
]

PERSONAGENS_CONCRETOS: list[str] = [
    "sua vizinha", "seu vizinho", "sua amiga", "seu amigo",
    "sua irmã", "seu irmão", "sua mãe", "seu pai", "sua avó", "seu avô",
    "a família", "o bairro", "a creche", "o posto", "a escola",
    "o jovem", "a jovem", "um morador", "uma moradora",
    "você", "a tia", "o tio", "a turma", "a comunidade",
]

PALAVRAS_LOCAIS: list[str] = [
    "oziel", "campinas", "dic", "jardim florence", "campo grande",
    "jardim oziel", "campineiro", "campineira",
]

PADROES_SERMAO: list[str] = [
    r"você deve ", r"você precisa ", r"é obrigação\b",
    r"é seu dever", r"todo cidadão deve", r"você tem que",
    r"todo mundo precisa", r"é necessário que você",
    r"você é obrigado", r"faça sua parte\b",
]

# Número: inteiros, decimais, percentuais
RE_NUMERO = re.compile(r"\b\d[\d.,]*\s*%?\b")

# Sentenças: divide por . ! ? (simplificado mas suficiente)
RE_SENTENCA = re.compile(r"[.!?]+")


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    rule_id: str
    passed: bool
    message: str
    flag: str | None = None  # flag opcional sem rejeitar


@dataclass
class ReviewResult:
    aprovado: bool
    score: float                       # 0.0–1.0
    regras_aprovadas: list[str] = field(default_factory=list)
    regras_reprovadas: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    observacoes: list[str] = field(default_factory=list)


# ── Regras individuais ─────────────────────────────────────────────────────────

def check_r1_dado_verificavel(
    contexto_oculto: str, data_points: list[dict]
) -> RuleResult:
    """R1: contexto_oculto cita pelo menos 1 dado verificável com fonte."""
    texto_lower = contexto_oculto.lower()
    numeros_no_texto = RE_NUMERO.findall(contexto_oculto)

    # Sem números: aceita se há personagem concreto ou ancoragem local
    if not numeros_no_texto:
        for palavra in PALAVRAS_LOCAIS + PERSONAGENS_CONCRETOS:
            if palavra.lower() in texto_lower:
                return RuleResult(
                    "R1", True,
                    "Narrativa concreta sem número mas com personagem/local"
                )
        if not data_points:
            return RuleResult("R1", False, "Sem dados verificáveis nem ancoragem concreta")
        # Tem data_points mas sem número no texto — OK se contexto é narrativo
        return RuleResult("R1", True, "DataPoints disponíveis; contexto é narrativo")

    if not data_points:
        # Tem números mas sem DataPoints para verificar
        # Aceita se há personagem concreto (números de ordem/quantidade cotidiana)
        for palavra in PERSONAGENS_CONCRETOS:
            if palavra.lower() in texto_lower:
                return RuleResult(
                    "R1", True,
                    "Números de contexto cotidiano com personagem concreto"
                )
        return RuleResult(
            "R1", False,
            "Números presentes mas nenhum DataPoint disponível para verificação"
        )

    # Tem números E data_points: verifica correspondência exata
    valores_dp = {str(dp["valor"]).replace(",", ".").rstrip("0").rstrip(".")
                  for dp in data_points}
    for num in numeros_no_texto:
        num_clean = num.strip().rstrip("%").replace(",", ".").rstrip("0").rstrip(".")
        if num_clean in valores_dp:
            return RuleResult("R1", True, f"Dado verificável encontrado: {num}")

    # Números não batem com DataPoints — ainda aceita se há personagem concreto
    for palavra in PERSONAGENS_CONCRETOS:
        if palavra.lower() in texto_lower:
            return RuleResult(
                "R1", True,
                "Contexto narrativo com personagem concreto (números contextuais)"
            )

    return RuleResult(
        "R1", False,
        f"Números ({numeros_no_texto[:3]}) não correspondem a DataPoints coletados"
    )


def check_r2_linguagem_bairro(contexto_oculto: str, pilula_sabedoria: str) -> RuleResult:
    """R2: Linguagem passa no teste do bairro (sem jargão acadêmico)."""
    texto_completo = f"{contexto_oculto} {pilula_sabedoria}".lower()
    encontrados = [j for j in JARGAO_ACADEMICO if j in texto_completo]
    if encontrados:
        return RuleResult(
            "R2", False,
            f"Jargão acadêmico detectado: {encontrados[:3]}"
        )
    return RuleResult("R2", True, "Linguagem aprovada no teste do bairro")


def check_r3_sem_vies_partido(contexto_oculto: str, pilula_sabedoria: str) -> RuleResult:
    """R3: Nenhum viés de partido político — foco em estruturas."""
    texto_completo = f"{contexto_oculto} {pilula_sabedoria}"
    encontrados = []
    for padrao in PARTIDOS_E_FIGURAS:
        if re.search(padrao, texto_completo, re.IGNORECASE):
            encontrados.append(padrao.replace(r"\b", ""))
    if encontrados:
        return RuleResult(
            "R3", False,
            f"Referência a partido/figura política: {encontrados[:3]}"
        )
    return RuleResult("R3", True, "Nenhum viés de partido detectado")


def check_r4_ancoragem_local(
    contexto_oculto: str, data_points: list[dict]
) -> RuleResult:
    """R4: Ancoragem local — priorizar Campinas/Oziel/DIC."""
    # Verifica se há DataPoint local (nível <= 2)
    tem_dp_local = any(dp.get("localidade_nivel", 5) <= 2 for dp in data_points)

    # Verifica se texto menciona localidade
    texto_lower = contexto_oculto.lower()
    tem_local_texto = any(p in texto_lower for p in PALAVRAS_LOCAIS)

    if tem_dp_local or tem_local_texto:
        return RuleResult("R4", True, "Ancoragem local presente")

    # Sem dados locais — warning mas não bloqueia
    return RuleResult(
        "R4", True,
        "Sem dado local de Campinas/Oziel — usando referência nacional",
        flag="baixa_ancoragem_local",
    )


def check_r5_empoderamento(pilula_sabedoria: str) -> RuleResult:
    """R5: Pílula de sabedoria é empoderamento, não sermão."""
    texto = pilula_sabedoria.lower()
    for padrao in PADROES_SERMAO:
        if re.search(padrao, texto, re.IGNORECASE):
            return RuleResult(
                "R5", False,
                f"Padrão de sermão detectado: '{padrao}'"
            )
    return RuleResult("R5", True, "Pílula com tom de empoderamento")


def check_r6_evidencia_viralizacao(meme: dict) -> RuleResult:
    """R6: Meme tem evidência de ter viralizado (fonte RSS ou fact-checker)."""
    tem_url = bool(meme.get("source_url"))
    tem_rss = bool(meme.get("source_rss"))
    tem_verif = bool(meme.get("verificacao") or meme.get("agencia"))

    if tem_url or tem_rss or tem_verif:
        return RuleResult("R6", True, "Evidência de viralização presente")

    return RuleResult(
        "R6", False,
        "Sem fonte rastreável de viralização (source_url, source_rss ou verificação)"
    )


def check_r7_formato_contexto(contexto_oculto: str) -> RuleResult:
    """R7: contexto_oculto: máximo 3 frases, personagem concreto presente."""
    # Conta frases
    frases = [f.strip() for f in RE_SENTENCA.split(contexto_oculto) if f.strip()]
    if len(frases) > 3:
        return RuleResult(
            "R7", False,
            f"contexto_oculto tem {len(frases)} frases (máximo: 3)"
        )

    # Verifica personagem concreto
    texto_lower = contexto_oculto.lower()
    tem_personagem = any(p in texto_lower for p in PERSONAGENS_CONCRETOS)
    if not tem_personagem:
        return RuleResult(
            "R7", False,
            "Falta personagem concreto no contexto_oculto "
            "(ex: 'sua vizinha', 'o bairro', 'a creche')"
        )

    return RuleResult("R7", True, f"Formato correto: {len(frases)} frase(s) com personagem concreto")


def check_r8_numeros_com_fonte(
    contexto_oculto: str, pilula_sabedoria: str, data_points: list[dict]
) -> RuleResult:
    """R8: Toda afirmação numérica tem fonte rastreável em DataPoints."""
    texto = f"{contexto_oculto} {pilula_sabedoria}"
    numeros = RE_NUMERO.findall(texto)

    if not numeros:
        return RuleResult("R8", True, "Nenhum número — regra satisfeita trivialmente")

    if not data_points:
        return RuleResult(
            "R8", False,
            f"Números presentes ({numeros[:3]}) mas nenhum DataPoint disponível para verificar"
        )

    # Normaliza DataPoint values: remove separadores de milhar, trailing zeros
    valores_dp = set()
    for dp in data_points:
        v = str(dp["valor"]).replace(".", "").replace(",", ".")  # 1.213.792 → 1213792
        valores_dp.add(v.rstrip("0").rstrip("."))
        valores_dp.add(v)  # versão completa também
        # Adiciona versão original sem normalização
        orig = str(dp["valor"]).replace(",", ".")
        valores_dp.add(orig.rstrip("0").rstrip("."))

    sem_fonte = []
    for num in numeros:
        # Normaliza o número do texto da mesma forma
        num_clean = num.strip().rstrip("%").replace(".", "").replace(",", ".")
        num_norm = num_clean.rstrip("0").rstrip(".")
        num_orig = num.strip().rstrip("%").replace(",", ".").rstrip("0").rstrip(".")

        matched = (
            num_norm in valores_dp
            or num_clean in valores_dp
            or num_orig in valores_dp
        )
        if not matched:
            sem_fonte.append(num)

    if sem_fonte:
        return RuleResult(
            "R8", False,
            f"Números sem DataPoint verificável: {sem_fonte[:3]}"
        )

    return RuleResult("R8", True, f"Todos os {len(numeros)} número(s) têm fonte rastreável")


# ── Revisor principal ──────────────────────────────────────────────────────────

REGRAS_BLOQUEANTES = {"R1", "R2", "R3", "R5", "R7", "R8"}
REGRAS_WARNING = {"R4", "R6"}

DESCRICOES = {
    "R1": "contexto_oculto cita dado verificável com fonte",
    "R2": "Linguagem passa no teste do bairro",
    "R3": "Nenhum viés de partido político",
    "R4": "Ancoragem local: Campinas/Oziel/DIC",
    "R5": "Pílula: empoderamento, não sermão",
    "R6": "Evidência de viralização",
    "R7": "contexto_oculto: ≤3 frases + personagem concreto",
    "R8": "Afirmações numéricas com fonte rastreável",
}


def revisar(
    meme: dict,
    contexto_oculto: str,
    pilula_sabedoria: str,
    data_points: list[dict],
) -> ReviewResult:
    """
    Aplica todas as 8 golden rules.
    Retorna ReviewResult com aprovado=True apenas se todas as regras bloqueantes passarem.
    """
    resultados = [
        check_r1_dado_verificavel(contexto_oculto, data_points),
        check_r2_linguagem_bairro(contexto_oculto, pilula_sabedoria),
        check_r3_sem_vies_partido(contexto_oculto, pilula_sabedoria),
        check_r4_ancoragem_local(contexto_oculto, data_points),
        check_r5_empoderamento(pilula_sabedoria),
        check_r6_evidencia_viralizacao(meme),
        check_r7_formato_contexto(contexto_oculto),
        check_r8_numeros_com_fonte(contexto_oculto, pilula_sabedoria, data_points),
    ]

    aprovadas = [r.rule_id for r in resultados if r.passed]
    reprovadas = [r.rule_id for r in resultados if not r.passed]
    flags: dict[str, bool] = {}
    observacoes: list[str] = []

    for r in resultados:
        if r.flag:
            flags[r.flag] = True
        if not r.passed:
            observacoes.append(f"{r.rule_id}: {r.message}")

    # Bloqueantes que falharam
    bloqueantes_reprovadas = [r for r in reprovadas if r in REGRAS_BLOQUEANTES]
    aprovado = len(bloqueantes_reprovadas) == 0

    score = len(aprovadas) / len(resultados)

    return ReviewResult(
        aprovado=aprovado,
        score=round(score, 2),
        regras_aprovadas=aprovadas,
        regras_reprovadas=reprovadas,
        flags=flags,
        observacoes=observacoes,
    )


def formatar_resultado(result: ReviewResult, verbose: bool = False) -> str:
    """Formata ReviewResult para exibição no terminal."""
    status = "✅ APROVADO" if result.aprovado else "❌ REPROVADO"
    linhas = [f"{status} | score: {result.score:.0%}"]
    if result.flags:
        linhas.append(f"⚠️  Flags: {', '.join(result.flags)}")
    if result.observacoes:
        linhas.append("Observações:")
        for obs in result.observacoes:
            linhas.append(f"  • {obs}")
    if verbose:
        linhas.append(f"Aprovadas: {', '.join(result.regras_aprovadas)}")
        if result.regras_reprovadas:
            linhas.append(f"Reprovadas: {', '.join(result.regras_reprovadas)}")
    return "\n".join(linhas)
