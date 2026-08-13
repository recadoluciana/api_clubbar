ALTER TABLE checkout_asaas
  ADD COLUMN venda_id BIGINT NULL AFTER loja_id,
  ADD COLUMN pix_qr_code_id VARCHAR(100) NULL AFTER payment_id,
  ADD UNIQUE KEY uk_checkout_asaas_pix_qr_code_id (pix_qr_code_id),
  ADD INDEX idx_checkout_asaas_venda_id (venda_id),
  ADD CONSTRAINT fk_checkout_asaas_venda
    FOREIGN KEY (venda_id) REFERENCES venda(venda_id)
    ON DELETE RESTRICT ON UPDATE CASCADE;
