-- Repara bancos em que as migrations PIX do checkout_asaas não foram aplicadas.
-- As verificações tornam a migration segura para ambientes parcialmente atualizados.

DELIMITER //
CREATE PROCEDURE migrate_checkout_asaas_schema()
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND COLUMN_NAME = 'venda_id') THEN
    ALTER TABLE checkout_asaas ADD COLUMN venda_id BIGINT NULL AFTER loja_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND COLUMN_NAME = 'pix_qr_code_id') THEN
    ALTER TABLE checkout_asaas ADD COLUMN pix_qr_code_id VARCHAR(100) NULL AFTER payment_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND COLUMN_NAME = 'pix_payload') THEN
    ALTER TABLE checkout_asaas ADD COLUMN pix_payload TEXT NULL AFTER pix_qr_code_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND COLUMN_NAME = 'pix_encoded_image') THEN
    ALTER TABLE checkout_asaas ADD COLUMN pix_encoded_image LONGTEXT NULL AFTER pix_payload;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND COLUMN_NAME = 'pix_expiration_date') THEN
    ALTER TABLE checkout_asaas ADD COLUMN pix_expiration_date DATETIME NULL AFTER pix_encoded_image;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND INDEX_NAME = 'uk_checkout_asaas_pix_qr_code_id') THEN
    ALTER TABLE checkout_asaas ADD UNIQUE KEY uk_checkout_asaas_pix_qr_code_id (pix_qr_code_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND INDEX_NAME = 'idx_checkout_asaas_venda_id') THEN
    ALTER TABLE checkout_asaas ADD INDEX idx_checkout_asaas_venda_id (venda_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'checkout_asaas' AND CONSTRAINT_NAME = 'fk_checkout_asaas_venda') THEN
    ALTER TABLE checkout_asaas ADD CONSTRAINT fk_checkout_asaas_venda FOREIGN KEY (venda_id) REFERENCES venda(venda_id) ON DELETE RESTRICT ON UPDATE CASCADE;
  END IF;
END//
CALL migrate_checkout_asaas_schema()//
DROP PROCEDURE migrate_checkout_asaas_schema//
DELIMITER ;
