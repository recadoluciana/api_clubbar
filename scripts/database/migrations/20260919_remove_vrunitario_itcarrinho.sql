-- O preço do carrinho passa a ser sempre o preço atual do cardapioitem.
-- Itens legados sem vínculo com o cardápio não podem mais permanecer no carrinho.
DELETE FROM itcarrinho
WHERE cardapioitem_id IS NULL;

ALTER TABLE itcarrinho
  DROP FOREIGN KEY fk_itcarrinho_cardapioitem,
  MODIFY COLUMN cardapioitem_id BIGINT NOT NULL,
  DROP COLUMN vrunitario;

ALTER TABLE itcarrinho
  ADD CONSTRAINT fk_itcarrinho_cardapioitem
  FOREIGN KEY (cardapioitem_id)
  REFERENCES cardapioitem(cardapioitem_id)
  ON DELETE CASCADE ON UPDATE CASCADE;
