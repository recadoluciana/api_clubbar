ALTER TABLE beneficioprodutoresgate ADD COLUMN carrinho_id BIGINT NULL;
ALTER TABLE beneficioprodutoresgate ADD UNIQUE KEY uk_roleta_carrinho_produto (carrinho_id, produto_id);
ALTER TABLE checkout_asaas_item ADD COLUMN beneficioprodutoresgate_id BIGINT NULL;
