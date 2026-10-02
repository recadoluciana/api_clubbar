ALTER TABLE itcarrinho
  ADD COLUMN vrunitario DECIMAL(10,2) NULL AFTER cardapioitem_id;

UPDATE itcarrinho ic
LEFT JOIN cardapioitem ci ON ci.cardapioitem_id = ic.cardapioitem_id
LEFT JOIN produto p ON p.produto_id = ic.produto_id
SET ic.vrunitario = COALESCE(ci.vrpreco, p.vrprecoprod, 0);

ALTER TABLE itcarrinho DROP FOREIGN KEY fk_itcarrinho_cardapioitem;

ALTER TABLE itcarrinho
  MODIFY COLUMN cardapioitem_id BIGINT NULL,
  MODIFY COLUMN vrunitario DECIMAL(10,2) NOT NULL,
  ADD CONSTRAINT fk_itcarrinho_cardapioitem
    FOREIGN KEY (cardapioitem_id)
    REFERENCES cardapioitem(cardapioitem_id)
    ON DELETE SET NULL ON UPDATE CASCADE;
