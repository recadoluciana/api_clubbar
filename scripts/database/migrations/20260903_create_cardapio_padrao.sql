CREATE TABLE cardapio_padrao_categoria (
  cardapio_padrao_categoria_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  nmcategoria VARCHAR(120) NOT NULL,
  sitcategoria VARCHAR(10) NOT NULL DEFAULT 'ATIVA',
  idordcategoria BIGINT NOT NULL DEFAULT 1,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_cardapio_padrao_categoria_org
    FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  UNIQUE KEY uk_cardapio_padrao_categoria_nome (organizacao_id, nmcategoria),
  KEY idx_cardapio_padrao_categoria_org (organizacao_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cardapio_padrao_produto (
  cardapio_padrao_produto_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  cardapio_padrao_categoria_id BIGINT NULL,
  nmproduto VARCHAR(100) NOT NULL,
  dsproduto VARCHAR(255) NULL,
  vrprecoprod DECIMAL(10,2) NOT NULL,
  sitproduto VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  urlfotoproduto VARCHAR(255) NULL,
  tipodesconto VARCHAR(15) NOT NULL DEFAULT 'NENHUM',
  vrdesconto DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  pccashback DECIMAL(10,2) NULL,
  dtinidesconto DATETIME NULL,
  dtfimdesconto DATETIME NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_cardapio_padrao_produto_org
    FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_cardapio_padrao_produto_categoria
    FOREIGN KEY (cardapio_padrao_categoria_id)
    REFERENCES cardapio_padrao_categoria(cardapio_padrao_categoria_id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  UNIQUE KEY uk_cardapio_padrao_produto_nome (organizacao_id, nmproduto),
  KEY idx_cardapio_padrao_produto_org (organizacao_id),
  KEY idx_cardapio_padrao_produto_categoria (cardapio_padrao_categoria_id),
  CONSTRAINT chk_cardapio_padrao_produto_preco CHECK (vrprecoprod >= 0),
  CONSTRAINT chk_cardapio_padrao_produto_cashback
    CHECK (pccashback IS NULL OR (pccashback >= 0 AND pccashback <= 100))
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
