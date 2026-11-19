CREATE TABLE compra_evento (
  compra_evento_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  cliente_id BIGINT NOT NULL,
  evento_id BIGINT NOT NULL,
  venda_id BIGINT NULL,
  status ENUM('ABERTA','AGUARDANDO_PAGAMENTO','PAGA','EXPIRADA','CANCELADA') NOT NULL DEFAULT 'ABERTA',
  valor_total DECIMAL(10,2) NOT NULL DEFAULT 0,
  dtexpiracao DATETIME NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL,
  INDEX idx_compra_evento_cliente_status (cliente_id, status),
  INDEX idx_compra_evento_evento (evento_id),
  FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id),
  FOREIGN KEY (loja_id) REFERENCES loja(loja_id),
  FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id),
  FOREIGN KEY (evento_id) REFERENCES evento(evento_id),
  FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE compra_evento_item (
  compra_evento_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  compra_evento_id BIGINT NOT NULL,
  tipoitem ENUM('INGRESSO','PRODUTO') NOT NULL,
  reserva_ingresso_id BIGINT NULL,
  produto_id BIGINT NULL,
  quantidade BIGINT NOT NULL DEFAULT 1,
  valor_unitario DECIMAL(10,2) NOT NULL,
  valor_taxa DECIMAL(10,2) NOT NULL DEFAULT 0,
  subtotal DECIMAL(10,2) NOT NULL,
  descricao_snapshot VARCHAR(255) NULL,
  INDEX idx_compra_evento_item_compra (compra_evento_id),
  FOREIGN KEY (compra_evento_id) REFERENCES compra_evento(compra_evento_id) ON DELETE CASCADE,
  FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id),
  FOREIGN KEY (produto_id) REFERENCES produto(produto_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE reserva_ingresso ADD COLUMN compra_evento_id BIGINT NULL;
CREATE INDEX ix_reserva_ingresso_compra_evento_id ON reserva_ingresso(compra_evento_id);
ALTER TABLE reserva_ingresso ADD CONSTRAINT fk_reserva_compra_evento FOREIGN KEY (compra_evento_id) REFERENCES compra_evento(compra_evento_id);
