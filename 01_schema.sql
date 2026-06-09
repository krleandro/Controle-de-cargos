-- =============================================================================
-- SISTEMA DE GESTÃO DE CARGOS E VAGAS (QUADRO DE PESSOAL - FOPAG)
-- Prefeitura Municipal de Miracema
-- Arquivo: 01_schema.sql
-- Banco de Dados: SQLite 3
-- Descrição: DDL completo com tabelas normalizadas, constraints e view computada
--            para substituição da planilha legada "CARGOS EFETIVOS E COMISSIONADOS"
-- =============================================================================

PRAGMA journal_mode = WAL;   -- Write-Ahead Logging: leitura concorrente mais segura
PRAGMA foreign_keys = ON;    -- Obrigatório no SQLite para FKs serem respeitadas
PRAGMA encoding = 'UTF-8';


-- =============================================================================
-- BLOCO 1 — TABELA PRINCIPAL: Cargos
-- Contém todos os atributos descritivos e quantitativos de cada cargo do quadro.
-- O campo "saldo_vagas" NÃO é armazenado aqui; é sempre computado via VIEW.
-- =============================================================================

CREATE TABLE IF NOT EXISTS Cargos (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identificação do cargo
    nome                    TEXT    NOT NULL,
    codigo_fopag            TEXT    UNIQUE,          -- ex: "409", "1025"

    -- Status e provimento
    situacao                TEXT    NOT NULL DEFAULT 'Em vigor'
                                    CHECK (situacao IN ('Em vigor', 'Extinto', 'Revogado')),
    situacao_delib          TEXT    NOT NULL DEFAULT 'não enviado'
                                    CHECK (situacao_delib IN ('Enviado', 'salvo - em revisão', 'não enviado')),
    tipo_provimento         TEXT    NOT NULL
                                    CHECK (tipo_provimento IN ('Efetivo', 'Comissão')),

    -- Recrutamento
    recrutamento            TEXT    CHECK (recrutamento IN ('Amplo', 'Limitado', NULL)),
    recrutamento_obs        TEXT,                    -- campo livre de observações

    -- Requisitos de ingresso
    escolaridade            TEXT,                    -- ex: "Superior", "Ensino Médio"
    requisito_especifico    TEXT,                    -- ex: referência à Lei Federal nº 11.350/2006
    restricao_exigencia     TEXT,
    fonte_carga_horaria     TEXT,
    fonte_atribuicoes       TEXT,

    -- Regime de trabalho
    carga_horaria           TEXT    CHECK (
                                carga_horaria IN ('10','20','24','25','30','40','44',
                                                  'Não regulamentada em lei','Verificar edital', NULL)
                            ),

    -- Remuneração
    simbolo_vencimento      TEXT,                    -- ex: "P-34", "P-I"

    -- Quantitativos (base para o cálculo do saldo)
    total_previstos         INTEGER NOT NULL DEFAULT 0 CHECK (total_previstos >= 0),
    total_ocupados          INTEGER NOT NULL DEFAULT 0 CHECK (total_ocupados >= 0),

    -- Atribuições do cargo
    atribuicoes             TEXT,

    -- Auditoria
    criado_em               TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    atualizado_em           TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- Índices para as consultas mais frequentes
CREATE INDEX IF NOT EXISTS idx_cargos_situacao        ON Cargos (situacao);
CREATE INDEX IF NOT EXISTS idx_cargos_situacao_delib  ON Cargos (situacao_delib);
CREATE INDEX IF NOT EXISTS idx_cargos_tipo_provimento ON Cargos (tipo_provimento);
CREATE INDEX IF NOT EXISTS idx_cargos_codigo_fopag    ON Cargos (codigo_fopag);


-- =============================================================================
-- BLOCO 2 — TABELA RELACIONAL: FontesCargaHoraria
-- Relação 1:N com Cargos. Permite múltiplas fontes por cargo (botão "+" na UI).
-- A planilha legada armazenava isso em um único campo de texto concatenado
-- (ex: "Edital 2023 - BO 375" / "Lei 1632/2016 e Lei Federal nº 13.708/18").
-- =============================================================================

CREATE TABLE IF NOT EXISTS FontesCargaHoraria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id    INTEGER NOT NULL REFERENCES Cargos (id) ON DELETE CASCADE,

    tipo        TEXT    NOT NULL
                        CHECK (tipo IN ('Lei', 'Edital', 'Decreto', 'Outro')),
    numero      TEXT,                   -- ex: "1632", "09"
    ano         INTEGER,                -- ex: 2016, 2023
    detalhes    TEXT,                   -- descrição livre / ementa resumida

    criado_em   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_fch_cargo_id ON FontesCargaHoraria (cargo_id);


-- =============================================================================
-- BLOCO 3 — TABELA RELACIONAL: LeisPertinentes
-- Relação 1:N com Cargos. Registra o histórico legislativo de cada cargo,
-- incluindo a AÇÃO que a lei disparou (Cria / Extingue / Altera / Outros).
-- Esta tabela alimenta o MOTOR DE SALDO DE VAGAS (ver 02_business_logic.js).
-- =============================================================================

CREATE TABLE IF NOT EXISTS LeisPertinentes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cargo_id        INTEGER NOT NULL REFERENCES Cargos (id) ON DELETE CASCADE,

    -- Identificação da lei
    numero          TEXT    NOT NULL,               -- ex: "813", "2194"
    ano             INTEGER NOT NULL,               -- ex: 1999, 2024
    descricao       TEXT,                           -- ementa / observações (da coluna legada)

    -- Ação disparada pela lei sobre o quadro
    acao            TEXT    NOT NULL
                            CHECK (acao IN (
                                'Cria',         -- incrementa total_previstos
                                'Extingue',     -- decrementa total_previstos
                                'Altera',       -- alteração qualitativa (sem impacto numérico direto)
                                'Regulamenta',  -- regulamenta sem criar/extinguir vagas
                                'Fixa',         -- fixa total em valor absoluto
                                'Outro'
                            )),

    -- Impacto quantitativo na vaga (preenchido quando acao IN ('Cria','Extingue','Fixa'))
    -- Positivo = criação; Negativo = extinção; NULL = ação qualitativa (Altera/Regulamenta)
    quantidade      INTEGER DEFAULT NULL,

    -- Texto original da célula da planilha (preservado para auditoria)
    texto_original  TEXT,

    criado_em       TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_lp_cargo_id ON LeisPertinentes (cargo_id);
CREATE INDEX IF NOT EXISTS idx_lp_acao     ON LeisPertinentes (acao);


-- =============================================================================
-- BLOCO 4 — VIEW COMPUTADA: vw_SaldoVagas
-- O "Saldo de Vagas" é sempre CALCULADO, nunca armazenado como coluna estática.
-- Fórmula: saldo = total_previstos - total_ocupados
-- Nota: total_previstos já reflete os impactos acumulados das leis (gerenciado
--       pela lógica da aplicação ao inserir em LeisPertinentes — ver business logic).
-- A view centraliza o cálculo garantindo consistência em toda a aplicação.
-- =============================================================================

CREATE VIEW IF NOT EXISTS vw_SaldoVagas AS
SELECT
    c.id,
    c.nome,
    c.codigo_fopag,
    c.situacao,
    c.situacao_delib,
    c.tipo_provimento,
    c.recrutamento,
    c.escolaridade,
    c.carga_horaria,
    c.simbolo_vencimento,
    c.total_previstos,
    c.total_ocupados,
    -- Saldo computado em tempo real
    (c.total_previstos - c.total_ocupados) AS saldo_vagas,
    -- Flag de alerta: saldo negativo indica inconsistência no quadro
    CASE
        WHEN (c.total_previstos - c.total_ocupados) < 0 THEN 1
        ELSE 0
    END AS alerta_saldo_negativo,
    c.atribuicoes,
    c.criado_em,
    c.atualizado_em,
    c.recrutamento,
    c.restricao_exigencia,
    c.fonte_carga_horaria,
    c.fonte_atribuicoes
FROM Cargos c;


-- =============================================================================
-- BLOCO 5 — TRIGGER: Auditoria de atualização
-- Mantém o campo "atualizado_em" sempre sincronizado com o momento da mudança.
-- =============================================================================

CREATE TRIGGER IF NOT EXISTS trg_cargos_atualizado_em
AFTER UPDATE ON Cargos
FOR EACH ROW
BEGIN
    UPDATE Cargos
    SET    atualizado_em = datetime('now','localtime')
    WHERE  id = OLD.id;
END;


-- =============================================================================
-- BLOCO 6 — TRIGGER: Motor de Saldo por Leis (SQLite puro)
-- Ao inserir uma lei com ação 'Cria' ou 'Extingue', atualiza automaticamente
-- o campo total_previstos do cargo correspondente.
-- Ação 'Fixa' sobrescreve total_previstos com o valor absoluto informado.
-- Esta trigger complementa (não substitui) a lógica em 02_business_logic.js.
-- =============================================================================

CREATE TRIGGER IF NOT EXISTS trg_leis_atualiza_saldo
AFTER INSERT ON LeisPertinentes
FOR EACH ROW
WHEN NEW.quantidade IS NOT NULL
BEGIN
    UPDATE Cargos
    SET total_previstos =
        CASE NEW.acao
            -- Cria: soma a quantidade ao total previsto atual
            WHEN 'Cria'     THEN total_previstos + NEW.quantidade
            -- Extingue: subtrai (nunca abaixo de zero)
            WHEN 'Extingue' THEN MAX(0, total_previstos - NEW.quantidade)
            -- Fixa: define o total previsto como valor absoluto
            WHEN 'Fixa'     THEN NEW.quantidade
            -- Demais ações não alteram o quantitativo
            ELSE total_previstos
        END
    WHERE id = NEW.cargo_id;
END;


-- =============================================================================
-- BLOCO 7 — DADOS DE REFERÊNCIA (seed)
-- Configuração inicial do sistema para validação de domínios via tabela auxiliar.
-- =============================================================================

CREATE TABLE IF NOT EXISTS Dominios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria   TEXT NOT NULL,
    valor       TEXT NOT NULL,
    UNIQUE (categoria, valor)
);

INSERT OR IGNORE INTO Dominios (categoria, valor) VALUES
    ('situacao',        'Em vigor'),
    ('situacao',        'Extinto'),
    ('situacao',        'Revogado'),
    ('situacao_delib',  'Enviado'),
    ('situacao_delib',  'salvo - em revisão'),
    ('situacao_delib',  'não enviado'),
    ('tipo_provimento', 'Efetivo'),
    ('tipo_provimento', 'Comissão'),
    ('recrutamento',    'Amplo'),
    ('recrutamento',    'Limitado'),
    ('carga_horaria',   '10'),
    ('carga_horaria',   '20'),
    ('carga_horaria',   '24'),
    ('carga_horaria',   '25'),
    ('carga_horaria',   '30'),
    ('carga_horaria',   '40'),
    ('carga_horaria',   '44'),
    ('acao_lei',        'Cria'),
    ('acao_lei',        'Extingue'),
    ('acao_lei',        'Altera'),
    ('acao_lei',        'Regulamenta'),
    ('acao_lei',        'Fixa'),
    ('acao_lei',        'Outro'),
    ('fonte_ch_tipo',   'Lei'),
    ('fonte_ch_tipo',   'Edital'),
    ('fonte_ch_tipo',   'Decreto'),
    ('fonte_ch_tipo',   'Outro');
