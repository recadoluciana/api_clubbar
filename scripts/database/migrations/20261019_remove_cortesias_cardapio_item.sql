-- Cortesias passam a ser configuradas somente em campanhas do estabelecimento.
-- Itens gratuitos ou com desconto integral são removidos do cardápio; o produto
-- mestre e o histórico de vendas permanecem preservados.
DELETE FROM cardapioitem
WHERE vrpreco <= 0
   OR (tipodesconto = 'PERCENTUAL' AND vrdesconto >= 100)
   OR (tipodesconto = 'VALOR' AND vrdesconto >= vrpreco);

ALTER TABLE cardapioitem DROP COLUMN IF EXISTS qtcortesia;
ALTER TABLE cardapioitem DROP COLUMN IF EXISTS dtinicortesia;
ALTER TABLE cardapioitem DROP COLUMN IF EXISTS dtfimcortesia;
