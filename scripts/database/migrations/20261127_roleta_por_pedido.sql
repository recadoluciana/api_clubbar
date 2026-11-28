ALTER TABLE beneficioprodutoresgate ADD COLUMN carrinho_id BIGINT NULL;
ALTER TABLE beneficioprodutoresgate ADD COLUMN origem_giro VARCHAR(20) NULL;
ALTER TABLE beneficioprodutoresgate ADD UNIQUE KEY uk_roleta_carrinho_produto_origem (carrinho_id, produto_id, origem_giro);
ALTER TABLE checkout_asaas_item ADD COLUMN beneficioprodutoresgate_id BIGINT NULL;
