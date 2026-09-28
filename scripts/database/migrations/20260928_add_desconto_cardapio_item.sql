-- Descontos passam a pertencer ao item do cardápio, permitindo valores
-- diferentes para o mesmo produto em cada estabelecimento/cardápio.
ALTER TABLE cardapioitem
  ADD COLUMN tipodesconto ENUM('NENHUM', 'PERCENTUAL', 'VALOR') NOT NULL DEFAULT 'NENHUM' AFTER vrpreco,
  ADD COLUMN vrdesconto DECIMAL(10,2) NOT NULL DEFAULT 0.00 AFTER tipodesconto,
  ADD COLUMN dtinidesconto DATETIME NULL AFTER vrdesconto,
  ADD COLUMN dtfimdesconto DATETIME NULL AFTER dtinidesconto;

-- Preserva as promoções que já existiam nos produtos.
UPDATE cardapioitem item
INNER JOIN produto produto ON produto.produto_id = item.produto_id
SET item.tipodesconto = produto.tipodesconto,
    item.vrdesconto = produto.vrdesconto,
    item.dtinidesconto = produto.dtinidesconto,
    item.dtfimdesconto = produto.dtfimdesconto
WHERE produto.tipodesconto <> 'NENHUM';
