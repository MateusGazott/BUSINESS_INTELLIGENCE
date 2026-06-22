-- =========================================================================
-- SCRIPT DDL: Criação da Infraestrutura do DW COVID-19 ES
-- Disciplina: Business Intelligence — Prof. Otávio Lube
-- =========================================================================

CREATE SCHEMA IF NOT EXISTS dw;

-- -------------------------------------------------------------------------
-- 1. CAMADA STAGING (Tabela de Carga Bruta)
-- -------------------------------------------------------------------------
DROP TABLE IF EXISTS dw.stg_microdados;
CREATE TABLE dw.stg_microdados (
    id_registro SERIAL PRIMARY KEY,
    DataNotificacao VARCHAR(50),
    Municipio VARCHAR(150),
    IdadeNaDataNotificacao VARCHAR(50),
    Sexo VARCHAR(50),
    Classificacao VARCHAR(150),
    Evolucao VARCHAR(150),
    ComorbidadeCardio VARCHAR(50),
    ComorbidadeDiabetes VARCHAR(50),
    ComorbidadeObesidade VARCHAR(50),
    ComorbidadePulmao VARCHAR(50),
    ComorbidadeTabagismo VARCHAR(50),
    ComorbidadeRenal VARCHAR(50)
);

-- -------------------------------------------------------------------------
-- 2. CAMADA DE ARMAZENAMENTO (Tabelas Dimensionais)
-- -------------------------------------------------------------------------

-- Dimensão Tempo
CREATE TABLE IF NOT EXISTS dw.dim_tempo (
    sk_tempo INT PRIMARY KEY, -- Formato: YYYYMMDD
    data DATE NOT NULL,
    ano INT NOT NULL,
    mes INT NOT NULL,
    ano_mes VARCHAR(7) NOT NULL
);

-- Dimensão Localidade
CREATE TABLE IF NOT EXISTS dw.dim_localidade (
    sk_local SERIAL PRIMARY KEY,
    municipio VARCHAR(150) NOT NULL UNIQUE
);

-- Dimensão Perfil Paciente
CREATE TABLE IF NOT EXISTS dw.dim_perfil_paciente (
    sk_perfil SERIAL PRIMARY KEY,
    faixa_etaria VARCHAR(50) NOT NULL,
    sexo VARCHAR(50) NOT NULL,
    UNIQUE (faixa_etaria, sexo)
);

-- Dimensão Comorbidade
CREATE TABLE IF NOT EXISTS dw.dim_comorbidade (
    sk_como SERIAL PRIMARY KEY,
    cardio VARCHAR(50) NOT NULL,
    diabetes VARCHAR(50) NOT NULL,
    obesidade VARCHAR(50) NOT NULL,
    pulmao VARCHAR(50) NOT NULL,
    tabagismo VARCHAR(50) NOT NULL,
    renal VARCHAR(50) NOT NULL,
    UNIQUE (cardio, diabetes, obesidade, pulmao, tabagismo, renal)
);

-- -------------------------------------------------------------------------
-- 3. CAMADA DE ARMAZENAMENTO (Tabela Fato)
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw.fato_notificacao_covid (
    sk_data_notificacao INT REFERENCES dw.dim_tempo(sk_tempo),
    sk_local INT REFERENCES dw.dim_localidade(sk_local),
    sk_perfil INT REFERENCES dw.dim_perfil_paciente(sk_perfil),
    sk_como INT REFERENCES dw.dim_comorbidade(sk_como),
    qtd_notificacao INT DEFAULT 1,
    flag_confirmado INT NOT NULL,
    flag_obito_covid INT NOT NULL
);

-- -------------------------------------------------------------------------
-- 4. VALORES PADRÃO (Tratamento de Dados Ausentes/Membros Desconhecidos)
-- -------------------------------------------------------------------------
-- Permite inserção forçada de SKs negativas para chaves seriais
ALTER TABLE dw.dim_localidade DISABLE TRIGGER ALL;
ALTER TABLE dw.dim_perfil_paciente DISABLE TRIGGER ALL;
ALTER TABLE dw.dim_comorbidade DISABLE TRIGGER ALL;

INSERT INTO dw.dim_tempo (sk_tempo, data, ano, mes, ano_mes) 
VALUES (-1, '1900-01-01', 0, 0, 'N/A') ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_localidade (sk_local, municipio) 
VALUES (-1, 'DESCONHECIDO') ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_perfil_paciente (sk_perfil, faixa_etaria, sexo) 
VALUES (-1, 'DESCONHECIDO', 'DESCONHECIDO') ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_comorbidade (sk_como, cardio, diabetes, obesidade, pulmao, tabagismo, renal) 
VALUES (-1, 'Não', 'Não', 'Não', 'Não', 'Não', 'Não') ON CONFLICT DO NOTHING;

ALTER TABLE dw.dim_localidade ENABLE TRIGGER ALL;
ALTER TABLE dw.dim_perfil_paciente ENABLE TRIGGER ALL;
ALTER TABLE dw.dim_comorbidade ENABLE TRIGGER ALL;

-- Sincronizar as sequências após inserção manual do -1
SELECT setval(pg_get_serial_sequence('dw.dim_localidade', 'sk_local'), COALESCE((SELECT MAX(sk_local) FROM dw.dim_localidade), 1));
SELECT setval(pg_get_serial_sequence('dw.dim_perfil_paciente', 'sk_perfil'), COALESCE((SELECT MAX(sk_perfil) FROM dw.dim_perfil_paciente), 1));
SELECT setval(pg_get_serial_sequence('dw.dim_comorbidade', 'sk_como'), COALESCE((SELECT MAX(sk_como) FROM dw.dim_comorbidade), 1));