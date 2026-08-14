CREATE TABLE IF NOT EXISTS checkout_asaas_item (
  checkout_asaas_item_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  checkout_asaas_id BIGINT NOT NULL,
  produto_id BIGINT NOT NULL,
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
