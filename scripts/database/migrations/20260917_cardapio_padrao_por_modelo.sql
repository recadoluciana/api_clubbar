-- As tabelas antigas de cardápio padrão não continham cardapiomodelo_id.
-- No ambiente atual ambas estão vazias; confirme isso antes da migração.
ALTER TABLE cardapio_padrao_categoria
  DROP INDEX uk_cardapio_padrao_categoria_nome,
  ADD COLUMN cardapiomodelo_id BIGINT NOT NULL AFTER organizacao_id,
  ADD COLUMN categoria_id BIGINT NOT NULL AFTER cardapiomodelo_id,
  ADD COLUMN dsicone VARCHAR(50) NULL AFTER nmcategoria,
  ADD CONSTRAINT fk_cardapio_padrao_categoria_modelo
    FOREIGN KEY (cardapiomodelo_id) REFERENCES cardapiomodelo(cardapiomodelo_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_cardapio_padrao_categoria_categoria
    FOREIGN KEY (categoria_id) REFERENCES categoria(categoria_id),
  ADD UNIQUE KEY uk_cardapio_padrao_categoria_modelo_categoria (cardapiomodelo_id, categoria_id);

ALTER TABLE cardapio_padrao_produto
  DROP INDEX uk_cardapio_padrao_produto_nome,
  MODIFY COLUMN cardapio_padrao_categoria_id BIGINT NOT NULL,
  ADD COLUMN skuproduto VARCHAR(100) NULL AFTER sitproduto,
  ADD UNIQUE KEY uk_cardapio_padrao_produto_categoria_nome (cardapio_padrao_categoria_id, nmproduto);
