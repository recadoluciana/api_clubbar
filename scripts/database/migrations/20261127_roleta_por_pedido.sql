-- Seguro para bancos em que o fluxo anterior já criou parte das colunas.
SET @sql_roleta = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'beneficioprodutoresgate' AND COLUMN_NAME = 'carrinho_id') = 0, 'ALTER TABLE beneficioprodutoresgate ADD COLUMN carrinho_id BIGINT NULL', 'SELECT 1');
PREPARE roleta_stmt FROM @sql_roleta; EXECUTE roleta_stmt; DEALLOCATE PREPARE roleta_stmt;
SET @sql_roleta = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'beneficioprodutoresgate' AND COLUMN_NAME = 'origem_giro') = 0, 'ALTER TABLE beneficioprodutoresgate ADD COLUMN origem_giro VARCHAR(20) NULL', 'SELECT 1');
PREPARE roleta_stmt FROM @sql_roleta; EXECUTE roleta_stmt; DEALLOCATE PREPARE roleta_stmt;
SET @sql_roleta = IF((SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'beneficioprodutoresgate' AND INDEX_NAME = 'uk_roleta_carrinho_produto_origem') = 0, 'ALTER TABLE beneficioprodutoresgate ADD UNIQUE KEY uk_roleta_carrinho_produto_origem (carrinho_id, produto_id, origem_giro)', 'SELECT 1');
PREPARE roleta_stmt FROM @sql_roleta; EXECUTE roleta_stmt; DEALLOCATE PREPARE roleta_stmt;
SET @sql_roleta = IF((SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas_item' AND COLUMN_NAME = 'beneficioprodutoresgate_id') = 0, 'ALTER TABLE checkout_asaas_item ADD COLUMN beneficioprodutoresgate_id BIGINT NULL', 'SELECT 1');
PREPARE roleta_stmt FROM @sql_roleta; EXECUTE roleta_stmt; DEALLOCATE PREPARE roleta_stmt;
