CREATE TABLE IF NOT EXISTS beneficioprodutocampanha (
  beneficioprodutocampanha_id BIGINT NOT NULL AUTO_INCREMENT,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  produto_id BIGINT NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  nmcampanha VARCHAR(120) NOT NULL,
  dthrinicio DATETIME NOT NULL,
  dthrfim DATETIME NOT NULL,
  qtlimite INT NULL,
  limite_cliente_dia INT NOT NULL DEFAULT 1,
  situacao VARCHAR(20) NOT NULL DEFAULT 'ATIVA',
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL,
  PRIMARY KEY (beneficioprodutocampanha_id),
  KEY ix_bpc_loja_produto (loja_id, produto_id),
  CONSTRAINT fk_bpc_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id),
  CONSTRAINT fk_bpc_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id),
  CONSTRAINT fk_bpc_produto FOREIGN KEY (produto_id) REFERENCES produto(produto_id)
);

CREATE TABLE IF NOT EXISTS beneficioprodutoresgate (
  beneficioprodutoresgate_id BIGINT NOT NULL AUTO_INCREMENT,
  campanha_id BIGINT NOT NULL,
  cliente_id BIGINT NOT NULL,
  produto_id BIGINT NOT NULL,
  percentual_desconto DECIMAL(5,2) NOT NULL DEFAULT 0,
  situacao VARCHAR(20) NOT NULL DEFAULT 'DISPONIVEL',
  dtresgate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtexpiracao DATETIME NULL,
  venda_id BIGINT NULL,
  PRIMARY KEY (beneficioprodutoresgate_id),
  KEY ix_bpr_cliente_produto (cliente_id, produto_id),
  CONSTRAINT fk_bpr_campanha FOREIGN KEY (campanha_id) REFERENCES beneficioprodutocampanha(beneficioprodutocampanha_id),
  CONSTRAINT fk_bpr_cliente FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id),
  CONSTRAINT fk_bpr_produto FOREIGN KEY (produto_id) REFERENCES produto(produto_id),
  CONSTRAINT fk_bpr_venda FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
);

ALTER TABLE itcarrinho ADD COLUMN beneficioprodutoresgate_id BIGINT NULL AFTER cardapioitem_id;
ALTER TABLE itcarrinho ADD CONSTRAINT fk_itcarrinho_beneficio_resgate FOREIGN KEY (beneficioprodutoresgate_id) REFERENCES beneficioprodutoresgate(beneficioprodutoresgate_id);
ALTER TABLE itvenda ADD COLUMN beneficioprodutoresgate_id BIGINT NULL AFTER cardapioitem_id;
ALTER TABLE itvenda ADD CONSTRAINT fk_itvenda_beneficio_resgate FOREIGN KEY (beneficioprodutoresgate_id) REFERENCES beneficioprodutoresgate(beneficioprodutoresgate_id);
