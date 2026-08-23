CREATE TABLE reserva_ingresso (
  reserva_ingresso_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  organizacao_id BIGINT NOT NULL,
  loja_id BIGINT NOT NULL,
  cliente_id BIGINT NOT NULL,
  evento_id BIGINT NOT NULL,
  lote_id BIGINT NOT NULL,
  produto_id BIGINT NOT NULL,
  venda_id BIGINT NULL,
  qtreservada INT NOT NULL,
  vrunitario DECIMAL(10,2) NOT NULL,
  pctaxa DECIMAL(10,2) NOT NULL DEFAULT 0,
  vrtaxa DECIMAL(10,2) NOT NULL DEFAULT 0,
  vrtotal DECIMAL(10,2) NOT NULL,
  sitreserva ENUM('PREENCHENDO','AGUARDANDO_PAGAMENTO','CONFIRMADA','EXPIRADA','CANCELADA') NOT NULL DEFAULT 'PREENCHENDO',
  dtexpiracao DATETIME NOT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reserva_venda (venda_id),
  INDEX idx_reserva_lote_status_expiracao (lote_id, sitreserva, dtexpiracao),
  INDEX idx_reserva_cliente (cliente_id, dtcriacao),
  CONSTRAINT fk_reserva_organizacao FOREIGN KEY (organizacao_id) REFERENCES organizacao(organizacao_id),
  CONSTRAINT fk_reserva_loja FOREIGN KEY (loja_id) REFERENCES loja(loja_id),
  CONSTRAINT fk_reserva_cliente FOREIGN KEY (cliente_id) REFERENCES cliente(cliente_id),
  CONSTRAINT fk_reserva_evento FOREIGN KEY (evento_id) REFERENCES evento(evento_id),
  CONSTRAINT fk_reserva_lote FOREIGN KEY (lote_id) REFERENCES eventolote(lote_id),
  CONSTRAINT fk_reserva_produto FOREIGN KEY (produto_id) REFERENCES produto(produto_id),
  CONSTRAINT chk_reserva_quantidade CHECK (qtreservada > 0),
  CONSTRAINT chk_reserva_valores CHECK (vrunitario >= 0 AND pctaxa >= 0 AND vrtaxa >= 0 AND vrtotal >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE reserva_ingresso_participante (
  reserva_ingresso_participante_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  reserva_ingresso_id BIGINT NOT NULL,
  ordem INT NOT NULL,
  nmparticipante VARCHAR(150) NOT NULL,
  cpfparticipante VARCHAR(11) NOT NULL,
  itvenda_id BIGINT NULL,
  dtcriacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  dtultatu DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_reserva_participante_ordem (reserva_ingresso_id, ordem),
  INDEX idx_reserva_participante_cpf (cpfparticipante),
  INDEX idx_reserva_participante_itvenda (itvenda_id),
  CONSTRAINT fk_reserva_participante_reserva FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id) ON DELETE CASCADE,
  CONSTRAINT fk_reserva_participante_itvenda FOREIGN KEY (itvenda_id) REFERENCES itvenda(itvenda_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE venda MODIFY carrinho_id BIGINT NULL;
ALTER TABLE venda ADD COLUMN reserva_ingresso_id BIGINT NULL AFTER carrinho_id;
ALTER TABLE venda ADD UNIQUE KEY uk_venda_reserva_ingresso (reserva_ingresso_id);
ALTER TABLE venda ADD CONSTRAINT fk_venda_reserva_ingresso FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id);
ALTER TABLE venda ADD CONSTRAINT chk_venda_origem CHECK ((carrinho_id IS NULL) <> (reserva_ingresso_id IS NULL));
ALTER TABLE reserva_ingresso ADD CONSTRAINT fk_reserva_venda FOREIGN KEY (venda_id) REFERENCES venda(venda_id);

ALTER TABLE checkout_asaas MODIFY carrinho_id BIGINT NULL;
ALTER TABLE checkout_asaas ADD COLUMN reserva_ingresso_id BIGINT NULL AFTER carrinho_id;
ALTER TABLE checkout_asaas ADD INDEX idx_checkout_asaas_reserva (reserva_ingresso_id);
ALTER TABLE checkout_asaas ADD CONSTRAINT fk_checkout_asaas_reserva FOREIGN KEY (reserva_ingresso_id) REFERENCES reserva_ingresso(reserva_ingresso_id);
ALTER TABLE checkout_asaas ADD CONSTRAINT chk_checkout_asaas_origem CHECK ((carrinho_id IS NULL) <> (reserva_ingresso_id IS NULL));
