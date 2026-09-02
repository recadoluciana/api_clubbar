-- CLUBBAR / BITBEER
-- Schema completo para MySQL 8.0.16 ou superior.
-- Execute este arquivo dentro de um banco de dados já selecionado com USE.

SET NAMES utf8mb4;

CREATE TABLE operador (
  operador_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  nmoperador VARCHAR(200) NOT NULL,
  emailoperador VARCHAR(200) NOT NULL,
  senhahashoperador VARCHAR(255) NOT NULL,
  perfil VARCHAR(30) NOT NULL DEFAULT 'ADMIN',
  sitoperador VARCHAR(15) NOT NULL DEFAULT 'ATIVO',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_operador_email (emailoperador)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- CLUBBAR / BITBEER - SCHEMA CORRIGIDO

CREATE TABLE pais (
  pais_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  cdpais      BIGINT NOT NULL,
  nmpais      VARCHAR(120) NOT NULL,
  sgpais      VARCHAR(5) NULL,
  dtcriacao   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu    DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_pais_cdpais (cdpais),
  UNIQUE KEY uk_pais_nome (nmpais)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE estado (
  estado_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  pais_id     BIGINT NOT NULL,
  cdibgeest   BIGINT NULL,
  sgestado    VARCHAR(5) NOT NULL,
  nmestado    VARCHAR(120) NOT NULL,
  dtcriacao   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu    DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_estado_pais
    FOREIGN KEY (pais_id)
    REFERENCES pais(pais_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,

  UNIQUE KEY uk_estado_ibge (cdibgeest),
  UNIQUE KEY uk_estado_pais_sigla (pais_id, sgestado),
  UNIQUE KEY uk_estado_pais_estadoid (pais_id, estado_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE cidade (
  cidade_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  pais_id     BIGINT NOT NULL,
  estado_id   BIGINT NOT NULL,
  nmcidade    VARCHAR(120) NOT NULL,
  cdibgecid   BIGINT NULL,
  dtcriacao   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu    DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_cidade_estado_pais
    FOREIGN KEY (pais_id, estado_id)
    REFERENCES estado(pais_id, estado_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,

  UNIQUE KEY uk_cidade_estado_nome (estado_id, nmcidade),
  UNIQUE KEY uk_cidade_ibge (cdibgecid),
  UNIQUE KEY uk_cidade_pais_estado_id (
    pais_id,
    estado_id,
    cidade_id
  )

) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE bairro (
  bairro_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  cidade_id   BIGINT NOT NULL,
  nmbairro    VARCHAR(120) NOT NULL,
  dtcriacao   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu    DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_bairro_cidade
    FOREIGN KEY (cidade_id)
    REFERENCES cidade(cidade_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,

  UNIQUE KEY uk_bairro_cidade_nome (cidade_id, nmbairro),
  UNIQUE KEY uk_bairro_id_cidade (bairro_id, cidade_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;


CREATE TABLE leadparceiro (
  leadparceiro_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  nmresponsavel     VARCHAR(120) NOT NULL,
  nmorganizacao     VARCHAR(160) NULL,
  telefone          VARCHAR(30) NOT NULL,
  email             VARCHAR(160) NOT NULL,

  dtcriacao         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu          DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT uq_leadparceiro_email_telefone UNIQUE (email, telefone),
  INDEX idx_leadparceiro_email (email),
  INDEX idx_leadparceiro_dtcriacao (dtcriacao)
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

CREATE TABLE leadestabelecimento (
  leadestabelecimento_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  leadparceiro_id BIGINT NOT NULL,
  nmestabelecimento VARCHAR(160) NOT NULL,
  nmresponsavel VARCHAR(120) NULL,
  telefone_responsavel VARCHAR(30) NULL,
  email_responsavel VARCHAR(160) NULL,
  tipo VARCHAR(30) NOT NULL,
  tipovenda ENUM('PRODUTOS','INGRESSOS','AMBOS') NOT NULL DEFAULT 'AMBOS',
  cpfcnpj VARCHAR(14) NULL,
  telefone VARCHAR(30) NULL,
  email VARCHAR(160) NULL,
  estado_id BIGINT NOT NULL,
  cidade_id BIGINT NOT NULL,
  cep VARCHAR(9) NULL,
  endereco VARCHAR(255) NULL,
  numero VARCHAR(20) NULL,
  complemento VARCHAR(120) NULL,
  bairro VARCHAR(120) NULL,
  mensagem TEXT NULL,
  status ENUM(
    'NOVO','CONTATADO','NEGOCIANDO','ACEITOU_PARCERIA',
    'CONVERTIDO','RECUSOU_PARCERIA'
  ) NOT NULL DEFAULT 'NOVO',
  vrtaxaprod DECIMAL(10,2) NOT NULL DEFAULT 5,
  vrtaxaing DECIMAL(10,2) NOT NULL DEFAULT 5,
  dtaceite DATETIME NULL,
  dtconversao DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_leadestabelecimento_lead FOREIGN KEY (leadparceiro_id)
    REFERENCES leadparceiro(leadparceiro_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_leadestabelecimento_estado FOREIGN KEY (estado_id) REFERENCES estado(estado_id),
  CONSTRAINT fk_leadestabelecimento_cidade FOREIGN KEY (cidade_id) REFERENCES cidade(cidade_id),
  CONSTRAINT chk_leadestabelecimento_tipo CHECK (
    tipo IN ('BAR','CASA_NOTURNA','PRODUTOR_EVENTOS','CASA_EVENTOS')
  ),
  INDEX idx_leadestabelecimento_lead (leadparceiro_id),
  INDEX idx_leadestabelecimento_status (status),
  INDEX idx_leadestabelecimento_documento (cpfcnpj)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE leadmensagem (
  leadmensagem_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  leadparceiro_id BIGINT NOT NULL,
  leadestabelecimento_id BIGINT NOT NULL,
  origem ENUM('CLUBBAR', 'LEAD') NOT NULL,
  mensagem TEXT NOT NULL,
  lida CHAR(1) NOT NULL DEFAULT 'N',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_leadmensagem_lead
    FOREIGN KEY (leadparceiro_id)
    REFERENCES leadparceiro(leadparceiro_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,
  CONSTRAINT fk_leadmensagem_estabelecimento FOREIGN KEY (leadestabelecimento_id)
    REFERENCES leadestabelecimento(leadestabelecimento_id),

  CONSTRAINT chk_leadmensagem_lida
    CHECK (lida IN ('S', 'N')),

  INDEX idx_leadmensagem_lead_data (
    leadparceiro_id,
    dtcriacao
  ),
  INDEX idx_leadmensagem_estabelecimento (leadestabelecimento_id)
) ENGINE=InnoDB
DEFAULT CHARACTER SET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

CREATE TABLE leadagendamento (
  leadagendamento_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  leadparceiro_id BIGINT NOT NULL,
  leadestabelecimento_id BIGINT NOT NULL,

  tipo ENUM(
    'DEMONSTRACAO',
    'LIGACAO',
    'REUNIAO_ONLINE',
    'VISITA'
  ) NOT NULL,

  dtagendamento DATETIME NOT NULL,
  observacao VARCHAR(500) NULL,

  status ENUM(
    'PENDENTE',
    'CONFIRMADO',
    'RECUSADO',
    'REALIZADO',
    'CANCELADO'
  ) NOT NULL DEFAULT 'PENDENTE',

  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_leadagendamento_lead
    FOREIGN KEY (leadparceiro_id)
    REFERENCES leadparceiro(leadparceiro_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,
  CONSTRAINT fk_leadagendamento_estabelecimento FOREIGN KEY (leadestabelecimento_id)
    REFERENCES leadestabelecimento(leadestabelecimento_id),

  INDEX idx_leadagendamento_lead_data (
    leadparceiro_id,
    dtagendamento
  ),
  INDEX idx_leadagendamento_estabelecimento (leadestabelecimento_id)
) ENGINE=InnoDB
DEFAULT CHARACTER SET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

CREATE TABLE leadmaterial (
  leadmaterial_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  leadparceiro_id BIGINT NOT NULL,
  leadestabelecimento_id BIGINT NOT NULL,

  titulo VARCHAR(160) NOT NULL,
  descricao VARCHAR(500) NULL,
  tipo ENUM(
    'APRESENTACAO',
    'PROPOSTA',
    'CONTRATO',
    'VIDEO',
    'OUTRO'
  ) NOT NULL,

  urlarquivo VARCHAR(500) NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_leadmaterial_lead
    FOREIGN KEY (leadparceiro_id)
    REFERENCES leadparceiro(leadparceiro_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,
  CONSTRAINT fk_leadmaterial_estabelecimento FOREIGN KEY (leadestabelecimento_id)
    REFERENCES leadestabelecimento(leadestabelecimento_id),

  INDEX idx_leadmaterial_lead (
    leadparceiro_id,
    dtcriacao
  ),
  INDEX idx_leadmaterial_estabelecimento (leadestabelecimento_id)
) ENGINE=InnoDB
DEFAULT CHARACTER SET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

CREATE TABLE leadacesso (
  leadacesso_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  leadparceiro_id BIGINT NOT NULL,

  tokenhash CHAR(64) NOT NULL,
  dtvalidade DATETIME NOT NULL,
  dtultimoacesso DATETIME NULL,
  revogado CHAR(1) NOT NULL DEFAULT 'N',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uk_leadacesso_tokenhash (tokenhash),

  CONSTRAINT fk_leadacesso_lead
    FOREIGN KEY (leadparceiro_id)
    REFERENCES leadparceiro(leadparceiro_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,

  CONSTRAINT chk_leadacesso_revogado
    CHECK (revogado IN ('S', 'N'))
) ENGINE=InnoDB
DEFAULT CHARACTER SET=utf8mb4
COLLATE=utf8mb4_unicode_ci;

CREATE TABLE organizacao (
    organizacao_id BIGINT NOT NULL AUTO_INCREMENT,

    -- Identificação
    nmorganizacao VARCHAR(120) NOT NULL,
    nmresponsavelprincipal VARCHAR(120) NULL,

    -- Contato administrativo
    emailorganizacao VARCHAR(255) NOT NULL,
    telorganizacao VARCHAR(25) NOT NULL,
    tipooperacao VARCHAR(30) NULL,
    -- Controle
    sitorganizacao VARCHAR(15) NOT NULL DEFAULT 'ATIVA',
    leadparceiro_id BIGINT NULL,

    dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtultatu DATETIME NULL
        DEFAULT NULL
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (organizacao_id),

    UNIQUE KEY uk_organizacao_leadparceiro (
      leadparceiro_id
    ),

    KEY idx_organizacao_nome (
        nmorganizacao
    ),

    KEY idx_organizacao_situacao (
        sitorganizacao
    ),

    CONSTRAINT fk_organizacao_leadparceiro
        FOREIGN KEY (leadparceiro_id)
        REFERENCES leadparceiro(leadparceiro_id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_organizacao_situacao
        CHECK (
            sitorganizacao IN (
                'ATIVA',
                'INATIVA',
                'BLOQUEADA'
            )
        )
)
ENGINE = InnoDB
DEFAULT CHARACTER SET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

CREATE TABLE loja (
  loja_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  leadestabelecimento_id BIGINT NULL,
  titularfinanceiro_id BIGINT NULL,
  nmloja         VARCHAR(120) NOT NULL,
  endloja        VARCHAR(255) NULL,
  nrceploja      VARCHAR(9) NULL,
  nrendeloja     VARCHAR(20) NULL,
  dsrefeloja     VARCHAR(255) NULL,
  dsinstaloja    VARCHAR(255) NULL,
  dsbairroloja   VARCHAR(120) NULL,
  sitloja        VARCHAR(15) NOT NULL DEFAULT 'ATIVA',
  aberto24x7     CHAR(1) NOT NULL DEFAULT 'N',
  dshorarioloja  VARCHAR(255) NULL,
  nrtelloja      VARCHAR(25) NULL,
  qtcpdloja      INT NULL,
  nrdiavalidade  BIGINT NOT NULL DEFAULT 90,
  idvalidadeprod CHAR(1) NOT NULL DEFAULT 'S',
  estado_id      BIGINT NULL,
  cidade_id      BIGINT NULL,
  tipoloja       VARCHAR(30) NULL,
  atendimentofisico CHAR(1) NOT NULL DEFAULT 'S',
  vendaprodutos  CHAR(1) NOT NULL DEFAULT 'S',
  vendaingressos CHAR(1) NOT NULL DEFAULT 'S',
  urllogoloja    VARCHAR(255) NULL,
  urlfachadaloja VARCHAR(255) NULL,
  vrtaxaprod     DECIMAL(10,2) NOT NULL DEFAULT 5,
  vrtaxaing      DECIMAL(10,2) NOT NULL DEFAULT 5,
  dsestiloloja   VARCHAR(255) NULL,
  dtcriacao      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu       DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_loja_org
    FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_loja_cidade
    FOREIGN KEY (cidade_id) REFERENCES cidade(cidade_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_loja_estado
    FOREIGN KEY (estado_id) REFERENCES estado(estado_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_loja_leadestabelecimento
    FOREIGN KEY (leadestabelecimento_id) REFERENCES leadestabelecimento(leadestabelecimento_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  UNIQUE KEY uk_loja_leadestabelecimento (leadestabelecimento_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_loja_org ON loja(organizacao_id);
CREATE INDEX idx_loja_estado ON loja(estado_id);
ALTER TABLE loja
  ADD UNIQUE KEY uk_loja_org_id (organizacao_id, loja_id);

ALTER TABLE loja
  ADD CONSTRAINT chk_aberto24x7 CHECK (aberto24x7 IN ('S', 'N'));

ALTER TABLE loja
  ADD CONSTRAINT chk_idvalidadeprod CHECK (idvalidadeprod IN ('S', 'N'));
ALTER TABLE loja
  ADD CONSTRAINT chk_loja_capacidade CHECK (qtcpdloja IS NULL OR qtcpdloja > 0);

ALTER TABLE loja
  ADD CONSTRAINT chk_loja_atendimento_fisico
    CHECK (atendimentofisico IN ('S', 'N')),
  ADD CONSTRAINT chk_loja_venda_produtos
    CHECK (vendaprodutos IN ('S', 'N')),
  ADD CONSTRAINT chk_loja_venda_ingressos
    CHECK (vendaingressos IN ('S', 'N'));

CREATE TABLE lojaconteudo (
  lojaconteudo_id BIGINT AUTO_INCREMENT PRIMARY KEY, loja_id BIGINT NOT NULL,
  dsdetalhadaloja TEXT NULL, fotos JSON NULL, publicacoes JSON NULL, videos JSON NULL, configuracoes JSON NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_lojaconteudo_loja UNIQUE (loja_id),
  CONSTRAINT fk_lojaconteudo_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE lojapoliticaingresso (
  lojapoliticaingresso_id BIGINT AUTO_INCREMENT PRIMARY KEY, loja_id BIGINT NOT NULL,
  dspoliticaingresso TEXT NULL, urlmapaingressos VARCHAR(255) NULL, dsmapaingressos TEXT NULL,
  dsorientacoesacesso TEXT NULL, configuracoes JSON NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_lojapoliticaingresso_loja UNIQUE (loja_id),
  CONSTRAINT fk_lojapoliticaingresso_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- MySQL 8+
-- Uma loja possui no máximo um horário para cada dia da semana.
-- dia_semana: 1 = segunda-feira ... 7 = domingo.

CREATE TABLE lojahorario (
    lojahorario_id BIGINT NOT NULL AUTO_INCREMENT,
    loja_id BIGINT NOT NULL,
    diasemana TINYINT UNSIGNED NOT NULL,
    fechado BOOLEAN NOT NULL DEFAULT FALSE,
    horaabertura TIME NULL,
    horafechamento TIME NULL,
    fechadiaseguinte BOOLEAN NOT NULL DEFAULT FALSE,
    dtcriacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtalteracao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (lojahorario_id),
    CONSTRAINT uq_lojahorario_dia UNIQUE (loja_id, diasemana),
    CONSTRAINT fk_lojahorario_loja
        FOREIGN KEY (loja_id) REFERENCES loja (loja_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT ck_lojahorario_dia
        CHECK (diasemana BETWEEN 1 AND 7),
    CONSTRAINT ck_lojahorario_campos
        CHECK (
            (fechado = TRUE
                AND horaabertura IS NULL
                AND horafechamento IS NULL
                AND fechadiaseguinte = FALSE)
            OR
            (fechado = FALSE
                AND horaabertura IS NOT NULL
                AND horafechamento IS NOT NULL
                AND horaabertura <> horafechamento)
        )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE cliente (
  cliente_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  nmcliente      VARCHAR(120) NOT NULL,
  emailcliente   VARCHAR(160) NOT NULL,
  senhahashcli   VARCHAR(255) NOT NULL,

  sitcliente     VARCHAR(15) NOT NULL DEFAULT 'ATIVO',
  emailconf      CHAR(1) NOT NULL DEFAULT 'N',
  cliente_padrao CHAR(1) NOT NULL DEFAULT 'N',

  nrtelcliente   VARCHAR(25) NULL,
  nrcpfcliente   CHAR(11) NULL,

  endcliente     VARCHAR(150) NULL,
  nrendcliente   VARCHAR(20) NULL,
  complcliente   VARCHAR(80) NULL,
  bairrocliente  VARCHAR(80) NULL,
  cepcliente     VARCHAR(20) NULL,
  cidadecliente  VARCHAR(100) NULL,
  ufcliente      CHAR(2) NULL,
  idcidadeibge   INT NULL,

  dtnascimento   DATE NULL,

  pais_id        BIGINT NULL,
  estado_id      BIGINT NULL,
  cidade_id      BIGINT NULL,

  idclienteasaas VARCHAR(100) NULL,

  dtcriacao      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu       DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_cliente_email (emailcliente),

  UNIQUE KEY uk_cliente_cpf (nrcpfcliente),

  CONSTRAINT fk_cliente_estado_pais
    FOREIGN KEY (pais_id, estado_id)
    REFERENCES estado(pais_id, estado_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_cliente_cidade_estado_pais
    FOREIGN KEY (pais_id, estado_id, cidade_id)
    REFERENCES cidade(pais_id, estado_id, cidade_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_cliente_emailconf
    CHECK (emailconf IN ('S', 'N')),

  CONSTRAINT chk_cliente_padrao
    CHECK (cliente_padrao IN ('S', 'N')),

  CONSTRAINT chk_cliente_localizacao
    CHECK (
      (pais_id IS NULL AND estado_id IS NULL AND cidade_id IS NULL)
      OR
      (pais_id IS NOT NULL AND estado_id IS NOT NULL AND cidade_id IS NOT NULL)
    )

) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_cliente_asaas       ON cliente(idclienteasaas);

CREATE TABLE titularfinanceiro (
  titularfinanceiro_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  tipotitular ENUM('PF','PJ') NOT NULL,
  cpfcnpj VARCHAR(14) NOT NULL,
  nmrazaosocial VARCHAR(160) NOT NULL,
  nmfantasia VARCHAR(160) NULL,
  dtnascimento DATE NULL,
  email VARCHAR(255) NOT NULL,
  telefone VARCHAR(25) NOT NULL,
  cep VARCHAR(9) NOT NULL,
  endereco VARCHAR(255) NOT NULL,
  numero VARCHAR(20) NOT NULL,
  complemento VARCHAR(120) NULL,
  bairro VARCHAR(120) NOT NULL,
  cidade_id BIGINT NOT NULL,
  estado_id BIGINT NOT NULL,
  vrfaturamentomensal DECIMAL(12,2) NOT NULL DEFAULT 0,
  asaas_account_id VARCHAR(100) NULL,
  asaas_wallet_id VARCHAR(100) NULL,
  asaas_api_key_criptografada TEXT NULL,
  status_asaas VARCHAR(30) NOT NULL DEFAULT 'NAO_INICIADO',
  onboarding_url TEXT NULL,
  dtultimaverificacao DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_titularfinanceiro_organizacao (organizacao_id),
  CONSTRAINT fk_titularfinanceiro_organizacao FOREIGN KEY (organizacao_id)
    REFERENCES organizacao(organizacao_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_titularfinanceiro_cidade FOREIGN KEY (cidade_id) REFERENCES cidade(cidade_id),
  CONSTRAINT fk_titularfinanceiro_estado FOREIGN KEY (estado_id) REFERENCES estado(estado_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE loja
  ADD CONSTRAINT fk_loja_titularfinanceiro
    FOREIGN KEY (titularfinanceiro_id) REFERENCES titularfinanceiro(titularfinanceiro_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE INDEX idx_loja_titularfinanceiro ON loja(titularfinanceiro_id);

CREATE TABLE leadestabelecimentocontrato (
  leadestabelecimentocontrato_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  leadestabelecimento_id BIGINT NOT NULL,
  titularfinanceiro_id BIGINT NULL,
  versao VARCHAR(30) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'RASCUNHO',
  vrtaxaprod DECIMAL(10,2) NOT NULL DEFAULT 5,
  vrtaxaing DECIMAL(10,2) NOT NULL DEFAULT 5,
  conteudocontrato TEXT NOT NULL,
  hashdocumento CHAR(64) NULL,
  nmsignatario VARCHAR(160) NULL,
  cpfcnpjsignatario VARCHAR(14) NULL,
  ipaceite VARCHAR(45) NULL,
  dtaceite DATETIME NULL,
  dtdisponibilizacao DATETIME NULL,
  dtinicio DATETIME NULL,
  dtfim DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_leadestabelecimentocontrato_estabelecimento FOREIGN KEY (leadestabelecimento_id)
    REFERENCES leadestabelecimento(leadestabelecimento_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_leadestabelecimentocontrato_titular FOREIGN KEY (titularfinanceiro_id)
    REFERENCES titularfinanceiro(titularfinanceiro_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_leadestabelecimentocontrato_status CHECK (
    status IN ('RASCUNHO','ENVIADO','ACEITO','RECUSADO','CANCELADO','EXPIRADO')
  ),
  INDEX idx_leadestabelecimentocontrato_estabelecimento (leadestabelecimento_id),
  INDEX idx_leadestabelecimentocontrato_status (status)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lojaasaas (
  lojaasaas_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  venda_id BIGINT NULL,
  ambiente VARCHAR(20) NOT NULL,
  asaas_account_id VARCHAR(100) NULL,
  asaas_wallet_id VARCHAR(100) NOT NULL,
  asaas_api_key_criptografada TEXT NOT NULL,
  webhook_token_hash CHAR(64) NOT NULL,
  statusintegracao VARCHAR(20) NOT NULL DEFAULT 'ATIVA',
  dtcriacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtalteracao TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_lojaasaas_loja_ambiente (loja_id, ambiente),
  UNIQUE KEY uq_lojaasaas_webhook_token_hash (webhook_token_hash),
  CONSTRAINT fk_lojaasaas_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id),
  CONSTRAINT fk_lojaasaas_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE clienteasaas (
  clienteasaas_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  cliente_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  asaas_customer_id VARCHAR(100) NOT NULL,
  dtcriacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtalteracao TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_clienteasaas_cliente_loja (cliente_id, loja_id),
  CONSTRAINT fk_clienteasaas_cliente FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id) ON DELETE CASCADE,
  CONSTRAINT fk_clienteasaas_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE clisenha (
  clisenha_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  cliente_id BIGINT NOT NULL,
  codigo VARCHAR(10) NOT NULL,
  expiracao DATETIME NOT NULL,
  usado CHAR(1) NOT NULL DEFAULT 'N',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_clisenha
    FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id)
    ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE usuario (
  usuario_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id  BIGINT NOT NULL,
  loja_id         BIGINT NULL,
  nmusuario       VARCHAR(200) NOT NULL,
  emailuser       VARCHAR(200) NOT NULL,
  senhahashuser   VARCHAR(255) NOT NULL,
  dscargo         ENUM(
    'SUPERADMIN',
    'ADMIN',
    'GERENTE',
    'CAIXA',
    'TOTEM',
    'BARMAN',
    'GARCOM',
    'PORTEIRO'
  ) NOT NULL DEFAULT 'BARMAN',

  situsuario      VARCHAR(15) NOT NULL DEFAULT 'ATIVO',
  dtcriacao       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu        DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_usuario_org
    FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_usuario_loja
    FOREIGN KEY (organizacao_id, loja_id)
    REFERENCES loja(organizacao_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  UNIQUE KEY uk_usuario_email (emailuser),
  INDEX idx_usuario_loja (loja_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE auditoria (
  auditoria_id BIGINT NOT NULL AUTO_INCREMENT,
  tabela VARCHAR(100) NOT NULL,
  registro_id VARCHAR(255) NOT NULL,
  acao VARCHAR(15) NOT NULL,
  ator_tipo VARCHAR(20) NOT NULL DEFAULT 'SISTEMA',
  ator_id VARCHAR(100) NULL,
  usuario_id BIGINT NULL,
  operador_id BIGINT NULL,
  ator_nome VARCHAR(200) NOT NULL,
  ator_email VARCHAR(200) NULL,
  dados_anteriores JSON NULL,
  dados_novos JSON NULL,
  metodo_http VARCHAR(10) NULL,
  rota VARCHAR(500) NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (auditoria_id),
  INDEX idx_auditoria_registro (tabela, registro_id, dtcriacao),
  INDEX idx_auditoria_usuario (usuario_id, dtcriacao),
  INDEX idx_auditoria_operador (operador_id, dtcriacao),
  CONSTRAINT fk_auditoria_usuario FOREIGN KEY (usuario_id)
    REFERENCES usuario(usuario_id) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_auditoria_operador FOREIGN KEY (operador_id)
    REFERENCES operador(operador_id) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT chk_auditoria_acao
    CHECK (acao IN ('INCLUSAO', 'ALTERACAO', 'EXCLUSAO')),
  CONSTRAINT chk_auditoria_ator_tipo
    CHECK (ator_tipo IN ('USUARIO', 'OPERADOR', 'CLIENTE', 'LEAD', 'SISTEMA'))
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE usuariosenha (
  usuariosenha_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  usuario_id BIGINT NOT NULL,
  codigohash VARCHAR(255) NOT NULL,
  expiracao DATETIME NOT NULL,
  usado CHAR(1) NOT NULL DEFAULT 'N',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_usuariosenha_usuario (usuario_id),
  CONSTRAINT fk_usuariosenha_usuario
    FOREIGN KEY (usuario_id) REFERENCES usuario(usuario_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE categoria (
  categoria_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id   BIGINT NOT NULL,
  loja_id          BIGINT NOT NULL,
  nmcategoria      VARCHAR(120) NOT NULL,
  sitcategoria     ENUM('ATIVA','INATIVA') NOT NULL DEFAULT 'ATIVA',
  idordcategoria   BIGINT NOT NULL DEFAULT 1,
  dtcriacao        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu         DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_categoria_loja
    FOREIGN KEY (organizacao_id, loja_id)
    REFERENCES loja(organizacao_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_categoria_loja ON categoria(loja_id);

ALTER TABLE categoria
  ADD UNIQUE KEY uk_categoria_nome (loja_id, nmcategoria);

ALTER TABLE categoria
  ADD UNIQUE KEY uk_categoria_composta (organizacao_id, loja_id, categoria_id);

CREATE TABLE produto (
  produto_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id   BIGINT NOT NULL,
  loja_id          BIGINT NOT NULL,
  categoria_id     BIGINT NULL,
  nmproduto        VARCHAR(100) NOT NULL,
  dsproduto        VARCHAR(255) NULL,
  idtipoproduto    ENUM('I','P') NOT NULL DEFAULT 'P',
  vrprecoprod      DECIMAL(10,2) NOT NULL,
  sitproduto       ENUM('ATIVO','INATIVO') NOT NULL DEFAULT 'ATIVO',
  skuproduto       VARCHAR(100) NULL,
  dtcriacao        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu         DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  lote_id          BIGINT NULL,
  urlfotoproduto   VARCHAR(255) NULL,
  tipodesconto     ENUM('NENHUM','PERCENTUAL','VALOR') NOT NULL DEFAULT 'NENHUM',
  vrdesconto       DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  pccashback       DECIMAL(10,2) NULL,
  dtinidesconto    DATETIME NULL,
  dtfimdesconto    DATETIME NULL,

  UNIQUE KEY uk_produto_id_lote (produto_id, lote_id),

  CONSTRAINT fk_produto_loja
    FOREIGN KEY (organizacao_id, loja_id)
    REFERENCES loja(organizacao_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_produto_categoria_composta
    FOREIGN KEY (organizacao_id, loja_id, categoria_id)
    REFERENCES categoria(organizacao_id, loja_id, categoria_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_produto_preco
    CHECK (vrprecoprod >= 0),

  CONSTRAINT chk_produto_desconto
    CHECK (vrdesconto >= 0),
    CHECK (pccashback IS NULL OR (pccashback >= 0 AND pccashback <= 100))
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_produto_org_loja_sit
  ON produto(organizacao_id, loja_id, sitproduto);

CREATE INDEX idx_produto_org_loja_sit_nome
  ON produto(organizacao_id, loja_id, sitproduto, nmproduto);

CREATE INDEX idx_produto_categoria
  ON produto(categoria_id);

CREATE UNIQUE INDEX uq_produto_lote
  ON produto(organizacao_id, loja_id, lote_id);

CREATE TABLE carrinho (
  carrinho_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id   BIGINT NOT NULL,
  loja_id          BIGINT NOT NULL,
  cliente_id       BIGINT NOT NULL,
  usuario_id       BIGINT NULL,
  sitcarrinho      ENUM('ABERTO','FECHADO') NOT NULL DEFAULT 'ABERTO',
  dtcriacao        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu         DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_carrinho_loja_org
    FOREIGN KEY (organizacao_id, loja_id)
    REFERENCES loja(organizacao_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_carrinho_cliente
    FOREIGN KEY (cliente_id)
    REFERENCES cliente(cliente_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_carrinho_usuario
    FOREIGN KEY (usuario_id)
    REFERENCES usuario(usuario_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  UNIQUE KEY uk_carrinho_venda (
    carrinho_id,
    organizacao_id,
    loja_id,
    cliente_id
  ),

  UNIQUE KEY uk_carrinho_checkout (
    carrinho_id,
    cliente_id,
    loja_id
  )
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_carrinho_aberto_cliente_loja
  ON carrinho(organizacao_id, loja_id, cliente_id, sitcarrinho);

CREATE INDEX idx_carrinho_usuario
  ON carrinho(usuario_id);

CREATE TABLE itcarrinho (
  itcarrinho_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  carrinho_id      BIGINT NULL,
  reserva_ingresso_id BIGINT NULL,
  produto_id       BIGINT NOT NULL,
  lote_id          BIGINT NULL,
  qtitcarrinho     INT NOT NULL DEFAULT 1,
  dsobsitcar       VARCHAR(255) NULL,
  nmparticipante   VARCHAR(150) NULL,
  cpfparticipante  VARCHAR(14) NULL,
  dtcriacao        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu         DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_itcarrinho_carrinho
    FOREIGN KEY (carrinho_id)
    REFERENCES carrinho(carrinho_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_itcarrinho_produto
    FOREIGN KEY (produto_id)
    REFERENCES produto(produto_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_itcarrinho_qt
    CHECK (qtitcarrinho = 1)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_itcarrinho_carrinho
  ON itcarrinho(carrinho_id);

CREATE INDEX idx_itcarrinho_carrinho_produto
  ON itcarrinho(carrinho_id, produto_id);

CREATE INDEX idx_itcarrinho_lote
  ON itcarrinho(lote_id);

CREATE INDEX idx_itcarrinho_carrinho_dt
  ON itcarrinho(carrinho_id, dtcriacao, itcarrinho_id);

CREATE TABLE venda (
  venda_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id   BIGINT NOT NULL,
  loja_id          BIGINT NOT NULL,
  cliente_id       BIGINT NULL,
  usuario_id       BIGINT NULL,
  carrinho_id      BIGINT NULL,
  reserva_ingresso_id BIGINT NULL,
  tipovenda        ENUM('PRODUTO','INGRESSO') NOT NULL,
  dsplataforma     ENUM('ANDROID','TOTEM','IOS','WEB','OUTROS') NOT NULL DEFAULT 'OUTROS',
  sitvenda         ENUM('PENDENTE','PAGA','CANCELADA') NOT NULL DEFAULT 'PENDENTE',
  totalvenda       DECIMAL(10,2) NOT NULL DEFAULT 0,
  dtcriacao        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu         DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_venda_carrinho
    FOREIGN KEY (
      carrinho_id,
      organizacao_id,
      loja_id,
      cliente_id
    )
    REFERENCES carrinho(
      carrinho_id,
      organizacao_id,
      loja_id,
      cliente_id
    )
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  UNIQUE KEY uk_venda_carrinho (carrinho_id),
  UNIQUE KEY uk_venda_reserva_ingresso (reserva_ingresso_id),

  CONSTRAINT fk_venda_usuario
    FOREIGN KEY (usuario_id)
    REFERENCES usuario(usuario_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT chk_venda_total CHECK (totalvenda >= 0),
  CONSTRAINT chk_venda_origem CHECK ((carrinho_id IS NULL) <> (reserva_ingresso_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_venda_loja_cliente_data
  ON venda(organizacao_id, loja_id, cliente_id, dtcriacao);

CREATE INDEX idx_venda_cliente_data
  ON venda(cliente_id, dtcriacao);

CREATE INDEX idx_venda_usuario_data
  ON venda(usuario_id, dtcriacao);

CREATE TABLE itvenda (
  itvenda_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  venda_id              BIGINT NOT NULL,
  tipoitem              ENUM('PRODUTO','INGRESSO') NOT NULL,
  produto_id            BIGINT NULL,
  lote_id               BIGINT NULL,
  qtitvenda             INT NOT NULL DEFAULT 1,
  vrunititvenda         DECIMAL(10,2) NOT NULL,
  identregaitvenda      ENUM('SIM','NAO') NOT NULL DEFAULT 'NAO',
  dtentregaitvenda      DATETIME NULL,
  dtexpiraitvenda       DATE NULL,
  userentregaitvenda    BIGINT NULL,
  nmuserentregaitvenda  VARCHAR(100) NULL,
  dsobsitvenda          VARCHAR(255) NULL,
  qrtokenitvenda        VARCHAR(120) NOT NULL,
  nmparticipante        VARCHAR(150) NULL,
  cpfparticipante       VARCHAR(14) NULL,
  pctaxaitvenda         DECIMAL(5,2) NOT NULL DEFAULT 5.00,
  vrtaxaitvenda         DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  sititvenda            ENUM('ATIVO','CANCELAMENTO_SOLICITADO','CANCELADO') NOT NULL DEFAULT 'ATIVO',
  dtcancelamento        DATETIME NULL,
  vrreembolso           DECIMAL(10,2) NULL,
  idreembolso           VARCHAR(120) NULL,
  dtcriacao             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu              DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_itvenda_venda
    FOREIGN KEY (venda_id)
    REFERENCES venda(venda_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_itvenda_produto
    FOREIGN KEY (produto_id)
    REFERENCES produto(produto_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT fk_itvenda_user_entrega
    FOREIGN KEY (userentregaitvenda)
    REFERENCES usuario(usuario_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_itvenda_qt
    CHECK (qtitvenda = 1),

  CONSTRAINT chk_itvenda_taxa
    CHECK (
      pctaxaitvenda BETWEEN 0 AND 100
      AND vrtaxaitvenda >= 0
    ),

  CONSTRAINT chk_itvenda_origem
    CHECK (
      (tipoitem = 'PRODUTO' AND produto_id IS NOT NULL AND lote_id IS NULL)
      OR
      (tipoitem = 'INGRESSO' AND produto_id IS NULL AND lote_id IS NOT NULL)
    ),

  CONSTRAINT uq_itvenda_qrtoken
    UNIQUE (qrtokenitvenda)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_itvenda_venda
  ON itvenda(venda_id);

CREATE INDEX idx_itvenda_lote
  ON itvenda(lote_id);

CREATE INDEX idx_itvenda_entrega
  ON itvenda(identregaitvenda, dtentregaitvenda);

CREATE TABLE reserva_ingresso (
  reserva_ingresso_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL, loja_id BIGINT NOT NULL, cliente_id BIGINT NOT NULL,
  evento_id BIGINT NOT NULL, lote_id BIGINT NOT NULL,
  venda_id BIGINT NULL, qtreservada INT NOT NULL,
  vrunitario DECIMAL(10,2) NOT NULL, pctaxa DECIMAL(10,2) NOT NULL DEFAULT 0,
  vrtaxa DECIMAL(10,2) NOT NULL DEFAULT 0, vrtotal DECIMAL(10,2) NOT NULL,
  sitreserva ENUM('PREENCHENDO','AGUARDANDO_PAGAMENTO','CONFIRMADA','EXPIRADA','CANCELADA') NOT NULL DEFAULT 'PREENCHENDO',
  dtexpiracao DATETIME NOT NULL, dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reserva_venda (venda_id),
  INDEX idx_reserva_lote_status_expiracao (lote_id, sitreserva, dtexpiracao),
  INDEX idx_reserva_cliente (cliente_id, dtcriacao),
  FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id),
  FOREIGN KEY (loja_id) REFERENCES loja(loja_id), FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id),
  FOREIGN KEY (venda_id) REFERENCES venda(venda_id),
  CHECK (qtreservada > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE reserva_ingresso_participante (
  reserva_ingresso_participante_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  reserva_ingresso_id BIGINT NOT NULL, ordem INT NOT NULL,
  nmparticipante VARCHAR(150) NOT NULL, cpfparticipante VARCHAR(11) NOT NULL,
  itvenda_id BIGINT NULL, dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reserva_participante_ordem (reserva_ingresso_id, ordem),
  INDEX idx_reserva_participante_cpf (cpfparticipante),
  FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id) ON DELETE CASCADE,
  FOREIGN KEY (itvenda_id) REFERENCES itvenda(itvenda_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE venda ADD CONSTRAINT fk_venda_reserva_ingresso
  FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id);

CREATE TABLE pagvenda (
  pagvenda_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  venda_id              BIGINT NOT NULL,
  dsmetodopag           VARCHAR(40) NOT NULL,
  vrpagvenda            DECIMAL(10,2) NOT NULL,
  sitpagvenda           ENUM('PENDENTE','PAGO','CANCELADO') NOT NULL DEFAULT 'PENDENTE',
  idtransacaopagvenda   VARCHAR(120) NULL,
  dtconftranspagvenda   DATETIME NULL,
  dtcriacao             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu              DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_pagamento_venda
    FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

ALTER TABLE pagvenda
  ADD COLUMN provedor VARCHAR(40) NOT NULL DEFAULT 'ASAAS',
  ADD COLUMN reference_id VARCHAR(80) NULL,
  ADD COLUMN checkout_id VARCHAR(120) NULL,
  ADD COLUMN pay_url VARCHAR(255) NULL;

CREATE INDEX idx_pagvenda
  ON pagvenda(venda_id);

CREATE INDEX idx_sitpagvenda
  ON pagvenda(sitpagvenda, dtcriacao);

CREATE INDEX idx_pagvenda_reference
  ON pagvenda(reference_id);

CREATE TABLE atracao (
  atracao_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id      BIGINT NOT NULL,
  nmatracao           VARCHAR(120) NOT NULL,
  dsestilomusical     VARCHAR(255) NULL,
  urlbanneratracao    VARCHAR(255) NULL,
  dtcriacao           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu            DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_atracao_organizacao
    FOREIGN KEY (organizacao_id)
    REFERENCES organizacao(organizacao_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  INDEX idx_atracao_organizacao_nome (
    organizacao_id,
    nmatracao
  )
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE atracaodescricao (
  atracao_id    BIGINT PRIMARY KEY,
  dsatracao     TEXT NULL,
  dtcriacao     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu      DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_atracaodescricao_atracao
    FOREIGN KEY (atracao_id) REFERENCES atracao(atracao_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE evento (
  evento_id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id         BIGINT NOT NULL,
  loja_id                BIGINT NOT NULL,
  nmtituloevento         VARCHAR(120) NOT NULL,
  dtinicioevento         DATETIME NOT NULL,
  dtfimevento            DATETIME NULL,
  nmlocalevento          VARCHAR(120) NULL,
  dsendlocevento         VARCHAR(200) NULL,
  urlbannerevento        VARCHAR(255) NULL,
  statusevento           ENUM('RASCUNHO','ATIVO','ENCERRADO','CANCELADO') NOT NULL DEFAULT 'RASCUNHO',
  dtcriacao              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu               DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_evento_org_loja_id (
    organizacao_id,
    loja_id,
    evento_id
  ),

  CONSTRAINT fk_evento_loja
    FOREIGN KEY (organizacao_id, loja_id)
    REFERENCES loja(organizacao_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE eventodescricao (
  evento_id                 BIGINT PRIMARY KEY,
  dsdescevento              TEXT NULL,
  dspoliticacancelamento    TEXT NULL,
  dspoliticareembolso       TEXT NULL,
  dspoliticacashback        TEXT NULL,
  dtcriacao                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu                  DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_eventodescricao_evento
    FOREIGN KEY (evento_id) REFERENCES evento(evento_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_evento_loja_status_dt
  ON evento(organizacao_id, loja_id, statusevento, dtinicioevento);

CREATE INDEX idx_evento_titulo
  ON evento(nmtituloevento);

CREATE TABLE eventoatracao (
  eventoatracao_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  evento_id           BIGINT NOT NULL,
  atracao_id          BIGINT NOT NULL,
  dtinicioatracao     DATETIME NOT NULL,
  dtfimatracao        DATETIME NOT NULL,
  dtcriacao           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu            DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_eventoatracao_evento
    FOREIGN KEY (evento_id)
    REFERENCES evento(evento_id)
    ON DELETE CASCADE ON UPDATE CASCADE,

  CONSTRAINT fk_eventoatracao_atracao
    FOREIGN KEY (atracao_id)
    REFERENCES atracao(atracao_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT chk_eventoatracao_periodo
    CHECK (dtfimatracao > dtinicioatracao),

  CONSTRAINT uq_eventoatracao_evento_atracao_inicio
    UNIQUE (evento_id, atracao_id, dtinicioatracao),

  INDEX idx_eventoatracao_periodo (
    dtinicioatracao,
    dtfimatracao
  )
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE eventolote (
  lote_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id   BIGINT NOT NULL,
  loja_id          BIGINT NOT NULL,
  evento_id        BIGINT NOT NULL,
  nmlote           VARCHAR(80) NOT NULL,
  vrprecolote      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  qttotallote      INT NULL,
  qtvendidalote    INT NULL,
  dtiniciovenda    DATETIME NULL,
  dtfimvenda       DATETIME NULL,
  statuslote       ENUM('ATIVO','ESGOTADO','ENCERRADO','INATIVO') NOT NULL DEFAULT 'ATIVO',
  dtcriacao        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu         DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  UNIQUE KEY uk_lote_org_loja_id (
    organizacao_id,
    loja_id,
    lote_id
  ),

  UNIQUE KEY uk_lote_evento_nome (
    evento_id,
    nmlote
  ),

  CONSTRAINT fk_lote_evento
    FOREIGN KEY (organizacao_id, loja_id, evento_id)
    REFERENCES evento(organizacao_id, loja_id, evento_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,

  CONSTRAINT chk_lote_quantidades
    CHECK (
      (qttotallote IS NULL OR qttotallote >= 0)
      AND (qtvendidalote IS NULL OR qtvendidalote >= 0)
      AND (
        qttotallote IS NULL
        OR qtvendidalote IS NULL
        OR qtvendidalote <= qttotallote
      )
    ),

  CONSTRAINT chk_lote_preco
    CHECK (vrprecolote >= 0)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_lote_evento_status
  ON eventolote(evento_id, statuslote);

CREATE INDEX idx_lote_loja_evento
  ON eventolote(organizacao_id, loja_id, evento_id);


-- FKs que dependem de eventolote (adiadas para evitar erro de ordem)
ALTER TABLE produto
  ADD CONSTRAINT fk_produto_eventolote
  FOREIGN KEY (organizacao_id, loja_id, lote_id)
  REFERENCES eventolote(organizacao_id, loja_id, lote_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE itcarrinho
  ADD CONSTRAINT fk_itcarrinho_produto_lote
  FOREIGN KEY (produto_id, lote_id)
  REFERENCES produto(produto_id, lote_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE itvenda
  ADD CONSTRAINT fk_itvenda_lote
  FOREIGN KEY (lote_id) REFERENCES eventolote(lote_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

ALTER TABLE reserva_ingresso
  ADD CONSTRAINT fk_reserva_lote
  FOREIGN KEY (lote_id) REFERENCES eventolote(lote_id)
  ON DELETE RESTRICT ON UPDATE CASCADE;

ALTER TABLE reserva_ingresso
  ADD CONSTRAINT fk_reserva_evento
  FOREIGN KEY (evento_id) REFERENCES evento(evento_id)
  ON DELETE RESTRICT ON UPDATE CASCADE;


CREATE TABLE checkout_asaas (
  checkout_asaas_id BIGINT NOT NULL AUTO_INCREMENT,
  carrinho_id BIGINT NULL,
  reserva_ingresso_id BIGINT NULL,
  cliente_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  venda_id BIGINT NULL,

  checkout_id VARCHAR(100) NOT NULL,
  payment_id VARCHAR(100) NULL,
  pix_qr_code_id VARCHAR(100) NULL,
  pix_payload TEXT NULL,
  pix_encoded_image LONGTEXT NULL,
  pix_expiration_date DATETIME NULL,
  external_reference VARCHAR(100) NULL,
  status VARCHAR(30) NULL DEFAULT 'ACTIVE',
  dsorigemconfirmacao VARCHAR(20) NULL,
  dtconfirmacao DATETIME NULL,

  dtcriacao DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  checkout_url VARCHAR(500) NULL,
  valor DECIMAL(10,2) NULL,
  vrtaxaclubbar DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  vrcashbackusado DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  asaas_wallet_loja VARCHAR(100) NULL,
  asaas_wallet_clubbar VARCHAR(100) NULL,

  PRIMARY KEY (checkout_asaas_id),
  UNIQUE KEY uk_checkout_asaas_checkout_id (checkout_id),
  UNIQUE KEY uk_checkout_asaas_payment_id (payment_id),
  UNIQUE KEY uk_checkout_asaas_pix_qr_code_id (pix_qr_code_id),
  INDEX idx_checkout_asaas_venda_id (venda_id),
  INDEX idx_checkout_asaas_carrinho_id (carrinho_id),
  INDEX idx_checkout_asaas_reserva (reserva_ingresso_id),
  INDEX idx_checkout_asaas_cliente_id (cliente_id),
  INDEX idx_checkout_asaas_loja_id (loja_id),
  INDEX idx_checkout_asaas_status (status),
  INDEX idx_checkout_asaas_origem_confirmacao (dsorigemconfirmacao, dtconfirmacao),

  CONSTRAINT fk_checkout_asaas_carrinho
    FOREIGN KEY (carrinho_id, cliente_id, loja_id)
    REFERENCES carrinho(carrinho_id, cliente_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_checkout_asaas_venda
    FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_checkout_asaas_reserva
    FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id),
  CONSTRAINT chk_checkout_asaas_origem
    CHECK ((carrinho_id IS NULL) <> (reserva_ingresso_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS checkout_asaas_item (
  checkout_asaas_item_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  checkout_asaas_id BIGINT NOT NULL,
  produto_id BIGINT NULL,
  lote_id BIGINT NULL,
  idtipoproduto VARCHAR(1) NOT NULL DEFAULT 'P',
  nmproduto VARCHAR(150) NOT NULL,
  quantidade INT NOT NULL,
  vrunitario DECIMAL(10,2) NOT NULL,
  subtotal DECIMAL(10,2) NOT NULL,
  total_com_taxa DECIMAL(10,2) NOT NULL,
  pctaxaitvenda DECIMAL(10,2) NOT NULL DEFAULT 0,
  vrtaxaitvenda DECIMAL(10,2) NOT NULL DEFAULT 0,
  dsobsitem VARCHAR(255) NULL,
  nmparticipante VARCHAR(150) NULL,
  cpfparticipante VARCHAR(11) NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_checkout_asaas_item_checkout (checkout_asaas_id),
  INDEX idx_checkout_asaas_item_produto (produto_id),
  CONSTRAINT fk_checkout_asaas_item_checkout
    FOREIGN KEY (checkout_asaas_id) REFERENCES checkout_asaas(checkout_asaas_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_checkout_asaas_item_produto
    FOREIGN KEY (produto_id) REFERENCES produto(produto_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_checkout_asaas_item_lote
    FOREIGN KEY (lote_id) REFERENCES eventolote(lote_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS checkout_asaas_pagador (
  checkout_asaas_pagador_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  checkout_asaas_id BIGINT NOT NULL,
  venda_id BIGINT NULL,
  payment_id VARCHAR(100) NULL,
  asaas_customer_id VARCHAR(100) NULL,
  nome VARCHAR(150) NULL,
  cpf_cnpj VARCHAR(20) NULL,
  email VARCHAR(160) NULL,
  telefone VARCHAR(20) NULL,
  endereco VARCHAR(150) NULL,
  numero VARCHAR(20) NULL,
  complemento VARCHAR(80) NULL,
  bairro VARCHAR(80) NULL,
  cep VARCHAR(10) NULL,
  cidade VARCHAR(100) NULL,
  uf VARCHAR(2) NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_checkout_asaas_pagador_checkout (checkout_asaas_id),
  INDEX idx_checkout_asaas_pagador_venda (venda_id),
  INDEX idx_checkout_asaas_pagador_cpf_cnpj (cpf_cnpj),
  CONSTRAINT fk_checkout_asaas_pagador_checkout
    FOREIGN KEY (checkout_asaas_id) REFERENCES checkout_asaas(checkout_asaas_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_checkout_asaas_pagador_venda
    FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE lojacontabancaria (
  lojacontabancaria_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  codigobanco VARCHAR(10) NOT NULL,
  nmbanco VARCHAR(100) NULL,
  agencia VARCHAR(20) NOT NULL,
  nrconta VARCHAR(30) NOT NULL,
  digitoconta VARCHAR(5) NULL,
  tipoconta VARCHAR(20) NOT NULL DEFAULT 'CORRENTE',
  nmtitular VARCHAR(150) NOT NULL,
  cpfcnpjtitular VARCHAR(20) NOT NULL,
  chavepix VARCHAR(150) NULL,
  tipochavepix VARCHAR(20) NULL,
  status VARCHAR(15) NOT NULL DEFAULT 'ATIVA',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_lojacontabancaria_loja (loja_id),
  CONSTRAINT fk_lojacontabancaria_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao (organizacao_id),
  CONSTRAINT fk_lojacontabancaria_loja FOREIGN KEY (loja_id) REFERENCES loja (loja_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE repassefinanceiro (
  repassefinanceiro_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  venda_id BIGINT NOT NULL,
  checkout_asaas_id BIGINT NULL,
  vrbruto DECIMAL(10,2) NOT NULL,
  vrtaxaclubbar DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  vrrepasse DECIMAL(10,2) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'PENDENTE',
  dtprevista DATE NULL,
  dtpagamento DATETIME NULL,
  idtransferencia VARCHAR(100) NULL,
  urlcomprovante VARCHAR(500) NULL,
  observacao TEXT NULL,
  codigobanco VARCHAR(10) NULL,
  agencia VARCHAR(20) NULL,
  nrconta VARCHAR(30) NULL,
  digitoconta VARCHAR(5) NULL,
  tipoconta VARCHAR(20) NULL,
  nmtitular VARCHAR(150) NULL,
  cpfcnpjtitular VARCHAR(20) NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_repassefinanceiro_venda (venda_id),
  INDEX idx_repassefinanceiro_status_data (status, dtcriacao),
  INDEX idx_repassefinanceiro_loja (loja_id),
  CONSTRAINT fk_repassefinanceiro_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao (organizacao_id),
  CONSTRAINT fk_repassefinanceiro_loja FOREIGN KEY (loja_id) REFERENCES loja (loja_id),
  CONSTRAINT fk_repassefinanceiro_venda FOREIGN KEY (venda_id) REFERENCES venda (venda_id),
  CONSTRAINT fk_repassefinanceiro_checkout FOREIGN KEY (checkout_asaas_id) REFERENCES checkout_asaas (checkout_asaas_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cashback_config (
    cashback_config_id BIGINT NOT NULL AUTO_INCREMENT,

    organizacao_id BIGINT NOT NULL,
    loja_id BIGINT NOT NULL,

    sitcashback VARCHAR(10)
        COLLATE utf8mb4_unicode_ci
        NOT NULL DEFAULT 'ATIVO',

    pccashback DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    vrmincompra DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    vrmaxcashback DECIMAL(10,2)
        DEFAULT NULL,

    nrdiapliberacao INT
        NOT NULL DEFAULT 7,

    nrdiavalidade INT
        NOT NULL DEFAULT 90,

    permiteusoparcial CHAR(1)
        COLLATE utf8mb4_unicode_ci
        NOT NULL DEFAULT 'S',

    pcmaxusocompra DECIMAL(10,2)
        NOT NULL DEFAULT 30.00,

    dtcriacao DATETIME
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    dtultatu DATETIME
        NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (cashback_config_id),

    UNIQUE KEY uk_cashback_config_loja (loja_id),

    KEY idx_cashback_config_organizacao (
        organizacao_id
    ),

    KEY idx_cashback_config_situacao (
        sitcashback
    ),

    CONSTRAINT fk_cashback_config_loja
        FOREIGN KEY (
            organizacao_id,
            loja_id
        )
        REFERENCES loja (
            organizacao_id,
            loja_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_cashback_config_situacao
        CHECK (
            sitcashback IN ('ATIVO', 'INATIVO')
        ),

    CONSTRAINT chk_cashback_config_percentual
        CHECK (
            pccashback >= 0
            AND pccashback <= 100
        ),

    CONSTRAINT chk_cashback_config_valores
        CHECK (
            vrmincompra >= 0
            AND (
                vrmaxcashback IS NULL
                OR vrmaxcashback >= 0
            )
        ),

    CONSTRAINT chk_cashback_config_dias
        CHECK (
            nrdiapliberacao >= 0
            AND nrdiavalidade >= 0
        ),

    CONSTRAINT chk_cashback_config_uso_parcial
        CHECK (
            permiteusoparcial IN ('S', 'N')
        ),

    CONSTRAINT chk_cashback_config_max_uso
        CHECK (
            pcmaxusocompra IS NULL
            OR (
                pcmaxusocompra >= 0
                AND pcmaxusocompra <= 100
            )
        )
)
ENGINE = InnoDB
DEFAULT CHARSET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

CREATE TABLE cashback_movimento (
    cashback_movimento_id BIGINT
        NOT NULL AUTO_INCREMENT,

    cliente_id BIGINT NOT NULL,
    organizacao_id BIGINT NOT NULL,
    loja_id BIGINT NOT NULL,

    venda_origem_id BIGINT DEFAULT NULL,
    venda_uso_id BIGINT DEFAULT NULL,
    checkout_asaas_id BIGINT DEFAULT NULL,
    cashback_movimento_origem_id BIGINT DEFAULT NULL,

    tipomovimento VARCHAR(15)
        COLLATE utf8mb4_unicode_ci
        NOT NULL,

    sitcashback VARCHAR(15)
        COLLATE utf8mb4_unicode_ci
        NOT NULL,

    pcaplicado DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    vrbase DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    vrcashback DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    descricao VARCHAR(255)
        COLLATE utf8mb4_unicode_ci
        DEFAULT NULL,

    observacao VARCHAR(500)
        COLLATE utf8mb4_unicode_ci
        DEFAULT NULL,

    dtmovimento DATETIME
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    dtliberacao DATETIME DEFAULT NULL,
    dtvalidade DATETIME DEFAULT NULL,
    dtutilizacao DATETIME DEFAULT NULL,

    PRIMARY KEY (
        cashback_movimento_id
    ),

    KEY idx_cashback_movimento_cliente_loja (
        cliente_id,
        loja_id
    ),

    KEY idx_cashback_movimento_status (
        sitcashback
    ),

    KEY idx_cashback_movimento_data (
        dtmovimento
    ),

    KEY idx_cashback_movimento_venda_origem (
        venda_origem_id
    ),

    KEY idx_cashback_movimento_venda_uso (
        venda_uso_id
    ),
    KEY idx_cashback_movimento_checkout (checkout_asaas_id),
    KEY idx_cashback_movimento_origem (cashback_movimento_origem_id),

    KEY idx_cashback_movimento_loja (
        organizacao_id,
        loja_id
    ),

    CONSTRAINT fk_cashback_movimento_cliente
        FOREIGN KEY (
            cliente_id
        )
        REFERENCES cliente (
            cliente_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_cashback_movimento_loja
        FOREIGN KEY (
            organizacao_id,
            loja_id
        )
        REFERENCES loja (
            organizacao_id,
            loja_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_cashback_movimento_venda_origem
        FOREIGN KEY (
            venda_origem_id
        )
        REFERENCES venda (
            venda_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_cashback_movimento_venda_uso
        FOREIGN KEY (
            venda_uso_id
        )
        REFERENCES venda (
            venda_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT fk_cashback_movimento_checkout FOREIGN KEY (checkout_asaas_id) REFERENCES checkout_asaas(checkout_asaas_id),
    CONSTRAINT fk_cashback_movimento_origem FOREIGN KEY (cashback_movimento_origem_id) REFERENCES cashback_movimento(cashback_movimento_id),

    CONSTRAINT chk_cashback_movimento_percentual
        CHECK (
            pcaplicado >= 0
            AND pcaplicado <= 100
        ),

    CONSTRAINT chk_cashback_movimento_valores
        CHECK (
            vrbase >= 0
            AND vrcashback >= 0
        ),

    CONSTRAINT chk_cashback_movimento_datas
        CHECK (
            dtvalidade IS NULL
            OR dtliberacao IS NULL
            OR dtvalidade >= dtliberacao
        )
)
ENGINE = InnoDB
DEFAULT CHARSET = utf8mb4
COLLATE = utf8mb4_unicode_ci;

CREATE TABLE cashback_saldo (
    cashback_saldo_id BIGINT
        NOT NULL AUTO_INCREMENT,

    cliente_id BIGINT NOT NULL,
    organizacao_id BIGINT NOT NULL,
    loja_id BIGINT NOT NULL,

    vrdisponivel DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    vrpendente DECIMAL(10,2)
        NOT NULL DEFAULT 0.00,

    dtultatu DATETIME
        NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (
        cashback_saldo_id
    ),

    UNIQUE KEY uk_cashback_saldo_cliente_loja (
        cliente_id,
        loja_id
    ),

    KEY idx_cashback_saldo_loja (
        organizacao_id,
        loja_id
    ),

    KEY idx_cashback_saldo_cliente (
        cliente_id
    ),

    CONSTRAINT fk_cashback_saldo_cliente
        FOREIGN KEY (
            cliente_id
        )
        REFERENCES cliente (
            cliente_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT fk_cashback_saldo_loja
        FOREIGN KEY (
            organizacao_id,
            loja_id
        )
        REFERENCES loja (
            organizacao_id,
            loja_id
        )
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,

    CONSTRAINT chk_cashback_saldo_valores
        CHECK (
            vrdisponivel >= 0
            AND vrpendente >= 0
        )
)
ENGINE = InnoDB
DEFAULT CHARSET = utf8mb4
COLLATE = utf8mb4_unicode_ci;
