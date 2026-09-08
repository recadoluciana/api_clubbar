ALTER TABLE itcarrinho DROP FOREIGN KEY fk_itcarrinho_produto_lote;
ALTER TABLE produto DROP FOREIGN KEY fk_produto_eventolote;
ALTER TABLE produto DROP FOREIGN KEY fk_produto_loja;
DROP INDEX idx_produto_org_loja_sit ON produto;
DROP INDEX idx_produto_org_loja_sit_nome ON produto;
DROP INDEX uq_produto_lote ON produto;
ALTER TABLE produto
  DROP COLUMN loja_id,
  DROP COLUMN lote_id,
  DROP COLUMN idtipoproduto;
CREATE INDEX idx_produto_org_sit ON produto(organizacao_id, sitproduto);
CREATE INDEX idx_produto_org_sit_nome ON produto(organizacao_id, sitproduto, nmproduto);
