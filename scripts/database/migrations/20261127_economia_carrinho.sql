-- Preserva o preço anterior à promoção no momento da inclusão.
ALTER TABLE itcarrinho ADD COLUMN vrpreco_original DECIMAL(10,2) NULL;
