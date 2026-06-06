-- OzielMemes Pipeline — Schema PostgreSQL (Supabase)
-- Cidadania Conectada: Vozes do Oziel | Grupo Diálogos / CriaLab / FEAC

CREATE TABLE IF NOT EXISTS memes (
    id              TEXT PRIMARY KEY,
    hash_meme       TEXT UNIQUE NOT NULL,
    meme_texto      TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    formato         TEXT DEFAULT 'texto_viral',
    origem          TEXT,
    viralizou       TEXT,
    modulo          TEXT,
    dificuldade     SMALLINT DEFAULT 2,
    tags            TEXT,
    usado_no_jogo   SMALLINT DEFAULT 0,
    card_gerado     SMALLINT DEFAULT 0,
    roteiro_tiktok  SMALLINT DEFAULT 0,
    source_url      TEXT,
    source_rss      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS verificacoes (
    id               BIGSERIAL PRIMARY KEY,
    meme_id          TEXT NOT NULL REFERENCES memes(id),
    status           TEXT NOT NULL,
    fonte            TEXT NOT NULL,
    fonte_url        TEXT,
    explicacao       TEXT,
    data_verificacao TEXT,
    agencia          TEXT,
    is_current       SMALLINT DEFAULT 1,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_points (
    id               BIGSERIAL PRIMARY KEY,
    meme_id          TEXT NOT NULL REFERENCES memes(id),
    skill            TEXT NOT NULL,
    indicador        TEXT NOT NULL,
    valor            TEXT NOT NULL,
    unidade          TEXT,
    fonte            TEXT NOT NULL,
    fonte_url        TEXT,
    localidade_nome  TEXT NOT NULL,
    localidade_nivel INTEGER NOT NULL,
    ano_referencia   TEXT,
    coletado_em      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conteudo_gerado (
    id               BIGSERIAL PRIMARY KEY,
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
    is_current       SMALLINT DEFAULT 1,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS revisoes_qualidade (
    id                BIGSERIAL PRIMARY KEY,
    meme_id           TEXT NOT NULL REFERENCES memes(id),
    conteudo_id       BIGINT REFERENCES conteudo_gerado(id),
    aprovado          SMALLINT NOT NULL,
    score             REAL,
    regras_aprovadas  TEXT,
    regras_reprovadas TEXT,
    flags             TEXT,
    observacoes       TEXT,
    revisado_em       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_queue (
    id                   BIGSERIAL PRIMARY KEY,
    meme_id              TEXT REFERENCES memes(id),
    meme_hash            TEXT NOT NULL,
    meme_texto_raw       TEXT NOT NULL,
    estado               TEXT NOT NULL DEFAULT 'discovered',
    tentativas           INTEGER DEFAULT 0,
    max_tentativas       INTEGER DEFAULT 3,
    erro_ultimo          TEXT,
    metadados            TEXT,
    source_url           TEXT,
    source_rss           TEXT,
    candidato_criado_em  TIMESTAMPTZ DEFAULT NOW(),
    estado_atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    processado_em        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                BIGSERIAL PRIMARY KEY,
    iniciado_em       TIMESTAMPTZ DEFAULT NOW(),
    finalizado_em     TIMESTAMPTZ,
    memes_descobertos INTEGER DEFAULT 0,
    memes_aprovados   INTEGER DEFAULT 0,
    memes_rejeitados  INTEGER DEFAULT 0,
    erros             INTEGER DEFAULT 0,
    status            TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_memes_hash       ON memes(hash_meme);
CREATE INDEX IF NOT EXISTS idx_memes_modulo     ON memes(modulo);
CREATE INDEX IF NOT EXISTS idx_memes_categoria  ON memes(categoria);
CREATE INDEX IF NOT EXISTS idx_queue_estado     ON pipeline_queue(estado);
CREATE INDEX IF NOT EXISTS idx_queue_hash       ON pipeline_queue(meme_hash);
CREATE INDEX IF NOT EXISTS idx_datapoints_meme  ON data_points(meme_id);
CREATE INDEX IF NOT EXISTS idx_verif_meme       ON verificacoes(meme_id);
CREATE INDEX IF NOT EXISTS idx_conteudo_meme    ON conteudo_gerado(meme_id);
