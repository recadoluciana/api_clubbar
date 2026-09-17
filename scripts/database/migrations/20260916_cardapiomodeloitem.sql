CREATE TABLE IF NOT EXISTS cardapiomodeloitem (
  cardapiomodeloitem_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  cardapiomodelo_id BIGINT NOT NULL,
  produto_id BIGINT NOT NULL,
  vrpreco DECIMAL(10,2) NOT NULL,
  idorditem INT NOT NULL DEFAULT 1,
  CONSTRAINT fk_cardapiomodeloitem_modelo FOREIGN KEY (cardapiomodelo_id) REFERENCES cardapiomodelo(cardapiomodelo_id) ON DELETE CASCADE,
  CONSTRAINT fk_cardapiomodeloitem_produto FOREIGN KEY (produto_id) REFERENCES produto(produto_id),
  UNIQUE KEY uk_cardapiomodeloitem_produto (cardapiomodelo_id, produto_id),
  CONSTRAINT chk_cardapiomodeloitem_preco CHECK (vrpreco >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
