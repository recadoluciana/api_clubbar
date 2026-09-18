-- Aplicar somente depois de confirmar que cardapiomodeloproduto e
-- cardapio_padrao_produto estão vazias. Produto é o cadastro único da organização.
DROP TABLE cardapiomodeloproduto;
DROP TABLE cardapio_padrao_produto;

CREATE TABLE cardapiomodeloproduto (
  cardapiomodeloproduto_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  cardapiomodelocategoria_id BIGINT NOT NULL,
  produto_id BIGINT NOT NULL,
  idorditem INT NOT NULL DEFAULT 1,
  CONSTRAINT fk_cardapiomodeloproduto_categoria FOREIGN KEY (cardapiomodelocategoria_id)
    REFERENCES cardapiomodelocategoria(cardapiomodelocategoria_id) ON DELETE CASCADE,
  CONSTRAINT fk_cardapiomodeloproduto_produto FOREIGN KEY (produto_id)
    REFERENCES produto(produto_id),
  UNIQUE KEY uk_cardapiomodeloproduto_categoria_produto (cardapiomodelocategoria_id, produto_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
