-- CLUBBAR / BITBEER
-- Schema completo para MySQL 8.0.16 ou superior.
-- Execute este arquivo dentro de um banco de dados já selecionado com USE.

SET NAMES utf8mb4;


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


CREATE TABLE organizacao (
    organizacao_id BIGINT NOT NULL AUTO_INCREMENT,

    -- Identificação
    nmorganizacao VARCHAR(120) NOT NULL,
    rzsocialorganizacao VARCHAR(160) NOT NULL,
    cnpjorganizacao CHAR(14) NOT NULL,

    -- Contato administrativo
    emailorganizacao VARCHAR(255) NOT NULL,
    telorganizacao VARCHAR(25) NOT NULL,

    -- Endereço fiscal/administrativo
    ceporganizacao VARCHAR(20) NULL,
    endorganizacao VARCHAR(255) NOT NULL,
    nrendorganizacao VARCHAR(20) NOT NULL,
    complorganizacao VARCHAR(120) NULL,

    cidade_id BIGINT NOT NULL,
    nmbairro varchar(120) NULL,

    -- Controle
    sitorganizacao VARCHAR(15) NOT NULL DEFAULT 'ATIVA',

    dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    dtultatu DATETIME NULL
        DEFAULT NULL
        ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (organizacao_id),

    UNIQUE KEY uk_organizacao_cnpj (
        cnpjorganizacao
    ),

    KEY idx_organizacao_nome (
        nmorganizacao
    ),

    KEY idx_organizacao_situacao (
        sitorganizacao
    ),

    KEY idx_organizacao_cidade (
        cidade_id
    ),

    CONSTRAINT fk_organizacao_cidade
        FOREIGN KEY (cidade_id)
        REFERENCES cidade(cidade_id)
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
  nmloja         VARCHAR(120) NOT NULL,
  endloja        VARCHAR(255) NULL,
  dsrefeloja     VARCHAR(255) NULL,
  dsinstaloja    VARCHAR(255) NULL,
  dsbairroloja   VARCHAR(120) NULL,
  sitloja        VARCHAR(15) NOT NULL DEFAULT 'ATIVA',
  aberto24x7     CHAR(1) NOT NULL DEFAULT 'N',
  dshorarioloja  VARCHAR(255) NULL,
  nrtelloja      VARCHAR(25) NULL,
  nrdiavalidade  BIGINT NOT NULL DEFAULT 90,
  cidade_id      BIGINT NOT NULL,
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
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_loja_org ON loja(organizacao_id);
ALTER TABLE loja
  ADD UNIQUE KEY uk_loja_org_id (organizacao_id, loja_id);

ALTER TABLE loja
  ADD CONSTRAINT chk_aberto24x7 CHECK (aberto24x7 IN ('S', 'N'));

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

  CONSTRAINT chk_cliente_localizacao
    CHECK (
      (pais_id IS NULL AND estado_id IS NULL AND cidade_id IS NULL)
      OR
      (pais_id IS NOT NULL AND estado_id IS NOT NULL AND cidade_id IS NOT NULL)
    )

) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_cliente_asaas       ON cliente(idclienteasaas);

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
    CHECK (vrdesconto >= 0)
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
  sitcarrinho      ENUM('ABERTO','FECHADO') NOT NULL DEFAULT 'ABERTO',
  idpixmercadopago VARCHAR(80) NULL,
  vrpixmercadopago DECIMAL(12,2) NULL,
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

CREATE TABLE itcarrinho (
  itcarrinho_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  carrinho_id      BIGINT NOT NULL,
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
  cliente_id       BIGINT NOT NULL,
  carrinho_id      BIGINT NOT NULL,
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

  CONSTRAINT chk_venda_total
    CHECK (totalvenda >= 0)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_venda_loja_cliente_data
  ON venda(organizacao_id, loja_id, cliente_id, dtcriacao);

CREATE INDEX idx_venda_cliente_data
  ON venda(cliente_id, dtcriacao);

CREATE TABLE itvenda (
  itvenda_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  venda_id              BIGINT NOT NULL,
  produto_id            BIGINT NOT NULL,
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

  CONSTRAINT uq_itvenda_qrtoken
    UNIQUE (qrtokenitvenda)
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE INDEX idx_itvenda_venda
  ON itvenda(venda_id);

CREATE INDEX idx_itvenda_lote
  ON itvenda(lote_id);

CREATE INDEX idx_itvenda_entrega
  ON itvenda(identregaitvenda, dtentregaitvenda);

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
  ADD COLUMN provedor VARCHAR(40) NOT NULL DEFAULT 'MERCADOPAGO',
  ADD COLUMN reference_id VARCHAR(80) NULL,
  ADD COLUMN checkout_id VARCHAR(120) NULL,
  ADD COLUMN pay_url VARCHAR(255) NULL;

CREATE INDEX idx_pagvenda
  ON pagvenda(venda_id);

CREATE INDEX idx_sitpagvenda
  ON pagvenda(sitpagvenda, dtcriacao);

CREATE INDEX idx_pagvenda_reference
  ON pagvenda(reference_id);

CREATE TABLE evento (
  evento_id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id         BIGINT NOT NULL,
  loja_id                BIGINT NOT NULL,
  nmtituloevento         VARCHAR(120) NOT NULL,
  dsdescevento           TEXT NULL,
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

CREATE INDEX idx_evento_loja_status_dt
  ON evento(organizacao_id, loja_id, statusevento, dtinicioevento);

CREATE INDEX idx_evento_titulo
  ON evento(nmtituloevento);

CREATE TABLE eventolote (
  lote_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id   BIGINT NOT NULL,
  loja_id          BIGINT NOT NULL,
  evento_id        BIGINT NOT NULL,
  nmlote           VARCHAR(80) NOT NULL,
  vrprecolote      DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  qttotallote      INT NOT NULL DEFAULT 0,
  qtvendidalote    INT NOT NULL DEFAULT 0,
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
      qttotallote >= 0
      AND qtvendidalote >= 0
      AND qtvendidalote <= qttotallote
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
  ADD CONSTRAINT fk_itvenda_produto_lote
  FOREIGN KEY (produto_id, lote_id)
  REFERENCES produto(produto_id, lote_id)
  ON DELETE RESTRICT ON UPDATE RESTRICT;

CREATE TABLE leadparceiro (
  leadparceiro_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  nmresponsavel     VARCHAR(120) NOT NULL,
  nmestabelecimento VARCHAR(160) NOT NULL,
  tipo              VARCHAR(30) NOT NULL,
  telefone          VARCHAR(30) NOT NULL,
  email             VARCHAR(160) NOT NULL,
  estado_id         BIGINT NOT NULL,
  cidade_id         BIGINT NOT NULL,
  mensagem          TEXT NULL,
  status            ENUM(
                      'NOVO',
                      'CONTATADO',
                      'NEGOCIANDO',
                      'CONVERTIDO',
                      'PERDIDO'
                    ) NOT NULL DEFAULT 'NOVO',
  dtcriacao         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu          DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_leadparceiro_estado
    FOREIGN KEY (estado_id)
    REFERENCES estado(estado_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,

  CONSTRAINT fk_leadparceiro_cidade
    FOREIGN KEY (cidade_id)
    REFERENCES cidade(cidade_id)
    ON DELETE RESTRICT
    ON UPDATE RESTRICT,

  INDEX idx_leadparceiro_status (status),
  INDEX idx_leadparceiro_estado (estado_id),
  INDEX idx_leadparceiro_cidade (cidade_id),
  INDEX idx_leadparceiro_email (email),
  INDEX idx_leadparceiro_dtcriacao (dtcriacao)
) ENGINE=InnoDB;



CREATE TABLE checkout_asaas (
  checkout_asaas_id BIGINT NOT NULL AUTO_INCREMENT,
  carrinho_id BIGINT NOT NULL,
  cliente_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,

  checkout_id VARCHAR(100) NOT NULL,
  payment_id VARCHAR(100) NULL,
  external_reference VARCHAR(100) NULL,
  status VARCHAR(30) NULL DEFAULT 'ACTIVE',

  dtcriacao DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  checkout_url VARCHAR(500) NULL,
  valor DECIMAL(10,2) NULL,

  PRIMARY KEY (checkout_asaas_id),
  UNIQUE KEY uk_checkout_asaas_checkout_id (checkout_id),
  UNIQUE KEY uk_checkout_asaas_payment_id (payment_id),
  INDEX idx_checkout_asaas_carrinho_id (carrinho_id),
  INDEX idx_checkout_asaas_cliente_id (cliente_id),
  INDEX idx_checkout_asaas_loja_id (loja_id),
  INDEX idx_checkout_asaas_status (status),

  CONSTRAINT fk_checkout_asaas_carrinho
    FOREIGN KEY (carrinho_id, cliente_id, loja_id)
    REFERENCES carrinho(carrinho_id, cliente_id, loja_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;
