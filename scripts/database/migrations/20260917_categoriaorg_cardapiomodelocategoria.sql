-- Executar depois de 20260917_cardapio_padrao_por_modelo.sql.
-- Categorias e produtos padrão antigos devem estar vazios; não apaga produtos gerais.
RENAME TABLE categoria TO categoriaorg, cardapio_padrao_categoria TO cardapiomodelocategoria;

CREATE TABLE produtocategoriaorg (
  produto_id BIGINT NOT NULL,
  categoria_id BIGINT NOT NULL,
  PRIMARY KEY (produto_id, categoria_id),
  CONSTRAINT fk_produtocategoriaorg_produto FOREIGN KEY (produto_id) REFERENCES produto(produto_id) ON DELETE CASCADE,
  CONSTRAINT fk_produtocategoriaorg_categoria FOREIGN KEY (categoria_id) REFERENCES categoriaorg(categoria_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO produtocategoriaorg (produto_id, categoria_id)
SELECT produto_id, categoria_id FROM produto WHERE categoria_id IS NOT NULL;

ALTER TABLE produto
  DROP FOREIGN KEY fk_produto_categoria,
  DROP INDEX idx_produto_categoria,
  DROP COLUMN categoria_id;

ALTER TABLE cardapio_padrao_produto
  DROP FOREIGN KEY fk_cardapio_padrao_produto_categoria,
  DROP INDEX uk_cardapio_padrao_produto_categoria_nome,
  DROP INDEX idx_cardapio_padrao_produto_categoria,
  DROP COLUMN cardapio_padrao_categoria_id,
  ADD UNIQUE KEY uk_cardapio_padrao_produto_org_nome (organizacao_id, nmproduto);

ALTER TABLE cardapiomodelocategoria
  CHANGE COLUMN cardapio_padrao_categoria_id cardapiomodelocategoria_id BIGINT NOT NULL AUTO_INCREMENT,
  DROP COLUMN nmcategoria,
  DROP COLUMN dsicone,
  DROP COLUMN sitcategoria,
  DROP INDEX uk_cardapio_padrao_categoria_modelo_categoria,
  ADD UNIQUE KEY uk_cardapiomodelocategoria_modelo_categoria (cardapiomodelo_id, categoria_id);

CREATE TABLE cardapiomodeloproduto (
  cardapiomodeloproduto_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  cardapiomodelocategoria_id BIGINT NOT NULL,
  cardapio_padrao_produto_id BIGINT NOT NULL,
  idorditem INT NOT NULL DEFAULT 1,
  CONSTRAINT fk_cardapiomodeloproduto_categoria FOREIGN KEY (cardapiomodelocategoria_id)
    REFERENCES cardapiomodelocategoria(cardapiomodelocategoria_id) ON DELETE CASCADE,
  CONSTRAINT fk_cardapiomodeloproduto_produto FOREIGN KEY (cardapio_padrao_produto_id)
    REFERENCES cardapio_padrao_produto(cardapio_padrao_produto_id),
  UNIQUE KEY uk_cardapiomodeloproduto_categoria_produto (cardapiomodelocategoria_id, cardapio_padrao_produto_id)
) ENGINE=InnoDB DEFAULT CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE cardapioitem
  ADD KEY idx_cardapioitem_versao (cardapioversao_id),
  ADD UNIQUE KEY uk_cardapioitem_categoria_produto (cardapioversaocategoria_id, produto_id);

ALTER TABLE cardapioitem DROP INDEX uk_cardapioitem_produto;
