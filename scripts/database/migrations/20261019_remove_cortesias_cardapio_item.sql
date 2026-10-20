-- Cortesias passam a ser configuradas somente em campanhas do estabelecimento.
-- Preserve os itens existentes: preços zerados recebem R$ 5,00 e descontos
-- integrais são removidos. O histórico de vendas não é alterado.
ALTER TABLE produto
ADD COLUMN IF NOT EXISTS vrprecopadrao DECIMAL(10,2) NOT NULL DEFAULT 5.00;

ALTER TABLE produto
ALTER COLUMN vrprecopadrao SET DEFAULT 5.00;

UPDATE produto
SET vrprecopadrao = 5.00
WHERE vrprecopadrao IS NULL OR vrprecopadrao <= 0;

UPDATE cardapioitem
SET vrpreco = 5.00
WHERE vrpreco IS NULL OR vrpreco <= 0;

UPDATE cardapioitem
SET tipodesconto = 'NENHUM',
    vrdesconto = 0.00,
    dtinidesconto = NULL,
    dtfimdesconto = NULL
WHERE (tipodesconto = 'PERCENTUAL' AND vrdesconto >= 100)
   OR (tipodesconto = 'VALOR' AND vrdesconto >= vrpreco);

ALTER TABLE cardapioitem DROP COLUMN IF EXISTS qtcortesia;
ALTER TABLE cardapioitem DROP COLUMN IF EXISTS dtinicortesia;
ALTER TABLE cardapioitem DROP COLUMN IF EXISTS dtfimcortesia;
