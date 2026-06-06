-- OzielMemes Pipeline — Schema SQLite
-- Cidadania Conectada: Vozes do Oziel | Grupo Diálogos / CriaLab / FEAC

-- Tabela principal de memes
CREATE TABLE IF NOT EXISTS memes (
    id              TEXT PRIMARY KEY,
    hash_meme       TEXT UNIQUE NOT NULL,
    meme_texto      TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    formato         TEXT DEFAULT 'texto_viral',
    origem          TEXT,
    viralizou       TEXT,
    modulo          TEXT,
    dificuldade     INTEGER DEFAULT 2,
    tags            TEXT,           -- JSON array
    usado_no_jogo   INTEGER DEFAULT 0,
    card_gerado     INTEGER DEFAULT 0,
    roteiro_tiktok  INTEGER DEFAULT 0,
    source_url      TEXT,
    source_rss      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Verificações de fact-checking
CREATE TABLE IF NOT EXISTS verificacoes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    meme_id          TEXT NOT NULL REFERENCES memes(id),
    status           TEXT NOT NULL,   -- falso|enganoso|contexto_ausente|verdadeiro
    fonte            TEXT NOT NULL,
    fonte_url        TEXT,
    explicacao       TEXT,
    data_verificacao TEXT,
    agencia          TEXT,            -- lupa|aosfatos|boatos|g1|etc
    is_current       INTEGER DEFAULT 1,
    created_at       TEXT DEFAULT (datetime('now'))
);

-- DataPoints coletados de APIs abertas
CREATE TABLE IF NOT EXISTS data_points (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    meme_id          TEXT NOT NULL REFERENCES memes(id),
    skill            TEXT NOT NULL,
    indicador        TEXT NOT NULL,
    valor            TEXT NOT NULL,
    unidade          TEXT,
    fonte            TEXT NOT NULL,
    fonte_url        TEXT,
    localidade_nome  TEXT NOT NULL,
    localidade_nivel INTEGER NOT NULL,   -- 1=bairro 2=campinas 3=RM 4=SP 5=Brasil
    ano_referencia   TEXT,
    coletado_em      TEXT DEFAULT (datetime('now'))
);

-- Conteúdo gerado pelo Claude
CREATE TABLE IF NOT EXISTS conteudo_gerado (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    meme_id          TEXT NOT NULL REFERENCES memes(id),
    contexto_oculto  TEXT NOT NULL,
    pilula_sabedoria TEXT NOT NULL,
    objetivo_meme    TEXT,            -- o que o meme quer que você acredite + quem ganha
    pilula_alt1      TEXT,            -- alternativa 1 da pílula (ângulo distinto) p/ vídeo
    pilula_alt2      TEXT,            -- alternativa 2 da pílula (ângulo distinto) p/ vídeo
    roteiro_tiktok   TEXT,
    modelo_claude    TEXT NOT NULL,
    prompt_version   TEXT NOT NULL,
    tokens_input     INTEGER,
    tokens_output    INTEGER,
    is_current       INTEGER DEFAULT 1,
    created_at       TEXT DEFAULT (datetime('now'))
);

-- Revisões de qualidade (golden rules)
CREATE TABLE IF NOT EXISTS revisoes_qualidade (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    meme_id          TEXT NOT NULL REFERENCES memes(id),
    conteudo_id      INTEGER REFERENCES conteudo_gerado(id),
    aprovado         INTEGER NOT NULL,
    score            REAL,
    regras_aprovadas TEXT,   -- JSON array de IDs
    regras_reprovadas TEXT,  -- JSON array de IDs
    flags            TEXT,   -- JSON: {baixa_ancoragem_local: true, ...}
    observacoes      TEXT,
    revisado_em      TEXT DEFAULT (datetime('now'))
);

-- Fila do pipeline (estado persistido entre execuções)
CREATE TABLE IF NOT EXISTS pipeline_queue (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    meme_id              TEXT REFERENCES memes(id),
    meme_hash            TEXT NOT NULL,
    meme_texto_raw       TEXT NOT NULL,
    estado               TEXT NOT NULL DEFAULT 'discovered',
    -- Estados: discovered|fact_checking|enriching|generating|reviewing|approved|rejected|archived
    tentativas           INTEGER DEFAULT 0,
    max_tentativas       INTEGER DEFAULT 3,
    erro_ultimo          TEXT,
    metadados            TEXT,    -- JSON com dados intermediários
    source_url           TEXT,
    source_rss           TEXT,
    candidato_criado_em  TEXT DEFAULT (datetime('now')),
    estado_atualizado_em TEXT DEFAULT (datetime('now')),
    processado_em        TEXT
);

-- Log de execuções do pipeline
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    iniciado_em       TEXT DEFAULT (datetime('now')),
    finalizado_em     TEXT,
    memes_descobertos INTEGER DEFAULT 0,
    memes_aprovados   INTEGER DEFAULT 0,
    memes_rejeitados  INTEGER DEFAULT 0,
    erros             INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'running'   -- running|success|partial|failed
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_memes_hash       ON memes(hash_meme);
CREATE INDEX IF NOT EXISTS idx_memes_modulo     ON memes(modulo);
CREATE INDEX IF NOT EXISTS idx_memes_categoria  ON memes(categoria);
CREATE INDEX IF NOT EXISTS idx_queue_estado     ON pipeline_queue(estado);
CREATE INDEX IF NOT EXISTS idx_queue_hash       ON pipeline_queue(meme_hash);
CREATE INDEX IF NOT EXISTS idx_datapoints_meme  ON data_points(meme_id);
CREATE INDEX IF NOT EXISTS idx_verif_meme       ON verificacoes(meme_id);
CREATE INDEX IF NOT EXISTS idx_conteudo_meme    ON conteudo_gerado(meme_id);
