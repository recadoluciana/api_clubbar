-- O preço do carrinho passa a ser sempre o preço atual do cardapioitem.
-- Itens legados sem vínculo com o cardápio não podem mais permanecer no carrinho.
DELETE FROM itcarrinho
WHERE cardapioitem_id IS NULL;

ALTER TABLE itcarrinho
  MODIFY COLUMN cardapioitem_id BIGINT NOT NULL,
  DROP COLUMN vrunitario;
